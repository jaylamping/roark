//! Preflight and the enable sequence on `vcan`: `safety` played as control would, over the bus layer's slow requests
//! and batches, against `sim-drive` (safety.md section 6: each rule proven on `vcan`).
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusLinks, CommandBatch, SlowKind, SlowOutcome, SlowRefusal, SlowRequest, Snapshot,
};
use common::{HZ, drive, id, info, next_snapshot, soon, timing};
use robstride::drive::{Command, HostFrame};
use robstride::{
    CanTimeout, Damper, Drive, EchoKind, Mode, Model, NewtonMeters, Param, ParamValue, Reporting,
    StatusFault, StatusFaults, Uid, Volts, encode,
};
use safety::{
    EnableFailure, Enabling, Next, Preflight, PreflightPassed, RUN_WITHIN_NS, Refusal, Register,
    RuleId, Seen, Step, Target,
};
use sim_drive::{Fault, SimDrive, ensure_vcan, serve};
use telemetry::{Epoch, Recorder, Recording, Session};

/// Shared with the exit, slow-request and fault tests, which nextest runs one at a time with these
/// (`.config/nextest.toml`, group `can0`).
const BUS: &str = "can0";
/// The UID the skeleton below gives drive 101.
const UID: Uid = Uid([0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef]);

/// One commissioned RS03 on `BUS`, every fact and cap set.
const SKELETON: &str = "\
schema: 1
name: sim_suite
power:
  source: bench_24v
  vbus_v: [22.0, 26.0]
  current_budget_a: 40.0
buses:
  can0:
    bitrate_bps: 1000000
    sample_point: 0.75
    adapter_serial: null
limbs:
  left_arm:
    joints:
      - name: arm_joint_one
        actuator: rs03
        bus: can0
        id: 101
        uid: \"0x0123456789abcdef\"
        direction: -1
        zero_rad: 2.0
        reference_pose: null
        hard_rad: [-0.5, 1.5]
        soft_rad: null
        torque_cap_nm: 10.0
        current_cap_a: 12.0
        speed_cap_rad_s: 1.0
  right_arm:
    joints: []
  waist:
    joints: []
  left_leg:
    joints: []
  right_leg:
    joints: []
";

/// What the drive does once preflight has passed.
#[derive(Clone, Copy)]
enum After {
    /// Answers as a drive does. The sim serves without a break.
    Answers,
    /// Answers nothing from then on: it never reaches Run as far as the host can tell. The sim stops serving when
    /// preflight passes and serves the silent drive again, and nothing it could have missed in between would answer.
    Silent,
    /// Put in Run by something other than this host once preflight has passed, as another controller's Enable leaves
    /// it: in Run (`Fault::Mode`), answering that Enable with a Run status on the bus. The sim stops serving when
    /// preflight passes and serves again from there; control begins the enable sequence once that status shows, as it
    /// would if it came in the ticks before the Enable.
    RunByAnother,
}

impl After {
    /// Whether what the drive does after preflight shows in `seen`, the proof made at `proved_ns`, so control can begin
    /// the enable sequence.
    fn shown(self, seen: Seen<'_>, proved_ns: u64) -> bool {
        match self {
            Self::Answers | Self::Silent => true,
            Self::RunByAnother => seen
                .view()
                .mode
                .is_some_and(|m| m.mode == Mode::Run && m.read_ns >= proved_ns),
        }
    }
}

/// What control does with the enable sequence, besides stepping it every tick.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Control {
    /// Steps it every tick and sends what it asks in that tick's batch.
    Steady,
    /// Stops stepping it once its reporting off's echo shows, until 50 ms after that echo was read, still sending an
    /// empty batch every tick: control stalled on the sequence alone. With no Enable sent the limb is idle, so the
    /// bus's control-silence stop doesn't apply either way.
    StallAfterEcho,
    /// Puts the Enable in a batch already expired: the bus counts it stale and holds its commands back, so the Enable
    /// never goes out, as on a tick control handed over late.
    ExpireEnable,
}

