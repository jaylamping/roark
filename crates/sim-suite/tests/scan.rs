//! A scan and a set-ID on `vcan` (PLAN.md item 3, Scan and identity): every ID probed in the slack, a drive outside the
//! bus's table found and given a new ID, against simulated drives; first the bus layer played as control would, then
//! through the runtime with its test robot (`bins/runtime/tests/skeleton.yaml`).
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusLinks, CommandBatch, LimbState, SlowKind, SlowOutcome, SlowRefusal, SlowRequest,
    Snapshot,
};
use common::{HZ, Shutdown, drive, id, info, interface, next_snapshot, soon, timing};
use robstride::{DeviceId, Drive, Model, Uid};
use runtime::{
    Answer, Enable, EnableRefused, IdentityAsk, IdentityDone, IdentityRefused, IdentityReply,
    IdentityRequest, Runtime, RuntimeConfig, Scope,
};
use sim_drive::{SimDrive, ensure_vcan, serve};
use skeleton::LimbName;
use telemetry::{EventKind, Recorder, Recording, Session};

const BUS: &str = "can0";

/// Plays control for one bus: an empty batch each tick, and slow requests asked one at a time.
struct Control<'a> {
    commands: rtrb::Producer<CommandBatch>,
    snapshots: rtrb::Consumer<Snapshot>,
    requests: rtrb::Producer<SlowRequest>,
    results: rtrb::Consumer<can::SlowResult>,
    epoch: &'a telemetry::Epoch,
    tag: u32,
    retries: u32,
}

impl Control<'_> {
    /// Ask `kind` and keep the bus fed until its result. A stall of this thread can leave control silent for a tick, or
    /// a loaded machine can leave a drain unemptied; such a refusal, or a probe's unsure window, is asked again, a few
    /// times at most in the whole run. A set-ID's unsure window is returned as it is.
    #[expect(
        clippy::unwrap_used,
        reason = "test helper: a bus that stops publishing fails the test"
    )]
    fn ask(&mut self, kind: SlowKind) -> SlowOutcome {
        let end = Instant::now() + Duration::from_secs(5);
        let period = 1_000_000_000 / HZ;
        self.tag += 1;
        let mut asked = false;
        loop {
            let mut snap = next_snapshot(&mut self.snapshots, end).unwrap();
            for _ in 0..self.snapshots.buffer().capacity() {
                let Ok(newer) = self.snapshots.pop() else {
                    break;
                };
                snap = newer;
            }
            let batch =
                CommandBatch::new(snap.tick + 1, self.epoch.ns(Instant::now()) + 3 * period);
            assert!(self.commands.push(batch).is_ok());
            if !asked {
                let request = SlowRequest {
                    tag: self.tag,
                    slot: 0,
                    kind,
                };
                assert!(self.requests.push(request).is_ok());
                asked = true;
            }
            if let Ok(result) = self.results.pop() {
                assert_eq!(result.tag, self.tag);
                // A set-ID is never sent twice: an unsure one is settled by the probes after it.
                let probe = matches!(kind, SlowKind::Probe(_));
                if (result.outcome == SlowOutcome::Refused(SlowRefusal::ControlSilent)
                    || (probe && result.outcome == SlowOutcome::Unsure))
                    && self.retries < 5
                {
                    self.retries += 1;
                    self.tag += 1;
                    asked = false;
                    continue;
                }
                return result.outcome;
            }
        }
    }
}

