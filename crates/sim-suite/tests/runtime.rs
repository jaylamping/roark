//! The runtime end to end on `vcan` against `sim-drive`, with its test robot (`bins/runtime/tests/skeleton.yaml`: five
//! limbs, one over two buses, one offline, the left arm commissioned): it starts a bus thread per wired bus and the
//! control thread on one schedule, enables nothing on its own, routes the operator's stops and clears to the right buses
//! and limbs, enables and holds exactly the joints an operator's enable names once their preflights pass, and ends with
//! every limb at rest and the session closed.
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{LimbState, Snapshot};
use common::HZ;
use robstride::drive::{Command, HostFrame, command};
use robstride::{Mode, Param, ParamValue, Reporting, RunMode, StatusFault, StatusFaults, Uid};
use runtime::{
    Clear, ClearRefused, Enable, EnableRefused, EnableReply, Reply, Runtime, RuntimeConfig, Scope,
};
use safety::EnableFailure;
use sim_drive::{Fault, SimDrive, Trigger, ensure_vcan, serve};
use skeleton::{LimbName, Skeleton};
use socketcan::{CanFrame, CanSocket, EmbeddedFrame, Id, Socket};

/// The runtime's test robot, never the live skeleton (testing.md rule 3).
/// How late drive 12 answers in the enable test's late stage: past the 50 ms an Enable has to reach Run
/// (`can::ENABLE_TO_RUN_NS`), with room left in the stop's wait for its Disable's answer.
const LATE: Duration = Duration::from_millis(60);

fn skeleton_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bins/runtime/tests/skeleton.yaml")
}

/// The simulated drives the skeleton puts on `bus`.
fn drives(skeleton: &Skeleton, bus: &str) -> Vec<SimDrive> {
    skeleton
        .limbs
        .iter()
        .flat_map(|limb| &limb.joints)
        .filter(|joint| joint.bus.as_ref().is_some_and(|b| b.as_str() == bus))
        .map(|joint| {
            let id = joint.id.get();
            SimDrive::new(
                robstride::Drive::new(joint.id, joint.actuator),
                Uid([b's', b'i', b'm', 0, id, 0, 0, 0]),
                u64::from(id),
            )
        })
        .collect()
}

/// Every host frame seen on `bus` until `stop`, with when it was read.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the monitor must open for the test to mean anything"
)]
fn watch(bus: &str, stop: &AtomicBool) -> Vec<(Instant, HostFrame)> {
    let socket = CanSocket::open(bus).unwrap();
    socket.set_read_timeout(Duration::from_millis(5)).unwrap();
    let mut seen = Vec::new();
    while !stop.load(Ordering::Acquire) {
        if let Ok(CanFrame::Data(frame)) = socket.read_frame()
            && let Id::Extended(id) = frame.id()
            && let Ok(Some(host)) = command(id.as_raw(), frame.data())
        {
            seen.push((Instant::now(), host));
        }
    }
    seen
}

/// Each bus's newest snapshot, until `done` holds for every bus or `end` passes.
fn until(
    runtime: &mut Runtime,
    newest: &mut [Option<Snapshot>],
    end: Instant,
    done: impl Fn(usize, &Snapshot) -> bool,
) -> bool {
    while Instant::now() < end {
        while let Some(Ok(view)) = runtime.views.as_mut().map(rtrb::Consumer::pop) {
            if let Some(slot) = newest.get_mut(view.bus) {
                *slot = Some(view.snapshot);
            }
        }
        if newest
            .iter()
            .enumerate()
            .all(|(bus, s)| s.as_ref().is_some_and(|s| done(bus, s)))
        {
            return true;
        }
        std::thread::yield_now();
    }
    false
}

/// Sets both flags when dropped, so a failed assert still ends the sims and watchers and the scope can join them.
struct Ends<'a>(&'a AtomicBool, &'a AtomicBool);

impl Drop for Ends<'_> {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
        self.1.store(true, Ordering::Release);
    }
}

/// The replies that have come in, until `n` have or `end` passes.
fn replies(runtime: &mut Runtime, n: usize, end: Instant) -> Vec<Reply> {
    let mut got = Vec::new();
    while got.len() < n && Instant::now() < end {
        if let Ok(r) = runtime.replies.pop() {
            got.push(r);
        }
        std::thread::yield_now();
    }
    got
}