impl Control {
    /// Whether control skips stepping the sequence this tick, at `now_ns`.
    fn holds(self, seen: Seen<'_>, now_ns: u64) -> bool {
        self == Self::StallAfterEcho
            && seen.view().last_echo.is_some_and(|echo| {
                echo.kind == EchoKind::Reporting(Reporting::Off)
                    && now_ns <= echo.read_ns + RUN_WITHIN_NS
            })
    }
}

/// How control's attempt ended.
#[derive(Debug, PartialEq)]
enum Ended {
    Refused(Refusal),
    Enabled,
    /// The enable sequence gave up before its Enable was planned: refused.
    GaveUp(EnableFailure),
    /// The enable sequence gave up once its Enable was planned: the limb must be stopped.
    Stop(EnableFailure),
}

/// Where control is.
enum Phase {
    Preflight(Preflight),
    /// Passed; waiting for the sim to apply what comes after.
    Handing(PreflightPassed),
    Enabling(Enabling),
}

/// Sets every stop flag when dropped, including while a failed assertion unwinds.
struct Stop<'a>(&'a AtomicBool, &'a AtomicBool, Arc<AtomicBool>);

impl Drop for Stop<'_> {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
        self.1.store(true, Ordering::Release);
        self.2.store(true, Ordering::Release);
    }
}

/// [`attempt_under`] with control steady.
fn attempt(uid: Uid, start: Option<Fault>, after: After) -> Ended {
    attempt_under(uid, start, after, Control::Steady)
}

