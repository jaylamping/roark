//! The bus loop on `vcan` against `sim-drive`, recorded from its first frame, and the recording checked frame by frame
//! against an independent `candump -L -x` capture of the same bus (logging.md section 8.6).
#![cfg(target_os = "linux")]

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{BusConfig, BusLinks, BusState, CommandBatch, Snapshot, StopOutcome, Timing};
use robstride::{
    DeviceId, Drive, Frame, Inbound, MitCommand, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad,
    RadPerSec, Radians, Uid, decode, encode,
};
use sim_drive::{SimDrive, ensure_vcan, serve};
use socketcan::{CanDataFrame, CanSocket, EmbeddedFrame, Socket, StandardId};
use telemetry::wire::Frames;
use telemetry::{
    BusInfo, Direction, Epoch, Recorder, Recording, Session, SessionInfo, SkeletonRef, Stage,
    TimestampSource,
};

/// A bus no other sim test uses.
const BUS: &str = "can2";
/// Slow enough that the test thread, playing control, makes every tick on a loaded machine.
const HZ: u64 = 50;
const HOLD_TICKS: usize = 50;
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
        buses: vec![BusInfo {
            name: BUS.to_owned(),
            bitrate: 1_000_000,
            timestamps: TimestampSource::Software,
            receive_filters: Vec::new(),
            error_filter: u32::MAX,
            adapter_firmware: None,
        }],
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
#[derive(Debug, PartialEq, Eq)]
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
/// until both report Run, hold for `HOLD_TICKS`, then go silent and see the bus stop with both drives confirming Reset.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: a missing snapshot fails the test"
)]
fn play_control(
    commands_tx: &mut rtrb::Producer<CommandBatch>,
    snapshots: &mut rtrb::Consumer<Snapshot>,
    epoch: Epoch,
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
            [Some(encode::enable(id(11))), Some(encode::enable(id(12)))],
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
        send(&snap, [Some(hold(11)), Some(hold(12))]);
        snap = next_snapshot(snapshots, end).unwrap();
        assert_eq!(snap.state, BusState::Active, "{snap:?}");
        answered += snap.drives().filter(|d| d.answered).count();
    }
    assert!(
        answered >= 2 * (HOLD_TICKS - 1),
        "answered {answered} of {}",
        2 * HOLD_TICKS
    );
    // Control goes silent: within two ticks the bus stops, and both drives confirm Reset.
    let silent_at = snap.tick;
    while !matches!(snap.state, BusState::Stopping { .. } | BusState::Stopped) {
        snap = next_snapshot(snapshots, end).unwrap();
    }
    assert!(
        snap.tick <= silent_at + 2,
        "stopped at tick {} after silence at {silent_at}",
        snap.tick
    );
    while snap.state != BusState::Stopped {
        snap = next_snapshot(snapshots, end).unwrap();
    }
    assert!(
        snap.drives().all(|d| d.stop == StopOutcome::Confirmed),
        "{snap:?}"
    );
    assert_eq!(snap.counters.foreign_host, 0);
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
    std::thread::scope(|scope| {
        let sim = scope.spawn(|| {
            let mut drives = [
                SimDrive::new(Drive::new(id(11), Model::Rs03), Uid([1; 8]), 5),
                SimDrive::new(Drive::new(id(12), Model::Rs03), Uid([2; 8]), 6),
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
        let exit = Arc::new(AtomicBool::new(false));
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                drives: vec![id(11), id(12)],
                timing: Timing::at_hz(HZ),
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

        play_control(&mut commands_tx, &mut snapshots, epoch);

        exit.store(true, Ordering::Release);
        let done = bus.join().unwrap();
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

/// Every frame in the MCAP, in order, against the capture: same count, ID, data, direction class and microsecond.
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
        assert_eq!(frames.omitted, 0);
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
    for (r, c) in recorded.iter().zip(captured) {
        let us = r.stamp.sec * 1_000_000 + u64::from(r.stamp.nsec / 1000);
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
