//! The bus loop on `vcan` against `sim-drive`, recorded from its first frame, and the recording checked frame by frame
//! against an independent `candump -L -x` capture of the same bus (logging.md section 8.6).
#![cfg(target_os = "linux")]

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusLinks, BusRunError, BusState, CommandBatch, Snapshot, StopOutcome, StopReason,
    Timing,
};
use robstride::{
    DeviceId, Drive, Frame, Inbound, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad,
    RadPerSec, Radians, Uid, decode, encode,
};
use sim_drive::{SimDrive, ensure_vcan, serve};
use socketcan::{CanDataFrame, CanSocket, EmbeddedFrame, Socket, StandardId};
use telemetry::wire::Frames;
use telemetry::{Direction, Epoch, Recorder, Recording, Session, SessionInfo, SkeletonRef, Stage};

/// A bus no other sim test uses.
const BUS: &str = "can2";
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
/// The marker sent until `candump` has it, so the capture is known to cover the whole run.
const MARKER: u16 = 0x7AB;

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

struct Candump {
    child: Child,
    log: PathBuf,
}

impl Drop for Candump {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// The marker frame, all bytes `fill`.
#[expect(clippy::unwrap_used, reason = "test helper: the marker must go out")]
fn marker(fill: u8) {
    let frame = CanDataFrame::new(StandardId::new(MARKER).unwrap(), &[fill; 8]).unwrap();
    CanSocket::open(BUS).unwrap().write_frame(&frame).unwrap();
}

/// `candump -L -x` on `BUS`, returned once it has captured the marker.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the capture must start for the test to mean anything"
)]
fn candump(dir: &Path) -> Candump {
    let log = dir.join("candump.log");
    let child = Command::new("candump")
        .args(["-L", "-x", BUS])
        .stdout(std::fs::File::create(&log).unwrap())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let dump = Candump { child, log };

    let end = Instant::now() + Duration::from_secs(10);
    while !std::fs::read_to_string(&dump.log)
        .unwrap()
        .contains(&format!("{MARKER:03X}#"))
    {
        assert!(Instant::now() < end, "candump never captured the marker");
        marker(0);
        // Waiting on an outside process with a deadline (testing.md rule 6), not a fixed nap.
        std::thread::yield_now();
    }
    dump
}

/// One captured frame: microseconds, ID, data, and whether candump marked it sent from this host.
#[derive(Clone, Debug, PartialEq, Eq)]
struct Line {
    us: u64,
    id: u32,
    data: Vec<u8>,
    local: bool,
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a malformed capture fails the test"
)]
fn parse(line: &str) -> Line {
    // (1794178885.091393) can2 0100FD0B#0011223344556677 T
    let mut parts = line.split_whitespace();
    let stamp = parts.next().unwrap().trim_matches(['(', ')']);
    let (sec, usec) = stamp.split_once('.').unwrap();
    let _bus = parts.next().unwrap();
    let (id, data) = parts.next().unwrap().split_once('#').unwrap();
    let flag = parts.next().unwrap();
    Line {
        us: sec.parse::<u64>().unwrap() * 1_000_000 + usec.parse::<u64>().unwrap(),
        id: u32::from_str_radix(id, 16).unwrap(),
        data: (0..data.len() / 2)
            .map(|i| u8::from_str_radix(&data[2 * i..2 * i + 2], 16).unwrap())
            .collect(),
        local: flag == "T",
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

/// Play control for the whole run, one batch per tick for the tick after the snapshot just read: enable both drives
/// until both report Run, hold for `HOLD_TICKS`, then set `exit` as the runtime does at shutdown and see the bus stop
/// the drives: both confirm Reset and take active reporting off.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a missing snapshot fails the test"
)]
fn play_control(
    commands_tx: &mut rtrb::Producer<CommandBatch>,
    snapshots: &mut rtrb::Consumer<Snapshot>,
    epoch: Epoch,
    exit: &AtomicBool,
) {
    // Play control: one batch per tick, for the tick after the snapshot just read.
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
        assert_eq!(snap.state, BusState::Active, "{snap:?}");
        answered += snap.drives().filter(|d| d.answered).count();
    }
    // One tick of slack: the test thread playing control may miss one tick on a loaded runner (two would stop the bus).
    assert!(
        answered >= 2 * (HOLD_TICKS - 1),
        "answered {answered} of {}",
        2 * HOLD_TICKS
    );
    // Shutdown while active: the thread stops the drives before it returns.
    exit.store(true, Ordering::Release);
    while snap.state != BusState::Stopped {
        snap = next_snapshot(snapshots, end).unwrap();
    }
    assert_eq!(snap.stop, Some(StopReason::Requested));
    assert!(
        snap.drives()
            .all(|d| d.stop == StopOutcome::Confirmed && d.reporting_off_sent),
        "{snap:?}"
    );
    assert!(snap.healthy && snap.bus_error.is_none(), "{snap:?}");
    assert_eq!(snap.counters.foreign_host, 0);
}