/// Guards: protocol - on `vcan`, a scan finds every drive answering on the bus, one in the bus's table and ones outside
/// it, two sharing an ID among them, and nothing at the other IDs; a set-ID moves a drive outside the table to a new ID,
/// where the next probe finds it, and its old ID is silent after (RS03 manual §4.1.1 type 0, §4.1.5 type 7; PLAN.md
/// item 3, Scan and identity; item 5: scan, then set IDs one drive at a time).
#[test]
fn a_scan_finds_every_drive_and_a_set_id_moves_one() {
    ensure_vcan(BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-scan-{}", std::process::id()));
    let (known, stray, first, second) = (Uid([1; 8]), Uid([2; 8]), Uid([3; 8]), Uid([4; 8]));
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = vec![
                SimDrive::new(Drive::new(id(101), Model::Rs03), known, 1),
                SimDrive::new(Drive::new(id(127), Model::Rs03), stray, 2),
                SimDrive::new(Drive::new(id(50), Model::Rs02), first, 3),
                SimDrive::new(Drive::new(id(50), Model::Rs02), second, 4),
            ];
            serve(BUS, &mut drives, &stop_sim, &mut |_| {})
        });
        let session = Session::start(&root, info(BUS), 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (commands_tx, commands) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, snapshots) = rtrb::RingBuffer::new(64);
        let (requests_tx, requests) = rtrb::RingBuffer::new(4);
        let (results_tx, results) = rtrb::RingBuffer::new(4);
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                // Only drive 101 is the bus's; the others are what a scan is for.
                drives: vec![drive(101, 0)],
                timing: timing(),
                interface: interface(),
            },
            BusLinks {
                commands,
                snapshots: snapshots_tx,
                recorder: buses.remove(0),
                requests,
                results: results_tx,
                orders: rtrb::RingBuffer::new(1).1,
                rearmed: rtrb::RingBuffer::new(1).0,
                epoch,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();
        let mut control = Control {
            commands: commands_tx,
            snapshots,
            requests: requests_tx,
            results,
            epoch: &epoch,
            tag: 0,
            retries: 0,
        };

        scan_and_set_id(&mut control, [known, stray, first, second]);

        exit.store(true, Ordering::Release);
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
    });
    let _ = std::fs::remove_dir_all(&root);
}

/// The scan and the set-ID, against drive 101 (`known`), a stray drive on 127 and two drives on 50.
fn scan_and_set_id(control: &mut Control<'_>, [known, stray, first, second]: [Uid; 4]) {
    // Until the simulated drives are up a probe may time out: wait for the bus's own drive first.
    let up = Instant::now() + Duration::from_secs(5);
    while control.ask(SlowKind::Probe(id(101))) == SlowOutcome::TimedOut {
        assert!(Instant::now() < up, "the simulated drives never answered");
    }

    let found: Vec<(u8, SlowOutcome)> = (1..=DeviceId::MAX)
        .map(|n| (n, control.ask(SlowKind::Probe(id(n)))))
        .filter(|(_, outcome)| *outcome != SlowOutcome::TimedOut)
        .collect();
    // The two drives on 50 answer in either order.
    let shared = |a, b| SlowOutcome::Found {
        uid: a,
        other: Some(b),
    };
    assert!(
        found.first() == Some(&(50, shared(first, second)))
            || found.first() == Some(&(50, shared(second, first))),
        "{found:?}"
    );
    assert_eq!(
        found.get(1..),
        Some(
            &[
                (
                    101,
                    SlowOutcome::Found {
                        uid: known,
                        other: None
                    }
                ),
                (
                    127,
                    SlowOutcome::Found {
                        uid: stray,
                        other: None
                    }
                ),
            ][..]
        )
    );

    let moved = SlowOutcome::Found {
        uid: stray,
        other: None,
    };
    // An unsure window on a loaded machine is settled by the probes that follow.
    let set = control.ask(SlowKind::SetId {
        old: id(127),
        new: id(11),
    });
    assert!(set == moved || set == SlowOutcome::Unsure, "{set:?}");
    assert_eq!(control.ask(SlowKind::Probe(id(11))), moved);
    assert_eq!(control.ask(SlowKind::Probe(id(127))), SlowOutcome::TimedOut);
}

/// The runtime's test robot, never the live skeleton (testing.md rule 3).
fn robot() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bins/runtime/tests/skeleton.yaml")
}

/// The UID the sims give drive `n`: the runtime test robot's.
const fn sim_uid(n: u8) -> Uid {
    Uid([b's', b'i', b'm', 0, n, 0, 0, 0])
}

/// The simulated drives the skeleton puts on `bus`, plus `extra`.
fn sims(skeleton: &skeleton::Skeleton, bus: &str, extra: &[(u8, Uid)]) -> Vec<SimDrive> {
    skeleton
        .limbs
        .iter()
        .flat_map(|limb| &limb.joints)
        .filter(|joint| joint.bus.as_ref().is_some_and(|b| b.as_str() == bus))
        .map(|joint| (joint.id.get(), joint.actuator, sim_uid(joint.id.get())))
        .chain(extra.iter().map(|(n, uid)| (*n, Model::Rs02, *uid)))
        .map(|(n, model, uid)| SimDrive::new(Drive::new(id(n), model), uid, u64::from(n)))
        .collect()
}

