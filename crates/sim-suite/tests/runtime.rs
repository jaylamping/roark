//! The runtime end to end on `vcan` against `sim-drive`, with the real skeleton (`config/skeleton.yaml`): it starts a
//! bus thread per wired bus and the control thread on one schedule, never enables anything, routes the operator's stop
//! and clear to the right buses and limbs, and ends with every limb at rest and the session closed.
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{LimbState, RearmRefused, Snapshot};
use common::HZ;
use robstride::Uid;
use robstride::drive::{Command, command};
use runtime::{ClearRefused, Reply, Request, Runtime, RuntimeConfig, Scope};
use sim_drive::{SimDrive, ensure_vcan, serve};
use skeleton::{LimbName, Skeleton};
use socketcan::{CanFrame, CanSocket, EmbeddedFrame, Id, Socket};

const SKELETON: &str = "../../config/skeleton.yaml";

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

/// Every host command seen on `bus` until `stop`.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the monitor must open for the test to mean anything"
)]
fn watch(bus: &str, stop: &AtomicBool) -> Vec<Command> {
    let socket = CanSocket::open(bus).unwrap();
    socket.set_read_timeout(Duration::from_millis(5)).unwrap();
    let mut seen = Vec::new();
    while !stop.load(Ordering::Acquire) {
        if let Ok(CanFrame::Data(frame)) = socket.read_frame()
            && let Id::Extended(id) = frame.id()
            && let Ok(Some(host)) = command(id.as_raw(), frame.data())
        {
            seen.push(host.command);
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
        while let Ok(view) = runtime.views.pop() {
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

/// Guards: safety - the runtime started on the real skeleton enables nothing (no Enable, MIT, Set Zero, set-ID or
/// parameter write reaches any bus, before or after a stop and clear: PLAN item 2, the runtime never enables on its
/// own); the operator's stop reaches every limb on every bus, the clear only the limb it names, on its bus, and a clear
/// of a limb wired to no bus is refused; and the runtime ends with every limb at rest, its threads joined and the
/// session closed (PLAN item 3a: stop always accepted; item 6: a stop names its scope).
#[test]
#[expect(clippy::too_many_lines, reason = "one run, start to end")]
fn the_runtime_runs_the_skeleton_stops_and_clears_and_never_enables_on_vcan() {
    let skeleton = skeleton::load(Path::new(SKELETON)).unwrap();
    let plans = runtime::plan(&skeleton).unwrap();
    let names: Vec<String> = plans.iter().map(|p| p.name.clone()).collect();
    for name in &names {
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
            skeleton: SKELETON.into(),
            sessions: root.clone(),
            hz: HZ,
            operator: "sim-suite".to_owned(),
            git_revision: "test".to_owned(),
        })
        .unwrap();
        assert_eq!(runtime.plans(), plans.as_slice());
        let end = Instant::now() + Duration::from_secs(10);
        let mut newest = vec![None; plans.len()];

        // Running, every limb idle: nothing was enabled.
        assert!(
            until(&mut runtime, &mut newest, end, |_, s| s.tick >= 20
                && s.limbs().all(|(_, l)| l.state == LimbState::Idle)),
            "{newest:?}"
        );

        // The operator's stop reaches every limb on every bus.
        assert!(runtime.requests.push(Request::Stop(Scope::Robot)).is_ok());
        assert!(
            until(&mut runtime, &mut newest, end, |_, s| s.stopped()),
            "{newest:?}"
        );

        // A clear of the waist, wired to no bus, is refused.
        assert!(
            runtime
                .requests
                .push(Request::Clear {
                    tag: 1,
                    limb: LimbName::Waist
                })
                .is_ok()
        );
        assert_eq!(
            replies(&mut runtime, 1, end),
            [Reply {
                tag: 1,
                limb: LimbName::Waist,
                bus: None,
                outcome: Err(ClearRefused::Offline),
            }]
        );
        // A clear of the left arm re-arms it on its bus alone. A drive that never confirmed the stop (one whose
        // status waits for its MIT scales, say) must first be quiet past its timeout, so the operator asks again
        // until the bus takes it.
        let left = plans
            .iter()
            .position(|p| p.limb_index(LimbName::LeftArm).is_some())
            .unwrap();
        let mut tag = 1;
        loop {
            tag += 1;
            assert!(
                runtime
                    .requests
                    .push(Request::Clear {
                        tag,
                        limb: LimbName::LeftArm
                    })
                    .is_ok()
            );
            let got = replies(&mut runtime, 1, end);
            assert_eq!(got.len(), 1, "one reply per clear: {got:?}");
            let reply = got[0];
            assert_eq!(
                (reply.tag, reply.limb, reply.bus),
                (tag, LimbName::LeftArm, Some(left))
            );
            if reply.outcome.is_ok() {
                break;
            }
            assert!(
                matches!(
                    reply.outcome,
                    Err(ClearRefused::Bus(RearmRefused::DriveNotQuiet { .. }))
                ),
                "{reply:?}"
            );
        }
        assert!(
            until(&mut runtime, &mut newest, end, |bus, s| {
                s.limbs().all(|(i, l)| {
                    let cleared = bus == left && plans[bus].limbs[i] == LimbName::LeftArm;
                    if cleared {
                        l.state == LimbState::Idle && l.generation == 1
                    } else {
                        l.state == LimbState::Stopped && l.generation == 0
                    }
                })
            }),
            "{newest:?}"
        );
        let session = runtime.session().to_path_buf();

        // Ended, every bus at rest (the cleared limb idle, the others stopped), the session closed.
        let exit = runtime.stop().unwrap();
        assert!(exit.control.error.is_none(), "{:?}", exit.control);
        assert_eq!(exit.control.replies_dropped, 0);
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

    // Only the stop's frames went out: Disables and reporting off, to every drive of every wired bus.
    for (name, commands) in names.iter().zip(&seen) {
        assert!(
            commands
                .iter()
                .all(|c| matches!(c, Command::Disable | Command::Reporting(_))),
            "{name}: {commands:?}"
        );
        assert!(commands.contains(&Command::Disable), "{name}: {commands:?}");
    }
}
