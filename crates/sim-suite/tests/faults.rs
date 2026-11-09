//! Faults injected into `sim-drive` on `vcan`, caught by the bus layer on a real socket (PLAN item 4 Done when: each
//! stop rule proven with its trigger injected on `vcan`).
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusConfig, BusLinks, CommandBatch, LimbState, Snapshot, Spawned, StopReason};
use common::{HZ, Shutdown, drive, hold, id, info, limbs, next_snapshot, soon, timing};
use robstride::{Drive, Frame, Mode, Model, StatusFault, StatusFaults, Uid, Write, encode};
use sim_drive::{Fault, Injected, SimDrive, Trigger, ensure_vcan, serve};
use telemetry::{BusRecorder, Epoch, Recorder, Recording, Session};

/// Shared with the slow-request test and every test here, which nextest runs one at a time (`.config/nextest.toml`,
/// group `can0`).
const FAULT_BUS: &str = "can0";
/// The MIT command drive 101 faults on: well into the hold.
const FAULT_ON_MIT: u32 = 20;

/// The bus thread on `FAULT_BUS` with drive 101 in limb 0 and drive 102 in limb 1, and control's two rings.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the bus must start for the test to mean anything"
)]
fn start_bus(
    epoch: Epoch,
    recorder: BusRecorder,
    exit: &Arc<AtomicBool>,
) -> (
    Spawned,
    rtrb::Producer<CommandBatch>,
    rtrb::Consumer<Snapshot>,
) {
    let (commands_tx, commands) = rtrb::RingBuffer::new(4);
    let (snapshots_tx, snapshots) = rtrb::RingBuffer::new(64);
    let bus = can::spawn(
        BusConfig {
            name: FAULT_BUS.to_owned(),
            drives: vec![drive(101, 0), drive(102, 1)],
            timing: timing(),
        },
        BusLinks {
            commands,
            snapshots: snapshots_tx,
            recorder,
            requests: rtrb::RingBuffer::new(1).1,
            results: rtrb::RingBuffer::new(1).0,
            epoch,
            start: soon(),
            exit: Arc::clone(exit),
        },
    )
    .unwrap();
    (bus, commands_tx, snapshots)
}

/// Control's batch for the tick after `snap`, good for three periods.
fn send(
    commands: &mut rtrb::Producer<CommandBatch>,
    epoch: Epoch,
    snap: &Snapshot,
    frames: [Option<Frame>; 2],
) {
    let period = 1_000_000_000 / HZ;
    let mut batch = CommandBatch::new(snap.tick + 1, epoch.ns(Instant::now()) + 3 * period);
    for (slot, frame) in frames.into_iter().enumerate() {
        if let Some(frame) = frame {
            assert!(batch.set(slot, frame));
        }
    }
    assert!(commands.push(batch).is_ok());
}