/// Sets both stop flags when dropped, including while a failed assertion unwinds.
struct Shutdown<'a>(&'a AtomicBool, Arc<AtomicBool>);

impl Drop for Shutdown<'_> {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
        self.1.store(true, Ordering::Release);
    }
}

/// Guards: safety - the bus layer opens nothing but `vcan` until the real adapter's checks exist, so a sim test or a
/// mistaken name can't put frames on a real bus (PLAN step 8; testing.md rule 8).
#[test]
fn spawn_refuses_anything_but_vcan() {
    let root = std::env::temp_dir().join(format!("sim-suite-refuse-{}", std::process::id()));
    for (start_s, bus, vcan_kind_read) in
        [(1, "lo", true), (2, "nosuchbus0", false), (3, "-v", false)]
    {
        let (_, commands) = rtrb::RingBuffer::new(1);
        let (snapshots, _) = rtrb::RingBuffer::new(1);
        // A session directory is named by its start time, so each case starts at its own second.
        let session = Session::start(&root, info(), start_s * 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, 1);
        let refused = can::spawn(
            BusConfig {
                name: bus.to_owned(),
                drives: vec![id(101)],
                timing: timing(),
            },
            BusLinks {
                commands,
                snapshots,
                recorder: buses.remove(0),
                epoch: recording.epoch(),
                exit: Arc::new(AtomicBool::new(false)),
            },
        );
        let kind = match &refused {
            Err(BusRunError::NotVcan { .. }) => Some(true),
            Err(BusRunError::Unchecked { .. }) => Some(false),
            _ => None,
        };
        assert_eq!(kind, Some(vcan_kind_read), "{bus}: {refused:?}");
    }
    let _ = std::fs::remove_dir_all(&root);
}

