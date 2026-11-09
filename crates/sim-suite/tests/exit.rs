//! A stopped bus told to exit while control's ring is full, on `vcan` against `sim-drive`: it waits for control to read
//! its Stopped snapshot, and a control that never reads again doesn't hold its join. The helpers are `bus.rs`'s, small
//! enough to copy until the sim suite has a shared module.
#![cfg(target_os = "linux")]

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusConfig, BusDrive, BusLinks, CommandBatch, LimbState, Snapshot, Timing};
use robstride::{
    DeviceId, Drive, Frame, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad,
    RadPerSec, Radians, Uid, encode,
};
use sim_drive::{SimDrive, ensure_vcan, serve};
use telemetry::{Epoch, Recorder, Recording, Session, SessionInfo, SkeletonRef, Stage};

/// Shared with the slow-request and fault tests (`.config/nextest.toml`, group `can0`).
const BUS: &str = "can0";
/// Slow enough that the test thread, playing control, makes every tick on a loaded machine.
const HZ: u64 = 100;
const HOLD_TICKS: usize = 50;

/// The tick at `HZ`, with the send window stretched to the collect deadline: these tests check the loop and its
/// recording, not the wake budget, so a test thread that wakes a few milliseconds late on a loaded runner is not a
/// late wake (the tick tests cover that).
fn timing() -> Timing {
    let at_hz = Timing::at_hz(HZ);
    Timing {
        send_window_ns: at_hz.collect_ns,
        ..at_hz
    }
}
#[expect(
    clippy::unwrap_used,
    reason = "test helper: IDs here are constants in range"
)]
fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a hold command is in range"
)]
fn hold(n: u8) -> Frame {
    let command = MitCommand {
        position: Radians::new(0.0).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        kp: NmPerRad::new(5.0).unwrap(),
        kd: NmSecPerRad::new(0.5).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
    };
    encode::mit(Drive::new(id(n), Model::Rs03), &command).unwrap()
}

/// Drive `n` in limb `limb`.
fn drive(n: u8, limb: usize) -> BusDrive {
    BusDrive {
        device: id(n),
        limb,
    }
}

/// A schedule that starts two periods from now, as the runtime's does.
fn soon() -> Instant {
    Instant::now() + Duration::from_nanos(2 * 1_000_000_000 / HZ)
}

fn info() -> SessionInfo {
    SessionInfo {
        git_revision: "test".to_owned(),
        operator: "sim-suite".to_owned(),
        stage: Stage::Vcan,
        skeleton: SkeletonRef {
            path: "inline".to_owned(),
            sha256: "00".repeat(32),
        },
        buses: vec![can::bus_info(BUS, 1_000_000)],
    }
}

/// The snapshot for the next tick, waiting at most a second.
fn next_snapshot(snapshots: &mut rtrb::Consumer<Snapshot>, end: Instant) -> Option<Snapshot> {
    while Instant::now() < end {
        if let Ok(s) = snapshots.pop() {
            return Some(s);
        }
        std::thread::yield_now();
    }
    None
}

/// Sets both stop flags when dropped, including while a failed assertion unwinds.
struct Shutdown<'a>(&'a AtomicBool, Arc<AtomicBool>);

impl Drop for Shutdown<'_> {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
        self.1.store(true, Ordering::Release);
    }
}

/// Play control up to the hold: one batch per tick for the tick after the snapshot just read, enabling both drives
/// until both report Run, then holding for `HOLD_TICKS`; the last snapshot.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a missing snapshot fails the test"
)]
fn enable_and_hold(
    commands_tx: &mut rtrb::Producer<CommandBatch>,
    snapshots: &mut rtrb::Consumer<Snapshot>,
    epoch: Epoch,
) -> Snapshot {
    let end = Instant::now() + Duration::from_secs(20);
    let period = 1_000_000_000 / HZ;
    let mut send = |snap: &Snapshot, frames: [Option<Frame>; 2]| {
        let tick = snap.tick + 1;
        // Good for three periods from now: long enough to reach its tick, never long enough to be sent late.
        let mut batch = CommandBatch::new(tick, epoch.ns(Instant::now()) + 3 * period);
        for (slot, frame) in frames.into_iter().enumerate() {
            if let Some(frame) = frame {
                assert!(batch.set(slot, frame));
            }
        }
        assert!(commands_tx.push(batch).is_ok());
    };
    // Enable both, until both report Run.
    let mut snap = next_snapshot(snapshots, end).unwrap();
    let mut enabled = false;
    while !enabled {
        send(
            &snap,
            [Some(encode::enable(id(101))), Some(encode::enable(id(102)))],
        );
        snap = next_snapshot(snapshots, end).unwrap();
        enabled = snap.drives().all(|d| {
            d.observed
                .is_some_and(|o| o.status.header.mode == Mode::Run)
        });
    }
    // Hold: every drive answers every tick.
    let mut answered = 0;
    for _ in 0..HOLD_TICKS {
        send(&snap, [Some(hold(101)), Some(hold(102))]);
        snap = next_snapshot(snapshots, end).unwrap();
        assert!(
            snap.limbs().all(|(_, l)| l.state == LimbState::Active),
            "{snap:?}"
        );
        answered += snap.drives().filter(|d| d.answered).count();
    }
    // One tick of slack: the test thread playing control may miss one tick on a loaded runner (two would stop the bus).
    assert!(
        answered >= 2 * (HOLD_TICKS - 1),
        "answered {answered} of {}",
        2 * HOLD_TICKS
    );
    snap
}