/// Send Enables to both drives until both report Run; the last snapshot.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the bus publishes until the deadline"
)]
fn enable_both(
    send: &mut impl FnMut(&Snapshot, [Option<Frame>; 2]),
    snapshots: &mut rtrb::Consumer<Snapshot>,
    end: Instant,
) -> Snapshot {
    let mut snap = next_snapshot(snapshots, end).unwrap();
    while !snap.drives().all(|d| {
        d.observed
            .is_some_and(|o| o.status.header.mode == Mode::Run)
    }) {
        send(
            &snap,
            [Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
        );
        snap = next_snapshot(snapshots, end).unwrap();
    }
    snap
}

/// Guards: safety - a fault injected into one drive on `vcan` is caught before the next send: within one tick of the
/// bus thread reading it, that drive's limb is stopping with `DriveFault` and its Disable sent, control's next frame to
/// it is refused, and the bus's other limb keeps getting commands and answering; the injection is reported as it
/// fires (PLAN item 6 Faults row; logging.md section 3: injected faults recorded).
#[test]
fn a_fault_injected_on_vcan_stops_only_its_limb() {
    ensure_vcan(FAULT_BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-faults-{}", std::process::id()));
    let over: StatusFaults = [StatusFault::Overcurrent].into_iter().collect();
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    let (mut injected_tx, mut injected) = rtrb::RingBuffer::<Injected>::new(4);
    std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut faulty = SimDrive::new(Drive::new(id(101), Model::Rs03), Uid([1; 8]), 21);
            faulty
                .schedule(Trigger::OnMit(FAULT_ON_MIT), Fault::FaultBits(over))
                .unwrap();
            let mut drives = [
                faulty,
                SimDrive::new(Drive::new(id(102), Model::Rs03), Uid([2; 8]), 22),
            ];
            serve(FAULT_BUS, &mut drives, &stop_sim, &mut |i| {
                assert!(injected_tx.push(i).is_ok(), "the injection ring is full");
            })
        });
        let session = Session::start(&root, info(FAULT_BUS), 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (bus, mut commands, mut snapshots) = start_bus(epoch, buses.remove(0), &exit);
        let mut send = |snap: &Snapshot, frames| send(&mut commands, epoch, snap, frames);

        // Play control: enable both until both run, then hold both, whatever the snapshots say.
        let end = Instant::now() + Duration::from_secs(10);
        let mut snap = enable_both(&mut send, &mut snapshots, end);
        // Hold until the bus thread has read the fault.
        let mut seen = None;
        let mut stopped = None;
        while stopped.is_none() {
            send(&snap, [Some(hold(101)), Some(hold(102))]);
            snap = next_snapshot(&mut snapshots, end).unwrap();
            let faulted = snap.drive(0).is_some_and(|d| d.fault_seen);
            if faulted && seen.is_none() {
                seen = Some(snap.tick);
            }
            if snap.limb(0).is_some_and(|l| l.state != LimbState::Active) {
                stopped = Some((snap.tick, snap.drive(0).map(|d| d.stop)));
            }
            if seen.is_none() {
                assert_eq!(
                    limbs(&snap),
                    [(LimbState::Active, None), (LimbState::Active, None)],
                    "{snap:?}"
                );
            }
        }
        let (seen, (stopped, outcome)) = (seen.unwrap(), stopped.unwrap());
        // The Disable went out in the tick that stopped the limb.
        let disabled = [can::StopOutcome::Sent, can::StopOutcome::Confirmed];
        assert!(
            outcome.is_some_and(|o| disabled.contains(&o)),
            "{outcome:?}"
        );
        assert!(
            stopped <= seen + 1,
            "read at tick {seen}, stopped at {stopped}"
        );
        assert!(
            matches!(
                limbs(&snap)[0],
                (
                    LimbState::Stopping { .. },
                    Some(StopReason::DriveFault { slot: 0 })
                )
            ),
            "{snap:?}"
        );
        // Control learns of the stop only now, so each of its next frames to drive 101 is refused; limb 1 runs on.
        let refused_before = snap.counters.refused_frames;
        for _ in 0..5 {
            send(&snap, [Some(hold(101)), Some(hold(102))]);
            snap = next_snapshot(&mut snapshots, end).unwrap();
            assert_eq!(limbs(&snap)[1], (LimbState::Active, None), "{snap:?}");
            assert!(snap.drive(1).is_some_and(|d| d.answered), "{snap:?}");
        }
        assert_eq!(
            snap.counters.refused_frames - refused_before,
            5,
            "{:?}",
            snap.counters
        );
        // The drive answered its Disable in Reset five ticks ago.
        assert_eq!(
            snap.drive(0).map(|d| d.stop),
            Some(can::StopOutcome::Confirmed),
            "{snap:?}"
        );

        let fired: Vec<_> = std::iter::from_fn(|| injected.pop().ok())
            .map(|i| (i.device, i.fault))
            .collect();
        assert_eq!(fired, [(id(101), Fault::FaultBits(over))]);

        exit.store(true, Ordering::Release);
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
    });
    let _ = std::fs::remove_dir_all(&root);
}

/// What control sends drive 101 once it has gone silent. Never MIT: a hold on stale feedback would stop the limb for
/// that instead, so only the silence rule can.
#[derive(Clone, Copy)]
enum Then {
    /// The enable sequence's `run_mode` write every tick.
    RunModeWrite,
    /// A Disable the drive loses, then the `run_mode` write every tick. `Fault::Silent` hides from the host whether the
    /// drive took the Disable, so this is the same to it as a Disable answered by a Reset that is lost too; the
    /// `IgnoreDisables(1)` only documents the case.
    LostDisable,
}

/// A silent drive's run: the tick of the snapshot that showed its first counted miss, its miss count in each
/// snapshot after it until its limb stopped, and the tick of the snapshot that showed the stop.
struct Silent {
    from: u64,
    misses: Vec<(u64, u32)>,
    stopped: u64,
}

