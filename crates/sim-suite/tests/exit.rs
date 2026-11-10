//! A bus of two limbs told to exit, on `vcan` against `sim-drive`. Both active, with control's ring full: it stops every
//! limb, and returns once control's ring takes a snapshot with every limb stopped, once control drops the ring, or after
//! its wait when control never reads again. Both stopping, with no time to collect: the stops' last echoes reach the
//! recording through the drain it returns at. And a bus that ends with slow results control's ring can't take counts
//! them. The helpers are `bus.rs`'s, small enough to copy until the sim suite has a shared module.
#![cfg(target_os = "linux")]

use std::io;
use std::path::Path;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusDrive, BusLinks, CommandBatch, LimbState, SlowKind, SlowOutcome, SlowRefusal,
    SlowRequest, SlowResult, Snapshot, StopOutcome, StopReason, Timing,
};
use robstride::{
    DeviceId, Drive, Frame, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad, Param,
    RadPerSec, Radians, Reporting, Uid, encode,
};
use sim_drive::{SimDrive, ensure_vcan, serve};
use telemetry::wire::{self, Frames, Stamp};
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

/// The tick at `HZ` with no time to collect: the send window and the collect deadline 1 ns after the tick's scheduled
/// start, which `Timing::check` accepts (it asks for a non-zero send window that ends by the collect deadline, and every
/// lag and span it bounds stays small). A wake measures at most the gap between the shell's two start reads of the
/// clock early, tens of nanoseconds, and a drain's read and each write are system calls of a microsecond or more, so
/// every frame is written after its tick's collect deadline, and its echo, like any reply, is read only in the next
/// tick's drain. Every wake is also past the send window, so no limb enables: an idle limb's late tick is held. The
/// post-Disable silence is long (well inside the stop window) to give control time to set `exit` before the stops
/// end.
fn no_collect_timing() -> Timing {
    Timing {
        send_window_ns: 1,
        collect_ns: 1,
        disable_silence_ns: 200_000_000,
        ..timing()
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
    /// The last snapshot control read before setting `exit`.
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
    /// The bus's own frames read back in the tick, each with its kernel stamp (wall clock).
    echoes: Vec<wire::Frame>,
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
                .cloned()
                .collect(),
        });
    }
    ticks
}

impl Ended {
    /// The ticks that ran after tick `after`, up to and including tick `upto`, which stays at or below `last.tick`:
    /// each of those made one snapshot, while the exit drain's tick after `last.tick` made none. Counted from the
    /// recording, which holds every tick that ran (a tick a stalled thread skipped is in neither).
    fn ran(&self, after: u64, upto: u64) -> u64 {
        let count = self
            .recorded
            .iter()
            .filter(|r| r.tick > after && r.tick <= upto)
            .count();
        u64::try_from(count).unwrap_or(u64::MAX)
    }

    /// The tick that wrote the bus's last frame. Its echo is read in that tick, or, written after the tick's collect
    /// deadline, in the next tick's drain: then it arrived before the reading tick woke. That compares the echo's
    /// kernel stamp with the tick's wake, both on the wall clock, since the recording stamps neither on the monotonic
    /// one, so it assumes the wall clock doesn't step during the run.
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
            .map(|f| order(f.stamp))
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

/// Control's side of a run: what it plays with, and what it hands back once the bus thread has ended.
struct Control<'a> {
    commands: rtrb::Producer<CommandBatch>,
    snapshots: rtrb::Consumer<Snapshot>,
    epoch: Epoch,
    exit: &'a AtomicBool,
    thread: &'a std::thread::JoinHandle<can::BusExit>,
}

/// What control did: the last snapshot it read before setting `exit`, those it read after, and its ring if it kept it.
struct Played {
    held: Snapshot,
    read: Vec<Snapshot>,
    ring: Option<rtrb::Consumer<Snapshot>>,
}

