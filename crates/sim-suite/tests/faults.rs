//! Faults injected into `sim-drive` on `vcan`, caught by the bus layer on a real socket (PLAN item 4 Done when: each
//! stop rule proven with its trigger injected on `vcan`).
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusConfig, BusLinks, CommandBatch, LimbState, Snapshot, Spawned, StopReason, Timing};
use common::{HZ, Shutdown, drive, hold, id, info, limbs, next_snapshot, soon};
use robstride::{Drive, Frame, Mode, Model, StatusFault, StatusFaults, Uid, encode};
use sim_drive::{Fault, Injected, SimDrive, Trigger, ensure_vcan, serve};
use telemetry::{BusRecorder, Epoch, Recorder, Recording, Session};

/// Shared with the slow-request test, which nextest runs apart from this one (`.config/nextest.toml`, group `can0`).
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
            timing: Timing::at_hz(HZ),
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

/// Guards: safety - a fault injected into one drive on `vcan` is caught before the next send: within one tick of the
/// bus thread reading it, that drive's limb is stopping with `DriveFault` and its Disable sent, control's next frame to
/// it is refused, and the bus's other limb keeps getting commands and answering; the injection is reported as it
/// fires (PLAN item 6 Faults row; step 7 design D1; logging.md section 3: injected faults recorded).
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
        let mut snap = next_snapshot(&mut snapshots, end).unwrap();
        while !snap.drives().all(|d| {
            d.observed
                .is_some_and(|o| o.status.header.mode == Mode::Run)
        }) {
            send(
                &snap,
                [Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
            );
            snap = next_snapshot(&mut snapshots, end).unwrap();
        }
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
                stopped = Some(snap.tick);
            }
            if seen.is_none() {
                assert_eq!(
                    limbs(&snap),
                    [(LimbState::Active, None), (LimbState::Active, None)],
                    "{snap:?}"
                );
            }
        }
        let (seen, stopped) = (seen.unwrap(), stopped.unwrap());
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
        // Control learns of the stop only now, so its next frame to drive 101 is refused; limb 1 runs on.
        for _ in 0..5 {
            send(&snap, [Some(hold(101)), Some(hold(102))]);
            snap = next_snapshot(&mut snapshots, end).unwrap();
            assert_eq!(limbs(&snap)[1], (LimbState::Active, None), "{snap:?}");
            assert!(snap.drive(1).is_some_and(|d| d.answered), "{snap:?}");
        }
        assert!(snap.counters.refused_frames >= 1, "{:?}", snap.counters);
        assert_ne!(
            snap.drive(0).map(|d| d.stop),
            Some(can::StopOutcome::NeverSent)
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