/// The answer to the scan or set-ID tagged `tag`, waiting until `end`.
fn identity_reply(runtime: &mut Runtime, tag: u64, end: Instant) -> Option<IdentityReply> {
    while Instant::now() < end {
        if let Ok(r) = runtime.identity_replies.pop() {
            assert_eq!(r.tag, tag, "{r:?}");
            return Some(r);
        }
        std::thread::yield_now();
    }
    None
}

/// Guards: safety - through the runtime on `vcan`: a scan of a bus lists every drive answering on it, the skeleton's and
/// ones it doesn't name, two sharing an ID among them, and no enable runs beside it; a set-ID moves a stray drive to a
/// free ID and is confirmed there; one from an ID nothing answers at, or onto an ID a drive holds, sends no type 7; and
/// one on a bus with a limb stopped is refused by the bus; each is an event in the session's log (PLAN item 3, Scan and identity: set-ID one drive at a time,
/// only while every limb on that bus is disabled; item 2: type 7 only with exactly one drive answering; item 3a
/// `scan(bus)`, `set_id(bus, old, new)`).
#[test]
#[expect(clippy::too_many_lines, reason = "one run, start to end")]
#[expect(clippy::panic, reason = "a test fails by panicking")]
fn the_runtime_scans_a_bus_and_sets_an_id_on_vcan() {
    let path = robot();
    let skeleton = skeleton::load(&path).unwrap();
    let names: Vec<&str> = skeleton.buses.iter().map(|b| b.name.as_str()).collect();
    for name in names.iter().copied() {
        ensure_vcan(name).unwrap();
    }
    let root = std::env::temp_dir().join(format!("sim-suite-runtime-scan-{}", std::process::id()));
    let (stray, first, second) = (Uid([7; 8]), Uid([8; 8]), Uid([9; 8]));
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sims: Vec<_> = names
            .iter()
            .map(|name| {
                let extra = if *name == BUS {
                    vec![(127, stray), (50, first), (50, second)]
                } else {
                    vec![]
                };
                let mut sim = sims(&skeleton, name, &extra);
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
        let bus = runtime
            .info()
            .plans
            .iter()
            .position(|p| p.name == BUS)
            .unwrap();
        // Running a few ticks first, so the sims are up before the first probe.
        let end = Instant::now() + Duration::from_secs(5);
        let mut ticks = 0;
        while ticks < 5 {
            assert!(Instant::now() < end, "the runtime never ran");
            if let Some(Ok(_)) = runtime.views.as_mut().map(rtrb::Consumer::pop) {
                ticks += 1;
            }
            std::thread::yield_now();
        }
        // The scan, and an enable asked once it has had a few passes to start: refused.
        let scan = IdentityRequest {
            tag: 1,
            bus,
            ask: IdentityAsk::Scan,
        };
        assert!(runtime.identity.push(scan).is_ok());
        let joints = runtime.joints(["arm_a_one"]).unwrap();
        let mut passes = 0;
        let end = Instant::now() + Duration::from_secs(5);
        while passes < 3 {
            assert!(Instant::now() < end, "the runtime stopped publishing");
            if let Some(Ok(v)) = runtime.views.as_mut().map(rtrb::Consumer::pop) {
                passes += usize::from(v.bus == bus);
            }
            std::thread::yield_now();
        }
        assert!(runtime.enables.push(Enable { tag: 2, joints }).is_ok());
        let end = Instant::now() + Duration::from_secs(10);
        let mut enable = None;
        while enable.is_none() && Instant::now() < end {
            enable = runtime.enable_replies.pop().ok();
        }
        assert_eq!(enable.map(|r| r.outcome), Some(Err(EnableRefused::Busy)));
        let reply = identity_reply(&mut runtime, 1, end).unwrap();
        let Ok(IdentityDone::Scanned(table)) = reply.outcome else {
            panic!("{reply:?}");
        };
        let heard: Vec<_> = table.heard().map(|(n, a)| (n.get(), a)).collect();
        let fifty = heard.iter().find(|(n, _)| *n == 50).map(|(_, a)| *a);
        assert!(
            fifty
                == Some(Answer::Several {
                    uid: first,
                    other: second
                })
                || fifty
                    == Some(Answer::Several {
                        uid: second,
                        other: first
                    }),
            "{heard:?}"
        );
        assert_eq!(
            heard
                .iter()
                .filter(|(n, _)| *n != 50)
                .copied()
                .collect::<Vec<_>>(),
            [
                (21, Answer::One(sim_uid(21))),
                (22, Answer::One(sim_uid(22))),
                (31, Answer::One(sim_uid(31))),
                (127, Answer::One(stray)),
            ]
        );

        // The stray moves to 30, and the IDs show it.
        let set = |old, new| IdentityAsk::SetId {
            old: id(old),
            new: id(new),
        };
        let outcome = |runtime: &mut Runtime, tag, what| {
            let request = IdentityRequest {
                tag,
                bus,
                ask: what,
            };
            assert!(runtime.identity.push(request).is_ok());
            let end = Instant::now() + Duration::from_secs(5);
            identity_reply(runtime, tag, end).unwrap().outcome
        };
        assert_eq!(
            outcome(&mut runtime, 3, set(127, 30)),
            Ok(IdentityDone::Moved { uid: stray })
        );
        assert_eq!(
            outcome(&mut runtime, 4, set(127, 30)),
            Err(IdentityRefused::NotOne(Answer::Silent))
        );
        assert_eq!(
            outcome(&mut runtime, 5, set(30, 21)),
            Err(IdentityRefused::Taken(Answer::One(sim_uid(21))))
        );
        let shared = outcome(&mut runtime, 6, set(50, 40));
        let several = |uid, other| Err(IdentityRefused::NotOne(Answer::Several { uid, other }));
        assert!(
            shared == several(first, second) || shared == several(second, first),
            "{shared:?}"
        );

        // A limb on the bus stopped: the bus refuses the first probe.
        runtime.stop(Scope::Limb(LimbName::Waist));
        let end = Instant::now() + Duration::from_secs(5);
        let mut stopped = false;
        while !stopped && Instant::now() < end {
            if let Some(Ok(v)) = runtime.views.as_mut().map(rtrb::Consumer::pop) {
                stopped =
                    v.bus == bus && v.snapshot.limbs().any(|(_, l)| l.state != LimbState::Idle);
            }
        }
        assert!(stopped);
        assert_eq!(
            outcome(&mut runtime, 7, set(30, 40)),
            Err(IdentityRefused::Bus(SlowRefusal::BusNotIdle))
        );

        let session = runtime.session().to_path_buf();
        let exit = runtime.end().unwrap();
        assert!(exit.control.error.is_none(), "{:?}", exit.control);
        assert_eq!(exit.control.replies_dropped, 0);
        // Every scan and set-ID is in the event log, with its bus, its tag and, refused, why.
        let events = common::events(&session);
        let of = |kind| {
            common::of_kind(&events, kind)
                .into_iter()
                .map(|e| (e.bus, e.tag, e.reason))
                .collect::<Vec<_>>()
        };
        let on_bus = |tag, reason| (Some(BUS), Some(tag), reason);
        assert_eq!(of(EventKind::ScanStarted), [on_bus(1, None)]);
        assert_eq!(of(EventKind::ScanFinished), [on_bus(1, None)]);
        assert_eq!(
            of(EventKind::SetIdStarted),
            [3, 4, 5, 6, 7].map(|tag| on_bus(tag, None))
        );
        assert_eq!(of(EventKind::SetIdSucceeded), [on_bus(3, None)]);
        assert_eq!(
            of(EventKind::SetIdRefused),
            [
                on_bus(4, Some("not_one_at_old_id")),
                on_bus(5, Some("new_id_taken")),
                on_bus(6, Some("not_one_at_old_id")),
                on_bus(7, Some("bus_refused")),
            ]
        );
        stop_sim.store(true, Ordering::Release);
        for sim in sims {
            sim.join().unwrap().unwrap();
        }
    });
    let _ = std::fs::remove_dir_all(&root);
}