/// Run preflight and, if it passes, the enable sequence for drive 101 on `BUS`, playing control on the bus layer's
/// rings as `control` says, against a sim drive answering with `uid`, with `start` applied before it serves, and doing
/// `after` once preflight passes.
#[expect(
    clippy::unwrap_used,
    clippy::too_many_lines,
    reason = "test helper: one control loop, start to end"
)]
fn attempt_under(uid: Uid, start: Option<Fault>, after: After, control: Control) -> Ended {
    ensure_vcan(BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-enable-{}", std::process::id()));
    let (passed, applied, stop_sim) = (
        AtomicBool::new(false),
        AtomicBool::new(false),
        AtomicBool::new(false),
    );
    let exit = Arc::new(AtomicBool::new(false));
    let skeleton = skeleton::parse(SKELETON).unwrap();
    let joint = skeleton.limbs.first().unwrap().joints.first().unwrap();
    let target = Target::new(joint, &skeleton.power).unwrap();
    let bus_name = joint.bus.clone().unwrap();
    assert_eq!(bus_name.as_str(), BUS);
    let ended = std::thread::scope(|scope| {
        let _stop = Stop(&passed, &stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [SimDrive::new(Drive::new(id(101), Model::Rs03), uid, 5)];
            if let Some(fault) = start {
                drives[0].inject(Instant::now(), fault).unwrap();
            }
            match after {
                After::Answers => {}
                After::Silent => {
                    serve(BUS, &mut drives, &passed, &mut |_| {})?;
                    drives[0].inject(Instant::now(), Fault::Silent).unwrap();
                }
                After::RunByAnother => {
                    serve(BUS, &mut drives, &passed, &mut |_| {})?;
                    let now = Instant::now();
                    drives[0].inject(now, Fault::Mode(Mode::Run)).unwrap();
                    let enable = HostFrame {
                        target: id(101),
                        command: Command::Enable,
                    };
                    drives[0].receive(now, enable);
                }
            }
            applied.store(true, Ordering::Release);
            serve(BUS, &mut drives, &stop_sim, &mut |_| {})
        });
        let session = Session::start(&root, info(BUS), 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (mut commands, commands_rx) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(64);
        let (mut requests, requests_rx) = rtrb::RingBuffer::new(4);
        let (results_tx, mut results) = rtrb::RingBuffer::new(4);
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                drives: vec![drive(101, 0)],
                timing: timing(),
            },
            BusLinks {
                commands: commands_rx,
                snapshots: snapshots_tx,
                recorder: buses.remove(0),
                requests: requests_rx,
                results: results_tx,
                orders: rtrb::RingBuffer::new(1).1,
                rearmed: rtrb::RingBuffer::new(1).0,
                epoch,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();

        let end = Instant::now() + Duration::from_secs(10);
        // Before preflight, a get-ID until the sim answers, so its first request doesn't race the sim's socket; asked
        // again on a time-out or a stall of this thread, a few times at most.
        let (mut serving, mut asked, mut retries) = (false, false, 0);
        let mut phase = None;
        let mut tag = 0;
        let ended = loop {
            let snap = newest(&mut snapshots, end);
            let now = epoch.ns(Instant::now());
            let seen = Seen::of(&bus_name, &snap, 0).unwrap();
            let mut batch = batch_after(&snap, epoch);
            if !serving {
                if let Ok(result) = results.pop() {
                    assert_eq!(result.tag, tag, "one request at a time");
                    serving = matches!(result.outcome, SlowOutcome::Identity(_));
                    assert!(
                        serving
                            || (retries < 5
                                && matches!(
                                    result.outcome,
                                    SlowOutcome::TimedOut
                                        | SlowOutcome::Refused(SlowRefusal::ControlSilent)
                                )),
                        "{result:?}"
                    );
                    retries += u32::from(!serving);
                    asked = false;
                }
                if !serving && !asked {
                    tag += 1;
                    let request = SlowRequest {
                        tag,
                        slot: 0,
                        kind: SlowKind::GetId,
                    };
                    assert!(requests.push(request).is_ok());
                    asked = true;
                }
                // This tick's batch goes out either way; preflight starts with the next.
                assert!(commands.push(batch).is_ok());
                continue;
            }
            // Preflight's tags follow the get-IDs': it tells its own results by them.
            let current = phase
                .take()
                .unwrap_or_else(|| Phase::Preflight(Preflight::start(target, 0, tag + 1, now)));
            let (next, ended) = match current {
                Phase::Preflight(mut preflight) => {
                    if let Ok(result) = results.pop() {
                        preflight.answered(result, now);
                        assert_eq!(preflight.ignored(), 0, "one request at a time: {result:?}");
                    }
                    match preflight.poll(seen, now) {
                        Step::Submit(request) => {
                            assert!(requests.push(request).is_ok());
                            (Some(Phase::Preflight(preflight)), None)
                        }
                        Step::Wait => (Some(Phase::Preflight(preflight)), None),
                        Step::Passed(proof) => {
                            passed.store(true, Ordering::Release);
                            (Some(Phase::Handing(proof)), None)
                        }
                        Step::Refused(refusal) => (None, Some(Ended::Refused(refusal))),
                        Step::Spent => (None, Some(Ended::Refused(Refusal::NoStatus))),
                    }
                }
                Phase::Handing(proof)
                    if applied.load(Ordering::Acquire) && after.shown(seen, proof.at_ns()) =>
                {
                    (Some(Phase::Enabling(Enabling::new(proof, now))), None)
                }
                Phase::Handing(proof) => (Some(Phase::Handing(proof)), None),
                Phase::Enabling(enabling) if control.holds(seen, now) => {
                    (Some(Phase::Enabling(enabling)), None)
                }
                Phase::Enabling(mut enabling) => match enabling.step(seen, snap.tick + 1, now) {
                    Next::Send(frame) => {
                        if control == Control::ExpireEnable && frame == encode::enable(id(101)) {
                            batch = CommandBatch::new(snap.tick + 1, 0);
                        }
                        assert!(batch.set(0, frame));
                        (Some(Phase::Enabling(enabling)), None)
                    }
                    Next::Wait => (Some(Phase::Enabling(enabling)), None),
                    Next::Enabled => (None, Some(Ended::Enabled)),
                    Next::Refused(failure) => (None, Some(Ended::GaveUp(failure))),
                    Next::Stop(failure) => (None, Some(Ended::Stop(failure))),
                },
            };
            assert!(commands.push(batch).is_ok());
            if let Some(ended) = ended {
                break ended;
            }
            phase = next;
        };

        exit.store(true, Ordering::Release);
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        passed.store(true, Ordering::Release);
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
        ended
    });
    let _ = std::fs::remove_dir_all(&root);
    ended
}

/// The newest snapshot, waiting for one; so a late wake of the test thread never answers an old tick.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the bus publishes until the deadline"
)]
fn newest(snapshots: &mut rtrb::Consumer<Snapshot>, end: Instant) -> Snapshot {
    let mut snap = next_snapshot(snapshots, end).unwrap();
    // At most the ring's worth: the bus publishes once a period, so this never chases it.
    for _ in 0..snapshots.buffer().capacity() {
        let Ok(newer) = snapshots.pop() else { break };
        snap = newer;
    }
    snap
}

