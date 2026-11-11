//! Control's orders to a bus thread on `vcan`: a stop of one limb and the operator's clear, through the rings the
//! runtime uses, against `sim-drive` (step 7 design, D2: control asks for a stop by order, never with Disables in a
//! batch).
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusLinks, CommandBatch, LimbState, Order, RearmRefused, Rearmed, Snapshot,
    StopReason,
};
use common::{HZ, Shutdown, drive, hold, id, info, limbs, next_snapshot, soon, timing};
use robstride::{Drive, Frame, Mode, Model, Uid, encode};
use sim_drive::{SimDrive, ensure_vcan, serve};
use telemetry::{Epoch, Recorder, Recording, Session};

/// Shared with the exit, slow-request, fault and enable tests, which nextest runs one at a time with these
/// (`.config/nextest.toml`, group `can0`).
const BUS: &str = "can0";

/// Control's batch for the tick after `snap`, good for three periods.
fn batch(epoch: Epoch, snap: &Snapshot, frames: [Option<Frame>; 2]) -> CommandBatch {
    let period = 1_000_000_000 / HZ;
    let mut batch = CommandBatch::new(snap.tick + 1, epoch.ns(Instant::now()) + 3 * period);
    for (slot, frame) in frames.into_iter().enumerate() {
        if let Some(frame) = frame {
            assert!(batch.set(slot, frame));
        }
    }
    batch
}

/// Guards: safety - on a real socket, control's order to stop one limb stops that limb alone (`LimbRequested`) while
/// the bus's other limb keeps its commands and answers; once the stop has ended, a re-arm order (the operator's clear)
/// is answered once under its tag and makes the limb idle with a new generation; and a stop order naming a limb the
/// bus doesn't have stops every limb (PLAN item 6: a stop names its scope, a latched stop clears only by an operator
/// clear, `host.hang`).
#[test]
#[expect(clippy::too_many_lines, reason = "one control loop, start to end")]
fn a_stop_order_stops_one_limb_and_a_rearm_order_clears_it_on_vcan() {
    ensure_vcan(BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-orders-{}", std::process::id()));
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [
                SimDrive::new(Drive::new(id(101), Model::Rs03), Uid([1; 8]), 31),
                SimDrive::new(Drive::new(id(102), Model::Rs03), Uid([2; 8]), 32),
            ];
            serve(BUS, &mut drives, &stop_sim, &mut |_| {})
        });
        let session = Session::start(&root, info(BUS), 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (mut commands, commands_rx) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(64);
        let (mut orders, orders_rx) = rtrb::RingBuffer::new(4);
        let (rearmed_tx, mut rearmed) = rtrb::RingBuffer::new(4);
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                drives: vec![drive(101, 0), drive(102, 1)],
                timing: timing(),
            },
            BusLinks {
                commands: commands_rx,
                snapshots: snapshots_tx,
                recorder: buses.remove(0),
                requests: rtrb::RingBuffer::new(1).1,
                results: rtrb::RingBuffer::new(1).0,
                orders: orders_rx,
                rearmed: rearmed_tx,
                epoch,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();

        // Play control: enable both until both run.
        let end = Instant::now() + Duration::from_secs(10);
        let mut snap = next_snapshot(&mut snapshots, end).unwrap();
        while !snap.drives().all(|d| {
            d.observed
                .is_some_and(|o| o.status.header.mode == Mode::Run)
        }) {
            let enables = [Some(encode::enable(id(101))), Some(encode::enable(id(102)))];
            assert!(commands.push(batch(epoch, &snap, enables)).is_ok());
            snap = next_snapshot(&mut snapshots, end).unwrap();
        }
        // Hold both a few ticks, then order limb 0 stopped and go on holding limb 1 alone.
        for _ in 0..3 {
            let holds = [Some(hold(101)), Some(hold(102))];
            assert!(commands.push(batch(epoch, &snap, holds)).is_ok());
            snap = next_snapshot(&mut snapshots, end).unwrap();
        }
        assert_eq!(
            limbs(&snap),
            [(LimbState::Active, None), (LimbState::Active, None)]
        );
        assert!(orders.push(Order::StopLimb(0)).is_ok());
        let ordered_ns = epoch.ns(Instant::now());
        let period = 1_000_000_000 / HZ;
        loop {
            assert!(
                commands
                    .push(batch(epoch, &snap, [None, Some(hold(102))]))
                    .is_ok()
            );
            snap = next_snapshot(&mut snapshots, end).unwrap();
            let (state, stop) = limbs(&snap)[0];
            if state != LimbState::Active {
                assert_eq!(stop, Some(StopReason::LimbRequested), "{snap:?}");
                // This thread may read snapshots a few ticks behind the bus, so the stop is timed by when it began:
                // pushed at `ordered_ns`, the order is taken at the next tick's start, within a period and that
                // tick's wake.
                if let LimbState::Stopping { since_ns } = state {
                    assert!(
                        since_ns <= ordered_ns + 2 * period,
                        "ordered at {ordered_ns} ns: {snap:?}"
                    );
                }
            }
            assert_eq!(limbs(&snap)[1], (LimbState::Active, None), "{snap:?}");
            assert!(snap.drive(1).is_some_and(|d| d.answered), "{snap:?}");
            if state == LimbState::Stopped {
                break;
            }
        }
        assert_eq!(snap.limb(0).map(|l| l.generation), Some(0));

        // The operator's clear.
        assert!(orders.push(Order::Rearm { tag: 5, limb: 0 }).is_ok());
        let answer = loop {
            assert!(
                commands
                    .push(batch(epoch, &snap, [None, Some(hold(102))]))
                    .is_ok()
            );
            snap = next_snapshot(&mut snapshots, end).unwrap();
            if let Ok(answer) = rearmed.pop() {
                break answer;
            }
        };
        assert_eq!(
            answer,
            Rearmed {
                tag: 5,
                limb: 0,
                outcome: Ok(()),
            }
        );
        // This thread may read snapshots behind the bus: the clear shows in the first one made after it was taken.
        while snap.limb(0).is_some_and(|l| l.generation == 0) {
            assert_eq!(
                limbs(&snap)[0],
                (LimbState::Stopped, Some(StopReason::LimbRequested))
            );
            assert!(
                commands
                    .push(batch(epoch, &snap, [None, Some(hold(102))]))
                    .is_ok()
            );
            snap = next_snapshot(&mut snapshots, end).unwrap();
        }
        assert_eq!(limbs(&snap)[0], (LimbState::Idle, None), "{snap:?}");
        assert_eq!(snap.limb(0).map(|l| l.generation), Some(1));
        assert_eq!(snap.counters.rearms_dropped, 0);

        // A stop order naming a limb the bus doesn't have stops both limbs, the running one included.
        assert!(orders.push(Order::StopLimb(7)).is_ok());
        while limbs(&snap)[1].0 == LimbState::Active {
            assert!(
                commands
                    .push(batch(epoch, &snap, [None, Some(hold(102))]))
                    .is_ok()
            );
            snap = next_snapshot(&mut snapshots, end).unwrap();
        }
        let bad = Some(StopReason::BadOrder { limb: 7 });
        for (state, stop) in limbs(&snap) {
            assert!(matches!(state, LimbState::Stopping { .. }), "{snap:?}");
            assert_eq!(stop, bad, "{snap:?}");
        }
        assert_eq!(snap.counters.bad_orders, 1);

        // Told to exit, the bus finishes the stop and ends once control has taken a snapshot showing it. A clear sent
        // as it exits never undoes that stop: refused (limb 0 still stopping) or left for the end (`Ended`).
        exit.store(true, Ordering::Release);
        assert!(orders.push(Order::Rearm { tag: 6, limb: 0 }).is_ok());
        while !bus.thread.is_finished() {
            if let Ok(s) = snapshots.pop() {
                snap = s;
            }
            assert!(Instant::now() < end, "the bus never ended: {snap:?}");
            std::thread::yield_now();
        }
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        assert!(done.last.is_some_and(|s| s.stopped()), "{:?}", done.last);
        let answer = rearmed.pop().unwrap();
        assert_eq!((answer.tag, answer.limb), (6, 0));
        assert!(
            matches!(
                answer.outcome,
                Err(RearmRefused::Ended | RearmRefused::NotStopped(0))
            ),
            "{answer:?}"
        );
        assert!(rearmed.pop().is_err(), "one answer per re-arm order");
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
    });
    let _ = std::fs::remove_dir_all(&root);
}

