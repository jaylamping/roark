//! A bus with two active limbs told to exit while control's ring is full, on `vcan` against `sim-drive`: it stops every
//! limb, and returns once control's ring takes a snapshot with every limb stopped, once control drops the ring, or after
//! its wait when control never reads again. The helpers are `bus.rs`'s, small enough to copy until the sim suite has a shared module.
#![cfg(target_os = "linux")]

use std::io;
use std::path::Path;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusDrive, BusLinks, CommandBatch, LimbState, Snapshot, StopOutcome, StopReason,
    Timing,
};
use robstride::{
    DeviceId, Drive, Frame, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad,
    RadPerSec, Radians, Uid, encode,
};
use sim_drive::{SimDrive, ensure_vcan, serve};
use telemetry::wire::{Frames, Stamp};
use telemetry::{Direction, Epoch, Recorder, Recording, Session, SessionInfo, SkeletonRef, Stage};

/// Shared by the tests in this file, one at a time (`.config/nextest.toml`, group `can0`).
const BUS: &str = "can0";
/// Slow enough that the test thread, playing control, makes every tick on a loaded machine.
const HZ: u64 = 100;
const PERIOD_NS: u64 = Timing::at_hz(HZ).period_ns;
const HOLD_TICKS: usize = 50;
/// Control's snapshot ring: small, so a control that stops reading fills it in a few ticks.
const RING: usize = 4;
/// `RING`, counted in ticks: the ring holds one snapshot a tick.
const RING_TICKS: u64 = RING as u64;
/// The stop window, long next to the stop these drives need (they confirm the first Disable and take their reporting
/// off after the 50 ms post-Disable silence, a few ticks), so a bus that waits one window after its stop can't be
/// mistaken for one that didn't; and not a whole number of periods, so the wait's rounding up shows.
const STOP_WINDOW_NS: u64 = 505_000_000;
/// The all-stopped snapshots a bus makes for a ring that takes none before it returns: one stop window in ticks, rounded
/// up (`BusLinks::exit`).
const EXIT_WAIT: u64 = STOP_WINDOW_NS.div_ceil(PERIOD_NS);