/// Drive 101 goes silent as it takes its `FAULT_ON_MIT`th hold and, for [`Then::LostDisable`], loses the Disable that
/// follows. Control holds both drives until a snapshot shows 101's first counted miss, then does `then` and holds
/// drive 102 throughout. Checks limb 1 ran on, limb 0 stopped for its silence with its Disable taken by the socket,
/// and drive 102 kept answering after it.
#[expect(
    clippy::unwrap_used,
    clippy::indexing_slicing,
    reason = "test helper: the run must start for the test to mean anything, and the bus has two limbs"
)]
fn silent_drive(then: Then) -> Silent {
    ensure_vcan(FAULT_BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-silent-{}", std::process::id()));
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    let ended = std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut silent = SimDrive::new(Drive::new(id(101), Model::Rs03), Uid([1; 8]), 23);
            silent
                .schedule(Trigger::OnMit(FAULT_ON_MIT), Fault::Silent)
                .unwrap();
            if let Then::LostDisable = then {
                silent
                    .schedule(Trigger::OnMit(FAULT_ON_MIT), Fault::IgnoreDisables(1))
                    .unwrap();
            }
            let mut drives = [
                silent,
                SimDrive::new(Drive::new(id(102), Model::Rs03), Uid([2; 8]), 24),
            ];
            serve(FAULT_BUS, &mut drives, &stop_sim, &mut |_| {})
        });
        let session = Session::start(&root, info(FAULT_BUS), 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (bus, mut commands, mut snapshots) = start_bus(epoch, buses.remove(0), &exit);
        let mut send = |snap: &Snapshot, frames| send(&mut commands, epoch, snap, frames);

        let end = Instant::now() + Duration::from_secs(10);
        let mut snap = enable_both(&mut send, &mut snapshots, end);
        let write = encode::param_write(&Write::mit_mode(Drive::new(id(101), Model::Rs03)));
        let active = [(LimbState::Active, None), (LimbState::Active, None)];
        // Hold both until the bus thread has counted 101's first unanswered command, whichever tick that is.
        let from = loop {
            send(&snap, [Some(hold(101)), Some(hold(102))]);
            snap = next_snapshot(&mut snapshots, end).unwrap();
            assert_eq!(limbs(&snap), active, "{snap:?}");
            let misses = snap.drive(0).map_or(0, |d| d.misses);
            if misses > 0 {
                assert_eq!(misses, 1, "{snap:?}");
                break snap.tick;
            }
        };
        let mut misses = Vec::new();
        let mut first = match then {
            Then::RunModeWrite => write,
            Then::LostDisable => encode::disable(id(101)),
        };
        let stopped = loop {
            send(&snap, [Some(first), Some(hold(102))]);
            first = write;
            snap = next_snapshot(&mut snapshots, end).unwrap();
            assert_eq!(limbs(&snap)[1], (LimbState::Active, None), "{snap:?}");
            if snap.limb(0).is_some_and(|l| l.state != LimbState::Active) {
                break snap.tick;
            }
            misses.push((snap.tick, snap.drive(0).map_or(0, |d| d.misses)));
        };
        assert!(
            matches!(
                limbs(&snap)[0],
                (
                    LimbState::Stopping { .. },
                    Some(StopReason::DriveSilent { slot: 0 })
                )
            ),
            "{snap:?}"
        );
        // The Disable went out in the tick that stopped the limb.
        let disabled = [can::StopOutcome::Sent, can::StopOutcome::Confirmed];
        assert!(
            snap.drive(0).is_some_and(|d| disabled.contains(&d.stop)),
            "{snap:?}"
        );
        // The other limb runs on after it.
        for _ in 0..3 {
            send(&snap, [None, Some(hold(102))]);
            snap = next_snapshot(&mut snapshots, end).unwrap();
            assert_eq!(limbs(&snap)[1], (LimbState::Active, None), "{snap:?}");
            assert!(snap.drive(1).is_some_and(|d| d.answered), "{snap:?}");
        }

        exit.store(true, Ordering::Release);
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
        Silent {
            from,
            misses,
            stopped,
        }
    });
    let _ = std::fs::remove_dir_all(&root);
    ended
}

/// Guards: safety - `host.silence` on a real socket: a running drive that stops answering stops its limb, and only its
/// limb, at the first send after `silence_misses` commands in a row go unanswered (PLAN item 6 Silence row).
#[test]
fn a_silent_drive_stops_only_its_limb_on_vcan() {
    let run = silent_drive(Then::RunModeWrite);
    for &(tick, misses) in &run.misses {
        assert_eq!(u64::from(misses), tick - run.from + 1, "tick {tick}");
    }
    assert_eq!(
        run.stopped,
        run.from + u64::from(timing().silence_misses),
        "silent from tick {}",
        run.from
    );
}

/// Guards: safety - `host.silence` on a real socket: a Disable the drive loses doesn't hold its silence off for good;
/// with no Reset read after it, the one miss before it stays counted through `stop_confirm_ns`, missed replies count
/// again after it, and the limb stops for them (PLAN item 2 Silence windows).
#[test]
fn a_lost_disable_doesnt_hide_a_silent_drive_on_vcan() {
    let t = timing();
    let quiet_ticks = t.stop_confirm_ns.div_ceil(t.period_ns);
    let run = silent_drive(Then::LostDisable);
    // Counting resumes at the first write sent `stop_confirm_ns` after the Disable, which went out the tick after the
    // first miss: a tick later if the Disable's tick woke late.
    let counted_from = run.from + 1 + quiet_ticks;
    let resumed = run
        .misses
        .iter()
        .find(|&&(_, m)| m > 1)
        .map(|&(tick, _)| tick);
    let resumed = resumed.unwrap_or(run.stopped);
    assert!(
        (counted_from..=counted_from + 1).contains(&resumed),
        "silent from tick {}, resumed at {resumed}: {:?}",
        run.from,
        run.misses
    );
    for &(tick, misses) in &run.misses {
        let expected = if tick < resumed {
            1
        } else {
            tick - resumed + 2
        };
        assert_eq!(u64::from(misses), expected, "tick {tick}");
    }
    assert_eq!(
        run.stopped,
        resumed + u64::from(t.silence_misses) - 1,
        "silent from tick {}, resumed at {resumed}",
        run.from
    );
}