/// Wait for the bus thread to end, reading `ring` meanwhile if given; what was read.
fn wait_for_the_end(
    thread: &std::thread::JoinHandle<can::BusExit>,
    mut ring: Option<&mut rtrb::Consumer<Snapshot>>,
) -> Vec<Snapshot> {
    let mut read = Vec::new();
    let end = Instant::now() + Duration::from_secs(10);
    while !thread.is_finished() {
        assert!(Instant::now() < end, "the bus never ended");
        if let Some(Ok(s)) = ring.as_mut().map(|r| r.pop()) {
            read.push(s);
            continue;
        }
        std::thread::yield_now();
    }
    read
}

/// Run both drives' bus at `timing` with `control` playing control, and read back how it ended.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a failed setup or join fails the test"
)]
fn run_bus(label: &str, timing: Timing, control: impl FnOnce(Control<'_>) -> Played) -> Ended {
    ensure_vcan(BUS).unwrap();
    let dir = std::env::temp_dir().join(format!("sim-suite-exit-{}-{label}", std::process::id()));
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
        let (commands, commands_rx) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, snapshots) = rtrb::RingBuffer::new(RING);
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                drives: vec![drive(101, 0), drive(102, 1)],
                timing,
            },
            BusLinks {
                commands: commands_rx,
                snapshots: snapshots_tx,
                recorder: buses.remove(0),
                epoch,
                requests: rtrb::RingBuffer::new(1).1,
                results: rtrb::RingBuffer::new(1).0,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();
        let mut played = control(Control {
            commands,
            snapshots,
            epoch,
            exit: &exit,
            thread: &bus.thread,
        });
        let done = bus.thread.join().unwrap();
        if let Some(ring) = played.ring.as_mut() {
            while let Ok(s) = ring.pop() {
                played.read.push(s);
            }
        }
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
        Ended {
            held: played.held,
            read: played.read,
            last: done.last,
            error: done.error,
            recorded: recorded(&session_dir.join("0000.mcap")),
        }
    });
    let _ = std::fs::remove_dir_all(&dir);
    ended
}

/// Enable and hold both drives, then keep sending a fresh hold every tick while no longer reading, until control's
/// ring is full; then set `exit` with the bus still active, and do `after`.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a failed push fails the test"
)]
fn exit_with_a_full_ring(after: After) -> Ended {
    run_bus(&format!("full-ring-{after:?}"), timing(), |mut c| {
        let held = enable_and_hold(&mut c.commands, &mut c.snapshots, c.epoch);
        // Control stops reading but keeps the drives held: the bus publishes one snapshot a tick, so the ring's count
        // says which tick has ended, and the next batch is for the tick after it.
        let end = Instant::now() + Duration::from_secs(10);
        let mut queued = 0;
        while queued < RING {
            push_batch(
                &mut c.commands,
                c.epoch,
                held.tick + u64::try_from(queued).unwrap() + 1,
                holds(),
            );
            while c.snapshots.slots() == queued {
                assert!(Instant::now() < end, "the bus published nothing");
                std::thread::yield_now();
            }
            queued = c.snapshots.slots();
        }
        c.exit.store(true, Ordering::Release);
        let Control {
            mut snapshots,
            thread,
            ..
        } = c;
        match after {
            After::DropsRing => {
                drop(snapshots);
                wait_for_the_end(thread, None);
                Played {
                    held,
                    read: Vec::new(),
                    ring: None,
                }
            }
            After::Reads | After::NeverReads => {
                let reads = matches!(after, After::Reads).then_some(&mut snapshots);
                let read = wait_for_the_end(thread, reads);
                Played {
                    held,
                    read,
                    ring: Some(snapshots),
                }
            }
        }
    })
}