/// The tick at `HZ`, with the send window stretched to the collect deadline (these tests check the exit, not the wake
/// budget, so a test thread that wakes a few milliseconds late on a loaded runner is not a late wake; the tick tests
/// cover that), and the stop window at `STOP_WINDOW_NS`.
fn timing() -> Timing {
    let at_hz = Timing::at_hz(HZ);
    Timing {
        send_window_ns: at_hz.collect_ns,
        stop_confirm_ns: STOP_WINDOW_NS,
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
    Instant::now() + Duration::from_nanos(2 * PERIOD_NS)
}

/// Every limb's state in `snap`.
fn states(snap: &Snapshot) -> Vec<LimbState> {
    snap.limbs().map(|(_, l)| l.state).collect()
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

/// The snapshot for the next tick, waiting at most until `end`.
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

/// Push control's batch for `tick`, good for three periods from now: long enough to reach its tick, never long enough
/// to be sent late.
fn push_batch(
    commands_tx: &mut rtrb::Producer<CommandBatch>,
    epoch: Epoch,
    tick: u64,
    frames: [Option<Frame>; 2],
) {
    let mut batch = CommandBatch::new(tick, epoch.ns(Instant::now()) + 3 * PERIOD_NS);
    for (slot, frame) in frames.into_iter().enumerate() {
        if let Some(frame) = frame {
            assert!(batch.set(slot, frame));
        }
    }
    assert!(commands_tx.push(batch).is_ok());
}

fn holds() -> [Option<Frame>; 2] {
    [Some(hold(101)), Some(hold(102))]
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
    // Enable both, until both report Run.
    let mut snap = next_snapshot(snapshots, end).unwrap();
    let mut enabled = false;
    while !enabled {
        push_batch(
            commands_tx,
            epoch,
            snap.tick + 1,
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
        push_batch(commands_tx, epoch, snap.tick + 1, holds());
        snap = next_snapshot(snapshots, end).unwrap();
        assert_eq!(
            states(&snap),
            [LimbState::Active, LimbState::Active],
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

/// What control does once `exit` is set.
#[derive(Clone, Copy, Debug)]
enum After {
    /// Reads its ring again.
    Reads,
    /// Never reads again, but keeps the ring.
    NeverReads,
    /// Drops its end of the ring.
    DropsRing,
}

/// How a run ended.
struct Ended {
    /// The last snapshot control read while holding.
    held: Snapshot,
    /// Every snapshot control read after the hold, in order: while reading again, and what was left in the ring once
    /// the thread ended (none if control dropped it).
    read: Vec<Snapshot>,
    /// The thread's `BusExit::last`.
    last: Option<Snapshot>,
    /// The thread's `BusExit::error`.
    error: Option<io::Error>,
    /// Every tick the recording holds, in order.
    recorded: Vec<Recorded>,
}

/// One tick as the recording shows it.
struct Recorded {
    tick: u64,
    /// When the tick woke, on the wall clock.
    woke: Stamp,
    /// The kernel stamps (wall clock) of the bus's own frames read back in the tick.
    echoes: Vec<Stamp>,
}

fn order(stamp: Stamp) -> (u64, u32) {
    (stamp.sec, stamp.nsec)
}

/// The ticks the recording holds.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: an unreadable recording fails the test"
)]
fn recorded(mcap: &Path) -> Vec<Recorded> {
    let bytes = std::fs::read(mcap).unwrap();
    let mut ticks = Vec::new();
    for message in mcap::MessageStream::new(&bytes).unwrap() {
        let message = message.unwrap();
        if message.channel.topic != format!("/can/{BUS}/frames") {
            continue;
        }
        let frames: Frames = serde_json::from_slice(&message.data).unwrap();
        ticks.push(Recorded {
            tick: frames.tick,
            woke: frames.wall,
            echoes: frames
                .frames
                .iter()
                .filter(|f| f.direction == Direction::TxEcho)
                .map(|f| f.stamp)
                .collect(),
        });
    }
    ticks
}

impl Ended {
    /// The ticks that ran after tick `after`, up to and including tick `upto`: each made one snapshot. Counted from
    /// the recording, which holds every tick that ran (a tick a stalled thread skipped is in neither).
    fn ran(&self, after: u64, upto: u64) -> u64 {
        let count = self
            .recorded
            .iter()
            .filter(|r| r.tick > after && r.tick <= upto)
            .count();
        u64::try_from(count).unwrap_or(u64::MAX)
    }

    /// The tick that wrote the bus's last frame. Its echo is read in that tick, or, written after the tick's collect
    /// deadline, in the next tick's drain: then it arrived before the reading tick woke.
    #[expect(
        clippy::expect_used,
        reason = "test helper: a stop that sent nothing fails the test"
    )]
    fn last_send(&self) -> u64 {
        let at = self
            .recorded
            .iter()
            .rposition(|r| !r.echoes.is_empty())
            .expect("the bus sent its stop");
        let reading = self.recorded.get(at).expect("in range");
        let last_echo = reading
            .echoes
            .iter()
            .copied()
            .map(order)
            .max()
            .expect("an echo");
        if last_echo >= order(reading.woke) {
            reading.tick
        } else {
            at.checked_sub(1)
                .and_then(|i| self.recorded.get(i))
                .expect("a tick before")
                .tick
        }
    }

    /// The tick the stop ended in: the one that wrote its last reporting off. That holds when every drive confirmed and
    /// the socket took its reporting off; a reporting off the queue kept refusing would hold the stop to the end of
    /// its window instead, and this says so rather than misread it.
    fn stopped_at(&self, last: &Snapshot) -> u64 {
        assert!(
            last.drives()
                .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent),
            "the stop didn't end on its last reporting off: {last:?}"
        );
        self.last_send()
    }
}

/// Enable and hold both drives, then keep sending a fresh hold every tick while no longer reading, until control's
/// ring is full; then set `exit` with the bus still active, and do `after`.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a missing snapshot or a failed join fails the test"
)]
fn exit_with_a_full_ring(after: After) -> Ended {
    ensure_vcan(BUS).unwrap();
    let dir = std::env::temp_dir().join(format!(
        "sim-suite-full-ring-{}-{after:?}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    let ended = std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [
                SimDrive::new(Drive::new(id(101), Model::Rs03), Uid([1; 8]), 7),
                SimDrive::new(Drive::new(id(102), Model::Rs03), Uid([2; 8]), 8),
            ];
            serve(BUS, &mut drives, &stop_sim)
        });
        let session = Session::start(&dir, info(), 1_794_178_885_000_000_000).unwrap();
        let session_dir = session.dir().to_owned();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (mut commands_tx, commands_rx) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(RING);
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
        let held = enable_and_hold(&mut commands_tx, &mut snapshots, epoch);

        // Control stops reading but keeps the drives held: the bus publishes one snapshot a tick, so the ring's count
        // says which tick has ended, and the next batch is for the tick after it.
        let end = Instant::now() + Duration::from_secs(10);
        let mut queued = 0;
        while queued < RING {
            push_batch(
                &mut commands_tx,
                epoch,
                held.tick + u64::try_from(queued).unwrap() + 1,
                holds(),
            );
            while snapshots.slots() == queued {
                assert!(Instant::now() < end, "the bus published nothing");
                std::thread::yield_now();
            }
            queued = snapshots.slots();
        }
        exit.store(true, Ordering::Release);

        let mut read = Vec::new();
        let mut snapshots = match after {
            After::DropsRing => {
                drop(snapshots);
                None
            }
            After::Reads | After::NeverReads => Some(snapshots),
        };
        let end = Instant::now() + Duration::from_secs(10);
        while !bus.thread.is_finished() {
            assert!(Instant::now() < end, "the bus never ended");
            if let (After::Reads, Some(ring)) = (after, snapshots.as_mut())
                && let Ok(s) = ring.pop()
            {
                read.push(s);
                continue;
            }
            std::thread::yield_now();
        }
        let done = bus.thread.join().unwrap();
        if let Some(ring) = snapshots.as_mut() {
            while let Ok(s) = ring.pop() {
                read.push(s);
            }
        }
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
        Ended {
            held,
            read,
            last: done.last,
            error: done.error,
            recorded: recorded(&session_dir.join("0000.mcap")),
        }
    });
    let _ = std::fs::remove_dir_all(&dir);
    ended
}