/// An empty batch for the tick after `snap`, good for three periods.
fn batch_after(snap: &Snapshot, epoch: Epoch) -> CommandBatch {
    let period = 1_000_000_000 / HZ;
    CommandBatch::new(snap.tick + 1, epoch.ns(Instant::now()) + 3 * period)
}

/// Guards: safety - `host.preflight` and `host.mode`: on a real socket, preflight writes and reads back every register
/// through the bus's slow requests and passes a drive that answers truthfully, and the enable sequence hands it to
/// control only after its Run status and the fresh Run answering the `run_mode` = MIT write (PLAN item 2, Enable one
/// drive; item 6 Preflight row).
#[test]
fn a_truthful_drive_passes_preflight_and_enables_on_vcan() {
    assert_eq!(attempt(UID, None, After::Answers), Ended::Enabled);
}

/// Guards: safety - `host.identity`: on a real socket, a drive answering get-ID with another UID than the skeleton's
/// is refused before anything is written (PLAN item 3, Scan and identity; item 6 Identity row).
#[test]
fn a_drive_with_another_uid_is_refused_on_vcan() {
    let other = Uid([9; 8]);
    let ended = attempt(other, None, After::Answers);
    assert_eq!(
        ended,
        Ended::Refused(Refusal::Uid {
            read: other,
            expected: UID
        })
    );
    let Ended::Refused(refusal) = ended else {
        return;
    };
    assert_eq!(refusal.rule(), RuleId::HostIdentity);
}

/// Guards: safety - `host.mode`: on a real socket, a drive that passed preflight and then never shows Run after its
/// Enable ends the sequence within 50 ms, and since the Enable went out the limb must be stopped (PLAN item 2, refuse
/// after 50 ms; item 6 Mode row).
#[test]
fn a_drive_that_never_reaches_run_fails_the_enable_on_vcan() {
    let ended = attempt(UID, None, After::Silent);
    assert_eq!(ended, Ended::Stop(EnableFailure::NoRun { last: None }));
    assert_eq!(EnableFailure::NoRun { last: None }.rule(), RuleId::HostMode);
}

/// Guards: safety - `host.preflight` on a real socket: a drive in another mode than Reset (here Calibration, as another
/// controller could leave it) is refused at the first status it shows, and never enabled (PLAN item 6 Preflight row:
/// the drive in Reset).
#[test]
fn a_drive_not_in_reset_is_refused_on_vcan() {
    let ended = attempt(UID, Some(Fault::Mode(Mode::Calibration)), After::Answers);
    assert_eq!(
        ended,
        Ended::Refused(Refusal::NotReset {
            mode: Mode::Calibration
        })
    );
    let Ended::Refused(refusal) = ended else {
        return;
    };
    assert_eq!(refusal.rule(), RuleId::HostPreflight);
}

impl Ended {
    /// The rule it was refused or stopped under, if it was.
    fn rule(&self) -> Option<RuleId> {
        match self {
            Self::Refused(refusal) => Some(refusal.rule()),
            Self::GaveUp(failure) | Self::Stop(failure) => Some(failure.rule()),
            Self::Enabled => None,
        }
    }
}