/// Let real time go by with the bus thread running, without sleeping.
fn pass(span: Duration) {
    let end = Instant::now() + span;
    while Instant::now() < end {
        std::thread::yield_now();
    }
}

/// An active bus told to exit with control's ring full: `drain` says whether control then reads again. Returns whether
/// the thread was still running 200 ms after `exit`, the last snapshot it handed back, and whether it ended without an
/// error.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a missing snapshot or a failed join fails the test"
)]
fn exit_with_a_full_ring(drain: bool) -> (bool, Option<Snapshot>, bool) {
    ensure_vcan(BUS).unwrap();
    let dir = std::env::temp_dir().join(format!(
        "sim-suite-full-ring-{}-{drain}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    let out = std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [
                SimDrive::new(Drive::new(id(101), Model::Rs03), Uid([1; 8]), 7),
                SimDrive::new(Drive::new(id(102), Model::Rs03), Uid([2; 8]), 8),
            ];
            serve(BUS, &mut drives, &stop_sim)
        });
        let session = Session::start(&dir, info(), 1_794_178_885_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (mut commands_tx, commands_rx) = rtrb::RingBuffer::new(4);
        // Small, so that a control that stops reading fills it in a few ticks.
        let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(4);
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
                epoch,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();
        let _ = enable_and_hold(&mut commands_tx, &mut snapshots, epoch);

        // Control stops reading; the ring fills; then the exit.
        pass(Duration::from_millis(300));
        exit.store(true, Ordering::Release);
        pass(Duration::from_millis(200));
        let running = !bus.thread.is_finished();
        if drain {
            let end = Instant::now() + Duration::from_secs(10);
            while !bus.thread.is_finished() {
                assert!(Instant::now() < end, "the bus never ended");
                let _ = snapshots.pop();
                std::thread::yield_now();
            }
        } else {
            // Never read again: the thread still has to end.
            let end = Instant::now() + Duration::from_secs(10);
            while !bus.thread.is_finished() {
                assert!(Instant::now() < end, "the bus never ended");
                std::thread::yield_now();
            }
        }
        let done = bus.thread.join().unwrap();
        let (last, clean) = (done.last, done.error.is_none());
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
        (running, last, clean)
    });
    let _ = std::fs::remove_dir_all(&dir);
    out
}

/// Guards: protocol - a stopped bus told to exit does not return while control's ring is full and control may still
/// read: control gets the Stopped snapshot first (can.md section 2 "every drop counted"; PLAN.md item 3 shutdown).
#[test]
fn a_stopped_bus_waits_for_a_ring_that_can_take_its_stopped_snapshot() {
    let (running, last, clean) = exit_with_a_full_ring(true);
    assert!(
        running,
        "the bus ended before control could read its Stopped snapshot"
    );
    assert!(clean);
    assert!(last.is_some_and(|s| s.stopped()), "{last:?}");
}

/// Guards: safety - a control that never reads again cannot hold the bus thread's join (and the recorder's close)
/// forever: the thread ends after its wait with the Stopped snapshot in its exit (PLAN.md item 3: a hung control
/// thread must let the drives time out; rust.md section 12 shutdown).
#[test]
fn a_stopped_bus_ends_when_control_never_reads_again() {
    let (_, last, clean) = exit_with_a_full_ring(false);
    assert!(clean);
    assert!(last.is_some_and(|s| s.stopped()), "{last:?}");
}