/// What every run shares: no error, and a last snapshot with every limb stopped by the exit's own stop (active limbs
/// told to exit, not ones control's silence had already stopped).
#[expect(
    clippy::unwrap_used,
    reason = "test helper: no last snapshot fails the test"
)]
fn stopped_by_the_exit(ended: &Ended) -> Snapshot {
    assert!(ended.error.is_none(), "{:?}", ended.error);
    let last = ended.last.unwrap();
    assert!(
        last.limbs()
            .all(|(_, l)| (l.state, l.stop) == (LimbState::Stopped, Some(StopReason::Requested))),
        "{last:?}"
    );
    assert_eq!(last.bus_error, None, "{last:?}");
    last
}

/// The ring full of the ticks after the hold, every limb active in each: control kept the drives held until `exit`.
fn full_of_active_ticks(ended: &Ended) {
    let queued: Vec<(u64, Vec<LimbState>)> = ended
        .read
        .iter()
        .take(RING)
        .map(|s| (s.tick, states(s)))
        .collect();
    let expected: Vec<(u64, Vec<LimbState>)> = (1..=RING_TICKS)
        .map(|k| (ended.held.tick + k, vec![LimbState::Active; 2]))
        .collect();
    assert_eq!(queued, expected);
}

/// Guards: protocol - a bus told to exit hands control its end: control's ring gets a snapshot with every limb stopped,
/// and the thread returns on the tick it does, with that snapshot as `BusExit::last`, not after a wait meant for a
/// control that
/// stopped reading (can.md section 2 Receive, "the drop is counted and reported"; rust.md section 5, every thread's
/// explicit stop path).
#[test]
fn a_bus_told_to_exit_returns_once_controls_ring_takes_its_stopped_snapshot() {
    let ended = exit_with_a_full_ring(After::Reads);
    let last = stopped_by_the_exit(&ended);
    full_of_active_ticks(&ended);
    let first_stopped = ended
        .read
        .iter()
        .position(Snapshot::stopped)
        .expect("control read a snapshot with every limb stopped");
    // The first all-stopped snapshot the ring took is the last one made: had the thread gone on waiting, control would
    // have read more after it.
    assert_eq!(first_stopped + 1, ended.read.len(), "{:?}", ended.read);
    assert_eq!(ended.read.last(), Some(&last));
}

/// Guards: safety - a control that never reads again cannot hold the bus thread's join (and the recorder's close)
/// forever: the thread ends after one stop window of untaken all-stopped snapshots, and its last snapshot counts its own
/// drop (PLAN.md item 3, "A hung control thread must let the drives time out"; rust.md section 5, every thread's
/// explicit stop path; can.md section 2 Receive, "the drop is counted and reported").
#[test]
fn a_bus_told_to_exit_ends_when_control_never_reads_again() {
    let ended = exit_with_a_full_ring(After::NeverReads);
    let last = stopped_by_the_exit(&ended);
    full_of_active_ticks(&ended);
    assert_eq!(ended.read.len(), RING, "{:?}", ended.read);
    let taken = *ended.read.last().expect("the full ring");
    // The wait: exactly one stop window, rounded up, of all-stopped snapshots after the one the stops ended in.
    let stopped = ended.stopped_at(&last);
    assert_eq!(ended.ran(stopped - 1, last.tick), EXIT_WAIT);
    // Every snapshot made after the ring filled was dropped, and counted: the last counts itself.
    assert_eq!(
        last.counters.snapshots_dropped - taken.counters.snapshots_dropped,
        ended.ran(taken.tick, last.tick)
    );
}

/// Guards: safety - a control that drops its end of the ring cannot hold the bus thread's join: told to exit, the thread
/// stops every limb and ends at its first all-stopped snapshot, without waiting the stop window for a reader that is
/// gone (PLAN.md item 3, "A hung control thread must let the drives time out"; rust.md section 5, every thread's
/// explicit stop path).
#[test]
fn a_bus_told_to_exit_ends_at_once_when_control_drops_its_ring() {
    let ended = exit_with_a_full_ring(After::DropsRing);
    let last = stopped_by_the_exit(&ended);
    // The thread ended at its first all-stopped snapshot, not after a wait for a reader that is gone.
    assert_eq!(last.tick, ended.stopped_at(&last));
}