/// Guards: safety - `drive.can_timeout`, `drive.caps`, `drive.damper` and `host.preflight` on a real socket: each
/// failure injected in `sim-drive` (a write not kept, the damper off, VBUS out of its window, a fault bit, a drive put
/// in Run by something else after its preflight) refuses the enable under its rule, with no Enable sent (PLAN item 6
/// drive layer and Preflight row: proven on `vcan`).
#[test]
fn each_preflight_failure_refuses_the_enable_on_vcan() {
    let rs03 = Model::Rs03.ranges();
    let window = skeleton::parse(SKELETON).unwrap().power.vbus_v;
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let volts = |v| Volts::new(v).unwrap();
    let rows = [
        // Writes answered but not kept: canTimeout reads its power-up 0, limit_torque the model's highest.
        (
            Some(Fault::IgnoreWrites(Param::CanTimeout)),
            After::Answers,
            Ended::Refused(Refusal::CanTimeout {
                read: CanTimeout::OFF,
            }),
            RuleId::DriveCanTimeout,
        ),
        (
            Some(Fault::IgnoreWrites(Param::LimitTorque)),
            After::Answers,
            Ended::Refused(Refusal::Cap {
                register: Register::LimitTorque,
                written: ParamValue::NewtonMeters(NewtonMeters::new(10.0).unwrap()),
                read: ParamValue::NewtonMeters(rs03.torque_max),
            }),
            RuleId::DriveCaps,
        ),
        // Registers preflight only reads: an injected value holds.
        (
            Some(Fault::Param(
                Param::Damper,
                ParamValue::Damper(Damper::ProtectionOff),
            )),
            After::Answers,
            Ended::Refused(Refusal::DamperOff),
            RuleId::DriveDamper,
        ),
        (
            Some(Fault::Param(Param::Vbus, ParamValue::Volts(volts(30.0)))),
            After::Answers,
            Ended::Refused(Refusal::Vbus {
                read: volts(30.0),
                window,
            }),
            RuleId::HostPreflight,
        ),
        (
            Some(Fault::FaultBits(over)),
            After::Answers,
            Ended::Refused(Refusal::Faults { bits: over }),
            RuleId::HostPreflight,
        ),
        (
            None,
            After::RunByAnother,
            Ended::GaveUp(EnableFailure::NotReset { mode: Mode::Run }),
            RuleId::HostPreflight,
        ),
    ];
    for (start, after, expected, rule) in rows {
        let ended = attempt(UID, start, after);
        assert_eq!(ended, expected, "{start:?}");
        assert_eq!(ended.rule(), Some(rule), "{start:?}");
    }
}

/// Guards: safety - `host.bus` on a real socket: control stalling on the sequence for more than 50 ms after its
/// reporting off's echo, before the tick that would plan the Enable, refuses the enable when it resumes, with no Enable
/// sent: the proof is that much older (PLAN item 2, Enable one drive; item 6 Bus row).
#[test]
fn a_stall_after_the_reporting_off_refuses_the_enable_on_vcan() {
    let ended = attempt_under(UID, None, After::Answers, Control::StallAfterEcho);
    assert_eq!(ended, Ended::GaveUp(EnableFailure::Stalled));
    assert_eq!(ended.rule(), Some(RuleId::HostBus));
}

/// Guards: safety - `host.bus` on a real socket: an Enable the bus never sends (its batch expired, so the bus held it
/// back) and no Run within 50 ms of its planning ends the sequence as an Enable not seen to go out, and since it may
/// have gone the limb is stopped (PLAN item 2, Enable one drive; item 6 Bus row).
#[test]
fn an_enable_the_bus_never_sends_stops_the_limb_on_vcan() {
    let ended = attempt_under(UID, None, After::Answers, Control::ExpireEnable);
    assert_eq!(ended, Ended::Stop(EnableFailure::NoEnableEcho));
    assert_eq!(ended.rule(), Some(RuleId::HostBus));
}