/// Guards: safety - the runtime enables nothing (no Enable, MIT, Set Zero, set-ID or parameter write reaches any bus,
/// before or after stops and clears: PLAN item 3, the runtime never enables on its own); the operator's robot stop
/// reaches every limb on every bus, a limb's stop and clear reach that limb on every bus it is on and nothing else, and a
/// clear of a limb on no bus is refused (PLAN item 3a: stop always accepted; item 6: a stop names its scope); and the
/// runtime ends with every limb at rest, its threads joined, every batch taken and the session closed.
#[test]
#[expect(clippy::too_many_lines, reason = "one run, start to end")]
fn the_runtime_runs_stops_and_clears_every_bus_and_never_enables_on_vcan() {
    let path = skeleton_path();
    let skeleton = skeleton::load(&path).unwrap();
    // Every bus the skeleton names, so a bus added to it is checked before anything opens it.
    let names: Vec<&str> = skeleton.buses.iter().map(|b| b.name.as_str()).collect();
    for name in names.iter().copied() {
        ensure_vcan(name).unwrap();
    }
    let root = std::env::temp_dir().join(format!("sim-suite-runtime-{}", std::process::id()));
    let stop_sim = AtomicBool::new(false);
    let stop_watch = AtomicBool::new(false);
    let seen = std::thread::scope(|scope| {
        let _ends = Ends(&stop_sim, &stop_watch);
        let watchers: Vec<_> = names
            .iter()
            .map(|name| scope.spawn(|| watch(name, &stop_watch)))
            .collect();
        let sims: Vec<_> = names
            .iter()
            .map(|name| {
                let mut sim = drives(&skeleton, name);
                let stop = &stop_sim;
                scope.spawn(move || serve(name, &mut sim, stop, &mut |_| {}))
            })
            .collect();

        let mut runtime = Runtime::start(&RuntimeConfig {
            skeleton: path.clone(),
            sessions: root.clone(),
            hz: HZ,
            operator: "sim-suite".to_owned(),
            git_revision: "test".to_owned(),
            views: true,
        })
        .unwrap();
        let plans = runtime.info().plans.clone();
        assert_eq!(
            plans.iter().map(|p| p.name.as_str()).collect::<Vec<_>>(),
            names
        );
        let bus_of = |limb| {
            plans
                .iter()
                .enumerate()
                .filter_map(|(bus, p)| Some((bus, p.limb_index(limb)?)))
                .collect::<Vec<_>>()
        };
        // The right arm is on both buses.
        let right = bus_of(LimbName::RightArm);
        assert_eq!(right.len(), 2);
        let is_right = |bus: usize, limb: usize| right.contains(&(bus, limb));
        let end = Instant::now() + Duration::from_secs(10);
        let mut newest = vec![None; plans.len()];

        // Running, every limb idle: nothing was enabled.
        assert!(
            until(&mut runtime, &mut newest, end, |_, s| s.tick >= 20
                && s.limbs().all(|(_, l)| l.state == LimbState::Idle)),
            "{newest:?}"
        );

        // The operator's stop reaches every limb on every bus.
        runtime.stop(Scope::Robot);
        assert!(
            until(&mut runtime, &mut newest, end, |_, s| s.stopped()),
            "{newest:?}"
        );

        // A clear of the left leg, whose only joint is on no bus, is refused.
        assert!(
            runtime
                .clears
                .push(Clear {
                    tag: 1,
                    limb: LimbName::LeftLeg
                })
                .is_ok()
        );
        assert_eq!(
            replies(&mut runtime, 1, end),
            [Reply {
                tag: 1,
                limb: LimbName::LeftLeg,
                bus: None,
                outcome: Err(ClearRefused::Offline),
            }]
        );
        // A clear of the right arm re-arms it on both its buses, one reply each, and nothing else.
        assert!(
            runtime
                .clears
                .push(Clear {
                    tag: 2,
                    limb: LimbName::RightArm
                })
                .is_ok()
        );
        let mut got = replies(&mut runtime, 2, end);
        got.sort_by_key(|r| r.bus);
        assert_eq!(
            got,
            [0, 1].map(|bus| Reply {
                tag: 2,
                limb: LimbName::RightArm,
                bus: Some(bus),
                outcome: Ok(()),
            })
        );
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| {
                s.limbs().all(|(i, l)| {
                    if is_right(bus, i) {
                        l.state == LimbState::Idle && l.generation == 1
                    } else {
                        l.state == LimbState::Stopped && l.generation == 0
                    }
                })
            }),
            "{newest:?}"
        );
        // The right arm's own stop reaches it on both buses again; the others stay as they were.
        runtime.stop(Scope::Limb(LimbName::RightArm));
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| {
                s.limbs().all(|(i, l)| {
                    l.state == LimbState::Stopped && l.generation == u32::from(is_right(bus, i))
                })
            }),
            "{newest:?}"
        );
        let session = runtime.session().to_path_buf();
        assert!(!runtime.finished().load(Ordering::Acquire));

        // Ended, every bus at rest, every batch taken, the session closed.
        let exit = runtime.end().unwrap();
        assert!(exit.control.error.is_none(), "{:?}", exit.control);
        assert_eq!(exit.control.bus_ended, None, "{:?}", exit.control);
        assert_eq!(exit.control.replies_dropped, 0);
        assert_eq!(exit.control.batches_dropped, 0);
        assert_eq!(exit.buses.len(), plans.len());
        for bus in &exit.buses {
            assert!(bus.error.is_none(), "{bus:?}");
            assert!(
                bus.last.is_some_and(|s| s
                    .limbs()
                    .all(|(_, l)| matches!(l.state, LimbState::Idle | LimbState::Stopped))),
                "{bus:?}"
            );
        }
        assert_eq!(exit.recording.buses.len(), plans.len());
        assert!(session.join("session.json").is_file());

        stop_sim.store(true, Ordering::Release);
        for sim in sims {
            sim.join().unwrap().unwrap();
        }
        stop_watch.store(true, Ordering::Release);
        watchers
            .into_iter()
            .map(|w| w.join().unwrap())
            .collect::<Vec<_>>()
    });
    let _ = std::fs::remove_dir_all(&root);

    // Only the stops' frames went out: Disables and reporting off, to every drive of every bus.
    for (name, frames) in names.iter().zip(&seen) {
        let commands: Vec<Command> = frames.iter().map(|(_, f)| f.command).collect();
        assert!(
            commands
                .iter()
                .all(|c| matches!(c, Command::Disable | Command::Reporting(Reporting::Off))),
            "{name}: {commands:?}"
        );
        assert!(commands.contains(&Command::Disable), "{name}: {commands:?}");
    }
}