/// Guards: protocol - nothing the bus thread handles disappears silently: a snapshot control's full ring can't take is
/// counted, and frames the exit tick's drain read are still recorded (can.md section 2 "every drop counted";
/// logging.md section 8.2).
#[test]
fn an_idle_bus_counts_dropped_snapshots_and_records_its_exit_drain() {
    const IDLE_BUS: &str = "can3";
    const LAST: u16 = 0x123;
    ensure_vcan(IDLE_BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-idle-{}", std::process::id()));
    let mut info = info();
    info.buses[0] = can::bus_info(IDLE_BUS, 1_000_000);
    let session = Session::start(&root, info, 1_000_000_000).unwrap();
    let session_dir = session.dir().to_owned();
    let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
    let epoch = recording.epoch();
    let recorder = Recorder::spawn(recording).unwrap();
    let (_commands_tx, commands) = rtrb::RingBuffer::new(1);
    // Room for one snapshot: while the test doesn't read, every later one is dropped.
    let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(1);
    let exit = Arc::new(AtomicBool::new(false));
    let bus = can::spawn(
        BusConfig {
            name: IDLE_BUS.to_owned(),
            drives: vec![id(101)],
            timing: timing(),
        },
        BusLinks {
            commands,
            snapshots: snapshots_tx,
            recorder: buses.remove(0),
            epoch,
            exit: Arc::clone(&exit),
        },
    )
    .unwrap();
    let _shutdown = Shutdown(&AtomicBool::new(false), Arc::clone(&exit));

    // Read a snapshot only every few periods, until one counts the drops in between.
    let end = Instant::now() + Duration::from_secs(10);
    let mut last_read = Instant::now();
    let dropped = loop {
        assert!(Instant::now() < end, "no snapshot counted a drop");
        if last_read.elapsed() < Duration::from_millis(30) {
            std::thread::yield_now();
            continue;
        }
        last_read = Instant::now();
        if let Ok(s) = snapshots.pop()
            && s.counters.snapshots_dropped > 0
        {
            break s;
        }
    };
    assert_eq!(dropped.state, BusState::Idle);

    // A frame on the bus, then the exit: the thread reads the frame (in this tick's collect or the next drain), sees
    // `exit` after a drain, records that drain's batch and returns.
    let frame = CanDataFrame::new(StandardId::new(LAST).unwrap(), &[7; 8]).unwrap();
    CanSocket::open(IDLE_BUS)
        .unwrap()
        .write_frame(&frame)
        .unwrap();
    exit.store(true, Ordering::Release);
    let done = bus.thread.join().unwrap();
    assert!(done.error.is_none(), "{:?}", done.error);
    let last_snapshot = done.last.map(|s| s.tick).unwrap();
    recorder.close(vec![done.recorder]).unwrap();

    let bytes = std::fs::read(session_dir.join("0000.mcap")).unwrap();
    let mut seen = false;
    let mut last_batch = None;
    for message in mcap::MessageStream::new(&bytes).unwrap() {
        let message = message.unwrap();
        if message.channel.topic == format!("/can/{IDLE_BUS}/frames") {
            let frames: Frames = serde_json::from_slice(&message.data).unwrap();
            seen |= frames.frames.iter().any(|f| f.id == u32::from(LAST));
            last_batch = Some(frames.tick);
        }
    }
    assert!(seen, "the frame is in the recording");
    assert!(
        last_batch.is_some_and(|t| t > last_snapshot),
        "the exit drain, after the last snapshot (tick {last_snapshot}), is recorded: last batch {last_batch:?}"
    );
    let _ = std::fs::remove_dir_all(&root);
}

/// Guards: safety - the bus loop runs PLAN.md item 3's tick on a real socket: enable, hold, and a control stop that
/// disables every drive, with the drives confirming Reset (PLAN.md item 2 Stop).
/// Guards: protocol - every frame the bus thread read is in the MCAP with its kernel timestamp and direction, and an
/// independent candump capture agrees frame for frame (logging.md section 8.6).
#[test]
fn the_bus_loop_runs_against_sim_drive_and_its_recording_matches_candump() {
    ensure_vcan(BUS).unwrap();
    let dir = std::env::temp_dir().join(format!("sim-suite-bus-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();

    // The drives.
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        // A failed assertion still stops the drives' thread and the bus, so the test fails instead of hanging.
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [
                SimDrive::new(Drive::new(id(101), Model::Rs03), Uid([1; 8]), 5),
                SimDrive::new(Drive::new(id(102), Model::Rs03), Uid([2; 8]), 6),
            ];
            serve(BUS, &mut drives, &stop_sim)
        });
        let dump = candump(&dir);

        // The recorder and the bus.
        let session = Session::start(&dir, info(), 1_794_178_885_000_000_000).unwrap();
        let session_dir = session.dir().to_owned();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (mut commands_tx, commands_rx) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(64);
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                drives: vec![id(101), id(102)],
                timing: timing(),
            },
            BusLinks {
                commands: commands_rx,
                snapshots: snapshots_tx,
                recorder: buses.remove(0),
                epoch,
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();
        assert!(bus.receive_buffer_bytes > 0);

        play_control(&mut commands_tx, &mut snapshots, epoch, &exit);

        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
        // Give candump the bus's last frames: it has read everything once it shows a second marker.
        marker(1);
        let wait = Instant::now() + Duration::from_secs(10);
        while !std::fs::read_to_string(&dump.log)
            .unwrap()
            .contains(&format!("{MARKER:03X}#0101"))
        {
            assert!(Instant::now() < wait, "candump never caught up");
            std::thread::yield_now();
        }
        let captured = captured_run(&dump.log);
        drop(dump);
        compare(&session_dir.join("0000.mcap"), &captured);
    });
    let _ = std::fs::remove_dir_all(&dir);
}