/// Guards: safety - a bus that ends answers every clear still in its order ring `Ended`, takes none of them on the
/// way out, and counts each answer control's full ring can't take, so a clear is never silently lost (PLAN item 6: a
/// latched stop clears only by an operator clear; logging.md section 4: nothing fails in silence).
#[test]
fn a_bus_that_ends_answers_every_queued_clear_and_counts_the_drops_on_vcan() {
    ensure_vcan(BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-orders-end-{}", std::process::id()));
    let exit = Arc::new(AtomicBool::new(true));
    let session = Session::start(&root, info(BUS), 1_000_000_000).unwrap();
    let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
    let epoch = recording.epoch();
    let recorder = Recorder::spawn(recording).unwrap();
    let (mut orders, orders_rx) = rtrb::RingBuffer::new(4);
    // Room for one answer: the other two are dropped and counted.
    let (rearmed_tx, mut rearmed) = rtrb::RingBuffer::new(1);
    for tag in 1..=3 {
        assert!(orders.push(Order::Rearm { tag, limb: 0 }).is_ok());
    }
    // Told to exit before its first tick with every limb idle, the bus ends at its first drain.
    let bus = can::spawn(
        BusConfig {
            name: BUS.to_owned(),
            drives: vec![drive(101, 0)],
            timing: timing(),
        },
        BusLinks {
            commands: rtrb::RingBuffer::new(1).1,
            snapshots: rtrb::RingBuffer::new(1).0,
            recorder: buses.remove(0),
            requests: rtrb::RingBuffer::new(1).1,
            results: rtrb::RingBuffer::new(1).0,
            orders: orders_rx,
            rearmed: rearmed_tx,
            epoch,
            start: soon(),
            exit: Arc::clone(&exit),
        },
    )
    .unwrap();
    let done = bus.thread.join().unwrap();
    assert!(done.error.is_none(), "{:?}", done.error);
    assert_eq!(
        rearmed.pop(),
        Ok(Rearmed {
            tag: 1,
            limb: 0,
            outcome: Err(RearmRefused::Ended),
        })
    );
    assert!(rearmed.pop().is_err());
    assert_eq!(done.counters.rearms_dropped, 2);
    recorder.close(vec![done.recorder]).unwrap();
    let _ = std::fs::remove_dir_all(&root);
}