/// Play control on an idle bus that can't collect (`no_collect_timing`): hold both drives on a status neither has
/// given, so the batch check stops both limbs; set `exit` as soon as a snapshot shows the stops under way, long before
/// they end; and drop the ring.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a missing snapshot fails the test"
)]
fn exit_while_stopping() -> Ended {
    run_bus("stopping", no_collect_timing(), |mut c| {
        let end = Instant::now() + Duration::from_secs(10);
        let mut snap = next_snapshot(&mut c.snapshots, end).unwrap();
        while states(&snap) == [LimbState::Idle, LimbState::Idle] {
            push_batch(&mut c.commands, c.epoch, snap.tick + 1, holds());
            snap = next_snapshot(&mut c.snapshots, end).unwrap();
        }
        assert!(
            snap.limbs()
                .all(|(_, l)| matches!(l.state, LimbState::Stopping { .. })),
            "{snap:?}"
        );
        c.exit.store(true, Ordering::Release);
        let Control {
            snapshots, thread, ..
        } = c;
        drop(snapshots);
        wait_for_the_end(thread, None);
        Played {
            held: snap,
            read: Vec::new(),
            ring: None,
        }
    })
}

/// What every run shares: no error; a last snapshot with each limb stopped for its reason in `reasons`, and no bus
/// error; and exactly one tick recorded after it, the drain the thread returned at.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: no last snapshot fails the test"
)]
fn stopped_for(ended: &Ended, reasons: [StopReason; 2]) -> Snapshot {
    assert!(ended.error.is_none(), "{:?}", ended.error);
    let last = ended.last.unwrap();
    let limbs: Vec<_> = last.limbs().map(|(_, l)| (l.state, l.stop)).collect();
    assert_eq!(
        limbs,
        reasons.map(|r| (LimbState::Stopped, Some(r))),
        "{last:?}"
    );
    assert_eq!(last.bus_error, None, "{last:?}");
    let after: Vec<u64> = ended
        .recorded
        .iter()
        .map(|r| r.tick)
        .filter(|&tick| tick > last.tick)
        .collect();
    assert_eq!(
        after.len(),
        1,
        "the exit drain's tick, after {}: {after:?}",
        last.tick
    );
    last
}

/// Active limbs told to exit: each stopped by the exit's own stop, not ones control's silence had already stopped.
fn stopped_by_the_exit(ended: &Ended) -> Snapshot {
    stopped_for(ended, [StopReason::Requested; 2])
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
/// no snapshot is made after the first such one it takes, and the thread returns at the next tick's drain with that
/// snapshot as `BusExit::last`, not after a wait meant for a control that stopped reading (can.md section 2 Receive, "the drop is
/// counted and reported"; rust.md section 5, every thread's explicit stop path).
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
    // The wait: exactly one stop window, rounded up, of all-stopped snapshots, the first being the one the stops ended
    // in.
    let stopped = ended.stopped_at(&last);
    assert_eq!(ended.ran(stopped - 1, last.tick), EXIT_WAIT);
    // Every snapshot made after the ring filled was dropped, and counted: the last counts itself.
    assert_eq!(
        last.counters.snapshots_dropped - taken.counters.snapshots_dropped,
        ended.ran(taken.tick, last.tick)
    );
}

/// Guards: safety - a control that drops its end of the ring cannot hold the bus thread's join: told to exit, the thread
/// stops every limb, makes no snapshot after its first all-stopped one, and returns at the next tick's drain with that
/// snapshot as `BusExit::last`, without waiting the stop window for a reader that is gone (PLAN.md item 3, "A hung
/// control thread must let the drives time out"; rust.md section 5, every thread's explicit stop path).
#[test]
fn a_bus_told_to_exit_ends_at_once_when_control_drops_its_ring() {
    let ended = exit_with_a_full_ring(After::DropsRing);
    let last = stopped_by_the_exit(&ended);
    // The last snapshot is the first all-stopped one, not one after a wait for a reader that is gone.
    assert_eq!(last.tick, ended.stopped_at(&last));
}