/// The capture between the two markers.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: an unreadable capture fails the test"
)]
fn captured_run(log: &Path) -> Vec<Line> {
    let lines: Vec<String> = BufReader::new(std::fs::File::open(log).unwrap())
        .lines()
        .map(Result::unwrap)
        .collect();
    let start = lines
        .iter()
        .rposition(|l| l.contains(&format!("{MARKER:03X}#0000")))
        .unwrap();
    lines
        .iter()
        .skip(start + 1)
        .take_while(|l| !l.contains(&format!("{MARKER:03X}#0101")))
        .map(|l| parse(l))
        .collect()
}

/// Every frame in the MCAP against the capture, in timestamp order: same count, ID, data, direction class and
/// microsecond.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: an unreadable recording fails the test"
)]
fn compare(mcap: &Path, captured: &[Line]) {
    let bytes = std::fs::read(mcap).unwrap();
    let mut recorded = Vec::new();
    for message in mcap::MessageStream::new(&bytes).unwrap() {
        let message = message.unwrap();
        if message.channel.topic != format!("/can/{BUS}/frames") {
            continue;
        }
        let frames: Frames = serde_json::from_slice(&message.data).unwrap();
        assert_eq!(
            (frames.omitted, frames.valid),
            (0, true),
            "tick {}",
            frames.tick
        );
        recorded.extend(frames.frames);
    }
    // Each hold tick alone puts two commands and two replies on the bus.
    assert!(
        captured.len() >= 4 * HOLD_TICKS,
        "candump caught only {} frames",
        captured.len()
    );
    assert_eq!(
        recorded.len(),
        captured.len(),
        "frame counts: MCAP {} vs candump {}",
        recorded.len(),
        captured.len()
    );
    // Each socket gets the bus's frames in its own order: a frame sent from sim-drive's socket and one sent from the
    // bus thread's within a microsecond can reach candump and the bus thread the other way round. Both carry the
    // kernel's timestamp, so both sides are compared in timestamp order (ties by ID and data, the same on both).
    let us = |r: &telemetry::wire::Frame| r.stamp.sec * 1_000_000 + u64::from(r.stamp.nsec / 1000);
    recorded.sort_by(|a, b| (us(a), a.id, &a.data).cmp(&(us(b), b.id, &b.data)));
    let mut captured = captured.to_vec();
    captured.sort_by(|a, b| (a.us, a.id, &a.data).cmp(&(b.us, b.id, &b.data)));
    for (r, c) in recorded.iter().zip(&captured) {
        let us = us(r);
        assert_eq!((r.id, &r.data, us), (c.id, &c.data, c.us), "{r:?} vs {c:?}");
        // On vcan everything is sent from this host: candump marks it T. The recorder tells ours from sim-drive's.
        assert_eq!(c.local, r.direction != Direction::Rx);
        let host_frame = matches!(decode(r.id, &r.data), Ok(Inbound::Echo(_)));
        assert_eq!(
            r.direction == Direction::TxEcho,
            host_frame,
            "{r:?}: our echoes are exactly the host frames"
        );
    }
}
