//! Preflight and the enable sequence on `vcan`: `safety` played as control would, over the bus layer's slow requests
//! and batches, against `sim-drive` (safety.md section 7: each rule proven on `vcan`).
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusConfig, BusLinks, CommandBatch, SlowRequest, Snapshot};
use common::{HZ, drive, id, info, next_snapshot, soon, timing};
use robstride::{Drive, Model, Uid};
use safety::{
    EnableFailure, Enabling, Next, Preflight, PreflightPassed, Refusal, RuleId, Step, Target,
};
use sim_drive::{Fault, SimDrive, ensure_vcan, serve};
use telemetry::{Epoch, Recorder, Recording, Session};

/// Shared with the slow-request and fault tests, which nextest runs apart from these (`.config/nextest.toml`, group
/// `can0`).
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
    /// Answers as a drive does.
    Answers,
    /// Answers nothing from then on: it never reaches Run as far as the host can tell.
    Silent,
}

/// How control's attempt ended.
#[derive(Debug, PartialEq)]
enum Ended {
    Refused(Refusal),
    Enabled,
    /// Gave up; whether the Enable had been planned.
    Failed(EnableFailure, bool),
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

/// Run preflight and, if it passes, the enable sequence for drive 101 on `BUS`, playing control on the bus layer's
/// rings, against a sim drive answering with `uid` and doing `after` once preflight passes.
#[expect(
    clippy::unwrap_used,
    clippy::too_many_lines,
    reason = "test helper: one control loop, start to end"
)]
fn attempt(uid: Uid, after: After) -> Ended {
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
    let ended = std::thread::scope(|scope| {
        let _stop = Stop(&passed, &stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [SimDrive::new(Drive::new(id(101), Model::Rs03), uid, 5)];
            serve(BUS, &mut drives, &passed, &mut |_| {})?;
            if let After::Silent = after {
                drives[0].inject(Instant::now(), Fault::Silent).unwrap();
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
                epoch,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();

        let end = Instant::now() + Duration::from_secs(10);
        // A few ticks of empty batches first, so the sim is serving before the first request.
        let warm = Instant::now() + Duration::from_millis(100);
        let mut phase = None;
        let mut tag = 0;
        let ended = loop {
            let snap = newest(&mut snapshots, end);
            let now = epoch.ns(Instant::now());
            let view = *snap.drive(0).unwrap();
            let mut batch = batch_after(&snap, epoch);
            if Instant::now() < warm {
                assert!(commands.push(batch).is_ok());
                continue;
            }
            let current = phase
                .take()
                .unwrap_or_else(|| Phase::Preflight(Preflight::start(target, now)));
            let (next, ended) = match current {
                Phase::Preflight(mut preflight) => {
                    if let Ok(result) = results.pop() {
                        assert_eq!(result.tag, tag, "one request at a time");
                        preflight.answered(result.outcome, now);
                    }
                    match preflight.poll(&view, now) {
                        Step::Submit(kind) => {
                            tag += 1;
                            let request = SlowRequest { tag, slot: 0, kind };
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
                Phase::Handing(proof) if applied.load(Ordering::Acquire) => {
                    (Some(Phase::Enabling(Enabling::new(proof, now))), None)
                }
                Phase::Handing(proof) => (Some(Phase::Handing(proof)), None),
                Phase::Enabling(mut enabling) => match enabling.step(&view, snap.tick + 1, now) {
                    Next::Send(frame) => {
                        assert!(batch.set(0, frame));
                        (Some(Phase::Enabling(enabling)), None)
                    }
                    Next::Wait => (Some(Phase::Enabling(enabling)), None),
                    Next::Enabled => (None, Some(Ended::Enabled)),
                    Next::Failed(failure) => (
                        None,
                        Some(Ended::Failed(failure, enabling.enable_planned())),
                    ),
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
    while let Ok(newer) = snapshots.pop() {
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
    assert_eq!(attempt(UID, After::Answers), Ended::Enabled);
}

/// Guards: safety - `host.identity`: on a real socket, a drive answering get-ID with another UID than the skeleton's
/// is refused before anything is written (PLAN item 3, Scan and identity; item 6 Identity row).
#[test]
fn a_drive_with_another_uid_is_refused_on_vcan() {
    let other = Uid([9; 8]);
    let ended = attempt(other, After::Answers);
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
    let ended = attempt(UID, After::Silent);
    assert_eq!(
        ended,
        Ended::Failed(EnableFailure::NoRun { last: None }, true)
    );
    assert_eq!(EnableFailure::NoRun { last: None }.rule(), RuleId::HostMode);
}