/// The answer to the enable tagged `tag`, waiting until `end`.
fn enable_reply(runtime: &mut Runtime, tag: u64, end: Instant) -> Option<EnableReply> {
    while Instant::now() < end {
        if let Ok(r) = runtime.enable_replies.pop() {
            assert_eq!(r.tag, tag, "{r:?}");
            return Some(r);
        }
        std::thread::yield_now();
    }
    None
}

/// Sets every flag when dropped, so a failed assert still ends the sims and watchers and the scope can join them.
struct Flags<'a>(&'a [&'a AtomicBool]);

impl Drop for Flags<'_> {
    fn drop(&mut self) {
        for flag in self.0 {
            flag.store(true, Ordering::Release);
        }
    }
}

/// Guards: safety - an operator's enable reaches exactly the joints it names, and only once every one's preflight has
/// passed: one naming a joint with no bus is refused before anything is sent; the left arm's two commissioned
/// joints pass preflight against `sim-drive`, get the enable sequence, go Active and are held with MIT commands; a stop
/// ends the hold, a clear and a new enable run preflight again and enable again; a drive that answers its Enable too
/// late fails the enable with the limb stopped, since the Enable may have gone; a limb-mate the host never enabled,
/// put in Run by something else, stops the whole limb (PLAN item 6 `host.mode`); a fault from a held drive stops its
/// limb (`host.fault`); the waist's joint, every fact and cap null, enables at its model's commissioning caps (PLAN item
/// 1); and the right arm, never named, gets only stops (PLAN item 3: the runtime never enables on its own; item 6:
/// enable is per joint set and runs preflight first).
#[test]
#[expect(clippy::too_many_lines, reason = "one run, start to end")]
fn an_enable_preflights_enables_and_holds_only_the_named_joints_on_vcan() {
    let path = skeleton_path();
    let skeleton = skeleton::load(&path).unwrap();
    // Every bus the skeleton names, so a bus added to it is checked before anything opens it.
    let names: Vec<&str> = skeleton.buses.iter().map(|b| b.name.as_str()).collect();
    for name in names.iter().copied() {
        ensure_vcan(name).unwrap();
    }
    let root =
        std::env::temp_dir().join(format!("sim-suite-runtime-enable-{}", std::process::id()));
    // The can1 sim's stages: it serves until each flag, then puts the next fault on the bus.
    let to_prompt = AtomicBool::new(false);
    let prompt_on = AtomicBool::new(false);
    let to_mode = AtomicBool::new(false);
    let to_fault = AtomicBool::new(false);
    let stop_sim = AtomicBool::new(false);
    let stop_watch = AtomicBool::new(false);
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let (seen, first_enable) = std::thread::scope(|scope| {
        let flags = [
            &to_prompt,
            &prompt_on,
            &to_mode,
            &to_fault,
            &stop_sim,
            &stop_watch,
        ];
        let _flags = Flags(&flags);
        let watchers: Vec<_> = names
            .iter()
            .map(|name| scope.spawn(|| watch(name, &stop_watch)))
            .collect();
        let can0 = scope.spawn(|| {
            let mut sim = drives(&skeleton, "can0");
            serve("can0", &mut sim, &stop_sim, &mut |_| {})
        });
        let can1 = scope.spawn(|| {
            // The left arm's drives 11 and 12 come first on can1, in skeleton order.
            let mut sim = drives(&skeleton, "can1");
            // From its third Enable, drive 12 answers later than an Enable must be answered; then promptly again.
            sim[1]
                .schedule(Trigger::OnEnable(3), Fault::Late(LATE))
                .unwrap();
            serve("can1", &mut sim, &to_prompt, &mut |_| {})?;
            sim[1]
                .inject(Instant::now(), Fault::Late(Duration::ZERO))
                .unwrap();
            prompt_on.store(true, Ordering::Release);
            serve("can1", &mut sim, &to_mode, &mut |_| {})?;
            // Drive 12 put in Run by another controller's Enable, answering it on the bus.
            let now = Instant::now();
            sim[1].inject(now, Fault::Mode(Mode::Run)).unwrap();
            sim[1].receive(
                now,
                HostFrame {
                    target: common::id(12),
                    command: Command::Enable,
                },
            );
            serve("can1", &mut sim, &to_fault, &mut |_| {})?;
            sim[0]
                .inject(Instant::now(), Fault::FaultBits(over))
                .unwrap();
            serve("can1", &mut sim, &stop_sim, &mut |_| {})
        });

        let mut runtime = Runtime::start(&RuntimeConfig {
            skeleton: path.clone(),
            sessions: root.clone(),
            hz: HZ,
            operator: "sim-suite".to_owned(),
            git_revision: "test".to_owned(),
            views: true,
        })
        .unwrap();
        let plans = runtime.info().plans.clone();
        let left = plans[1].limb_index(LimbName::LeftArm).unwrap();
        assert_eq!(plans[0].limb_index(LimbName::LeftArm), None);
        let left_is =
            |s: &Snapshot, state: LimbState| s.limb(left).is_some_and(|l| l.state == state);
        let end = Instant::now() + Duration::from_secs(20);
        let mut newest = vec![None; plans.len()];
        assert!(
            until(&mut runtime, &mut newest, end, |_, s| s.tick >= 20),
            "{newest:?}"
        );
        let enable = |runtime: &mut Runtime, tag, names: &[&str]| {
            let joints = runtime.joints(names.iter().copied()).unwrap();
            assert!(runtime.enables.push(Enable { tag, joints }).is_ok());
            enable_reply(runtime, tag, end)
        };
        let both = ["arm_a_one", "arm_a_two"];

        // A joint with no bus refuses the whole enable before anything is sent: the left arm stays idle.
        let leg = runtime
            .joints(["leg_a_one"])
            .unwrap()
            .iter()
            .next()
            .unwrap();
        assert!(matches!(
            enable(&mut runtime, 1, &["arm_a_one", "leg_a_one"]),
            Some(EnableReply { outcome: Err(EnableRefused::Preflight { joint, .. }), .. }) if joint == leg
        ));
        assert!(
            newest[1]
                .as_ref()
                .is_some_and(|s| left_is(s, LimbState::Idle))
        );

        // The left arm passes preflight, enables and is held.
        let first_enable = Instant::now();
        assert_eq!(
            enable(&mut runtime, 2, &both),
            Some(EnableReply {
                tag: 2,
                outcome: Ok(())
            })
        );
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || left_is(s, LimbState::Active)),
            "{newest:?}"
        );
        // Enabling a joint already enabled is refused.
        let a_one = runtime
            .joints(["arm_a_one"])
            .unwrap()
            .iter()
            .next()
            .unwrap();
        assert_eq!(
            enable(&mut runtime, 3, &["arm_a_one"]),
            Some(EnableReply {
                tag: 3,
                outcome: Err(EnableRefused::AlreadyEnabled { joint: a_one })
            })
        );

        // The operator's stop ends the hold; a clear and a new enable run preflight again.
        let clear = |runtime: &mut Runtime, tag| {
            assert!(
                runtime
                    .clears
                    .push(Clear {
                        tag,
                        limb: LimbName::LeftArm
                    })
                    .is_ok()
            );
            assert_eq!(
                replies(runtime, 1, end),
                [Reply {
                    tag,
                    limb: LimbName::LeftArm,
                    bus: Some(1),
                    outcome: Ok(())
                }]
            );
        };
        runtime.stop(Scope::Limb(LimbName::LeftArm));
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || left_is(s, LimbState::Stopped)),
            "{newest:?}"
        );
        clear(&mut runtime, 4);
        assert_eq!(
            enable(&mut runtime, 5, &both),
            Some(EnableReply {
                tag: 5,
                outcome: Ok(())
            })
        );

        // A drive that doesn't answer its Enable in time: the Enable may have gone, so the enable fails with the limb
        // stopped.
        runtime.stop(Scope::Limb(LimbName::LeftArm));
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || left_is(s, LimbState::Stopped)),
            "{newest:?}"
        );
        clear(&mut runtime, 6);
        let a_two = runtime
            .joints(["arm_a_two"])
            .unwrap()
            .iter()
            .next()
            .unwrap();
        let late = enable(&mut runtime, 7, &["arm_a_two"]);
        assert!(
            matches!(
                late,
                Some(EnableReply {
                    outcome: Err(EnableRefused::Sequence {
                        joint,
                        failure: EnableFailure::NoRun { .. },
                        stopped: true,
                    }),
                    ..
                }) if joint == a_two
            ),
            "{late:?}"
        );
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || left_is(s, LimbState::Stopped)),
            "{newest:?}"
        );
        to_prompt.store(true, Ordering::Release);
        while !prompt_on.load(Ordering::Acquire) {
            assert!(Instant::now() < end, "drive 12 never made prompt");
            std::thread::yield_now();
        }

        // host.mode: only drive 11 enabled, then drive 12 put in Run by something else stops the whole left arm.
        clear(&mut runtime, 8);
        assert_eq!(
            enable(&mut runtime, 9, &["arm_a_one"]),
            Some(EnableReply {
                tag: 9,
                outcome: Ok(())
            })
        );
        to_mode.store(true, Ordering::Release);
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || left_is(s, LimbState::Stopped)),
            "{newest:?}"
        );

        // host.fault: drive 11 enabled and held, then faulted, stops the left arm on the bus.
        clear(&mut runtime, 10);
        assert_eq!(
            enable(&mut runtime, 11, &["arm_a_one"]),
            Some(EnableReply {
                tag: 11,
                outcome: Ok(())
            })
        );
        to_fault.store(true, Ordering::Release);
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || s.limb(left).is_some_and(|l| l.state != LimbState::Active
                    && l.stop
                        == Some(can::StopReason::DriveFault { slot: 0 }))),
            "{newest:?}"
        );
        // Control drops the hold in the pass that hands over that view, after handing it over: a view of a later tick
        // shows that pass done before the run ends.
        let fault_tick = newest[1].as_ref().map_or(0, |s| s.tick);
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| bus == 0
                || s.tick > fault_tick),
            "{newest:?}"
        );

        // An uncommissioned joint (every fact and cap null) enables, at its model's commissioning caps.
        assert_eq!(
            enable(&mut runtime, 12, &["waist_one"]),
            Some(EnableReply {
                tag: 12,
                outcome: Ok(())
            })
        );

        let exit = runtime.end().unwrap();
        assert!(exit.control.error.is_none(), "{:?}", exit.control);
        assert_eq!(exit.control.bus_ended, None, "{:?}", exit.control);
        assert_eq!(exit.control.replies_dropped, 0);
        assert_eq!(exit.control.batches_dropped, 0);
        assert_eq!(exit.control.stray_results, 0);
        assert_eq!(exit.control.mode_stops, 1, "{:?}", exit.control);
        // Two joints after the first stop, two after the second, one after host.mode, one after host.fault.
        assert_eq!(exit.control.holds_ended, 6, "{:?}", exit.control);
        for bus in &exit.buses {
            assert!(bus.error.is_none(), "{bus:?}");
        }

        stop_sim.store(true, Ordering::Release);
        can0.join().unwrap().unwrap();
        can1.join().unwrap().unwrap();
        stop_watch.store(true, Ordering::Release);
        let seen = watchers
            .into_iter()
            .map(|w| w.join().unwrap())
            .collect::<Vec<_>>();
        (seen, first_enable)
    });
    let _ = std::fs::remove_dir_all(&root);

    // The right arm was never named, on can0 or can1: only the end's stops reached it.
    let only_stops =
        |c: &Command| matches!(c, Command::Disable | Command::Reporting(Reporting::Off));
    for id in [21, 22] {
        assert!(
            seen[0]
                .iter()
                .filter(|(_, f)| f.target == common::id(id))
                .all(|(_, f)| only_stops(&f.command)),
            "{:?}",
            seen[0]
        );
    }
    // The waist's drive (uncommissioned) got the caps it is enabled at, written as preflight writes any cap.
    let joint = skeleton
        .limbs
        .iter()
        .flat_map(|l| &l.joints)
        .find(|j| j.id == common::id(31))
        .unwrap();
    let caps = joint.caps();
    let waist = robstride::Drive::new(joint.id, joint.actuator);
    let expected = [
        robstride::Write::limit_torque(waist, caps.torque).unwrap(),
        robstride::Write::limit_cur(waist, caps.current).unwrap(),
        robstride::Write::limit_spd(waist, caps.speed).unwrap(),
    ]
    .map(|w| w.value());
    let written: Vec<ParamValue> = seen[0]
        .iter()
        .filter(|(_, f)| f.target == common::id(31))
        .filter_map(|(_, f)| match f.command {
            Command::ParamWrite {
                param: Param::LimitTorque | Param::LimitCur | Param::LimitSpd,
                value,
            } => Some(value),
            _ => None,
        })
        .collect();
    assert_eq!(written, expected);
    let to = |id: u8| -> Vec<(Instant, Command)> {
        seen[1]
            .iter()
            .filter(|(_, f)| f.target == common::id(id))
            .map(|(at, f)| (*at, f.command))
            .collect()
    };
    let right = to(23);
    assert!(
        !right.is_empty() && right.iter().all(|(_, c)| only_stops(c)),
        "{right:?}"
    );
    for id in [11, 12] {
        let frames = to(id);
        // The refused enable sent nothing to the left arm: its first frame came after the enable that passed.
        assert!(
            frames.iter().all(|(at, _)| *at >= first_enable),
            "drive {id}: {frames:?}"
        );
        // The first enable's sequence, in PLAN item 2's order: active reporting off, Enable, `run_mode` = MIT, then
        // the hold's MIT commands.
        let commands: Vec<Command> = frames.iter().map(|(_, c)| *c).collect();
        let first = |want: &dyn Fn(&Command) -> bool| commands.iter().position(want);
        let enable = first(&|c| *c == Command::Enable).unwrap();
        let mode = first(&|c| {
            matches!(
                c,
                Command::ParamWrite {
                    param: Param::RunMode,
                    value: ParamValue::RunMode(RunMode::Mit)
                }
            )
        })
        .unwrap();
        let mit = first(&|c| matches!(c, Command::Mit(_))).unwrap();
        let off = commands[..enable]
            .iter()
            .rposition(|c| *c == Command::Reporting(Reporting::Off));
        assert!(
            off.is_some() && enable < mode && mode < mit,
            "drive {id}: {commands:?}"
        );
        // Held with zero gains and zero torque (to the codes' resolution).
        let model = robstride::Model::Rs03;
        for c in &commands {
            if let Command::Mit(codes) = c {
                let held = codes.command(model).unwrap();
                let (kp, kd, torque) = (held.kp.get(), held.kd.get(), held.torque.get());
                assert!(
                    kp == 0.0 && kd == 0.0 && torque.abs() < 0.01,
                    "drive {id}: {held:?}"
                );
            }
        }
    }
    // Drive 12 was sent an Enable by the first two enables and the late one only; drive 11 by the four it was named in.
    assert_eq!(
        to(11).iter().filter(|(_, c)| *c == Command::Enable).count(),
        4
    );
    assert_eq!(
        to(12).iter().filter(|(_, c)| *c == Command::Enable).count(),
        3
    );
}