/// Guards: protocol - nothing the bus thread handles disappears silently, its last slow results included: a bus told to
/// exit gives every request still in its ring its one result, and those control's full ring can't take, after any
/// snapshot could count them, are counted in what the thread hands back (can.md section 2: bounded everything, every
/// drop counted and reported).
#[test]
fn a_bus_that_ends_counts_the_slow_results_control_cant_take() {
    const ASKED: u32 = 3;
    ensure_vcan(BUS).unwrap();
    let dir = std::env::temp_dir().join(format!("sim-suite-slow-exit-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let session = Session::start(&dir, info(), 1_794_178_885_000_000_000).unwrap();
    let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
    let epoch = recording.epoch();
    let recorder = Recorder::spawn(recording).unwrap();
    let (mut requests_tx, requests) = rtrb::RingBuffer::new(4);
    for tag in 1..=ASKED {
        let request = SlowRequest {
            tag,
            slot: 0,
            kind: SlowKind::Read(Param::Vbus),
        };
        assert!(requests_tx.push(request).is_ok());
    }
    // Room for one result, which control never takes.
    let (results_tx, mut results) = rtrb::RingBuffer::new(1);
    // Told to exit before it starts, with its only limb idle: it ends at its first drain, before any snapshot.
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
            epoch,
            requests,
            results: results_tx,
            start: soon(),
            exit: Arc::new(AtomicBool::new(true)),
        },
    )
    .unwrap();
    let done = bus.thread.join().unwrap();
    assert!(done.error.is_none(), "{:?}", done.error);
    assert_eq!(done.last.map(|s| s.tick), None);
    assert_eq!(
        results.pop().ok(),
        Some(SlowResult {
            tag: 1,
            slot: 0,
            outcome: SlowOutcome::Refused(SlowRefusal::Ended),
        })
    );
    assert_eq!(done.slow_results_dropped, u64::from(ASKED - 1));
    recorder.close(vec![done.recorder]).unwrap();
    let _ = std::fs::remove_dir_all(&dir);
}

/// Guards: protocol - active reporting off, Exit sequence (PLAN.md item 2): every drive's reporting off reaches the
/// recording (logging.md section 8) even when the bus decides its exit on the tick that wrote the last one, after
/// that tick's collect deadline, so that its echo can be read only in the drain the thread returns at.
#[test]
fn the_stops_last_reporting_off_is_recorded_through_the_exit_drain() {
    let ended = exit_while_stopping();
    let expired = [0, 1].map(|slot| StopReason::ExpiredFeedback { slot });
    let held: Vec<_> = ended.held.limbs().map(|(_, l)| l.stop).collect();
    assert_eq!(held, expired.map(Some));
    let last = stopped_for(&ended, expired);
    // The exit was decided at the first all-stopped snapshot: control had set `exit` and dropped the ring long before.
    assert_eq!(last.tick, ended.stopped_at(&last));
    // Each drive's reporting off is recorded once, by its echo, and the last of them in the exit drain's tick, the one
    // after `last`: written after its own tick's collect deadline, it was read in no tick before.
    let off = |n| {
        let frame = encode::active_reporting(id(n), Reporting::Off);
        (frame.id(), frame.data().to_vec())
    };
    let mut offs: Vec<(u64, (u32, Vec<u8>))> = ended
        .recorded
        .iter()
        .flat_map(|r| r.echoes.iter().map(|f| (r.tick, (f.id, f.data.clone()))))
        .filter(|(_, echo)| *echo == off(101) || *echo == off(102))
        .collect();
    assert_eq!(
        offs.last().map(|(tick, _)| *tick),
        ended.recorded.last().map(|r| r.tick)
    );
    offs.sort_by(|a, b| a.1.cmp(&b.1));
    let drives: Vec<_> = offs.into_iter().map(|(_, echo)| echo).collect();
    let mut expected = vec![off(101), off(102)];
    expected.sort();
    assert_eq!(drives, expected);
}
