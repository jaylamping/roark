//! A session written from synthetic ticks reads back with the `mcap` crate's reader, as Foxglove or Python see it.

use std::io::{self, Cursor, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

use telemetry::wire::{
    Clock, Event as EventMessage, EventTotals, Frames, Gap, SessionRecord, Stamp,
};
use telemetry::{
    BusInfo, BusRecorder, Direction, Event, EventKind, FrameRecord, Level, MAX_FRAMES_PER_TICK,
    Recorder, Recording, Session, SessionInfo, Sink, SkeletonRef, Stage, TickBatch,
    TimestampSource,
};

/// 2026-11-08T12:34:56Z.
const START_NS: u64 = 1_794_141_296_000_000_000;
const TICK_NS: u64 = 4_000_000;

struct Dir(PathBuf);

impl Dir {
    fn new(name: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("telemetry-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap_or_else(|e| unreachable_io(&e));
        Self(dir)
    }
}

impl Drop for Dir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[expect(
    clippy::panic,
    reason = "test helper: a temp dir that can't be made fails the test"
)]
fn unreachable_io(e: &io::Error) -> ! {
    panic!("temp dir: {e}")
}

fn info(buses: &[&str]) -> SessionInfo {
    SessionInfo {
        git_revision: "0213129".to_owned(),
        operator: "test".to_owned(),
        stage: Stage::Vcan,
        skeleton: SkeletonRef {
            path: "config/skeleton.yaml".to_owned(),
            sha256: "00".repeat(32),
        },
        buses: buses
            .iter()
            .map(|name| BusInfo {
                name: (*name).to_owned(),
                bitrate: 1_000_000,
                timestamps: TimestampSource::Software,
                receive_filters: Vec::new(),
                error_filter: 0,
                adapter_firmware: None,
            })
            .collect(),
    }
}

fn frame(id: u32, stamp_ns: u64, direction: Direction) -> FrameRecord {
    FrameRecord {
        id,
        extended: true,
        error: false,
        remote: false,
        len: 8,
        data: [0x80, 0x00, 0x7F, 0xFF, 0x80, 0x01, 0x00, 0xFA],
        stamp_ns,
        direction,
    }
}

/// Tick `n`'s batch with one command and its reply.
fn tick(n: u64) -> TickBatch {
    let wall = START_NS + n * TICK_NS;
    let mut batch = TickBatch::new(n, n * TICK_NS, wall);
    assert!(batch.push(frame(0x0100_FD01, wall + 10_000, Direction::TxEcho)));
    assert!(batch.push(frame(0x0200_01FD, wall + 250_000, Direction::Rx)));
    batch
}

fn record(buses: &mut [BusRecorder], bus: usize, batch: &TickBatch) -> bool {
    buses.get_mut(bus).is_some_and(|b| b.record(*batch))
}

struct Read {
    topic: String,
    schema: String,
    encoding: String,
    log_time: u64,
    publish_time: u64,
    data: Vec<u8>,
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: an unreadable file fails the test"
)]
fn read(path: &Path) -> Vec<Read> {
    let bytes = std::fs::read(path).unwrap();
    mcap::MessageStream::new(&bytes)
        .unwrap()
        .map(|m| {
            let m = m.unwrap();
            let schema = m.channel.schema.as_ref().unwrap();
            assert_eq!(schema.encoding, "jsonschema");
            assert!(!schema.data.is_empty(), "every channel carries its schema");
            Read {
                topic: m.channel.topic.clone(),
                schema: schema.name.clone(),
                encoding: m.channel.message_encoding.clone(),
                log_time: m.log_time,
                publish_time: m.publish_time,
                data: m.data.into_owned(),
            }
        })
        .collect()
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a message that doesn't parse fails the test"
)]
fn parse<T: serde::de::DeserializeOwned>(m: &Read) -> T {
    serde_json::from_slice(&m.data).unwrap()
}

fn on<'a>(messages: &'a [Read], topic: &str) -> Vec<&'a Read> {
    messages.iter().filter(|m| m.topic == topic).collect()
}

/// Guards: protocol - the recording's shape (header, a message per bus per tick, /clock, end marker, session.json),
/// logging.md sections 3 and 8.
#[test]
fn a_session_reads_back_with_its_header_ticks_clock_and_end_marker() {
    let root = Dir::new("readback");
    let session = Session::start(&root.0, info(&["can0", "can1"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    assert_eq!(dir, root.0.join("2026-11-08T12:34:56Z"));
    assert!(
        dir.join("0000.mcap.lock").exists(),
        "the lock is there while the file is open"
    );

    let (mut recording, mut buses) = Recording::new(session, 500);
    for n in 0..300 {
        assert!(record(&mut buses, 0, &tick(n)));
        assert!(record(&mut buses, 1, &tick(n)));
        recording.step(n * TICK_NS, START_NS + n * TICK_NS).unwrap();
    }
    let summary = recording.close(buses, START_NS + 300 * TICK_NS).unwrap();
    assert_eq!(summary.buses.len(), 2);
    assert!(
        summary
            .buses
            .iter()
            .all(|b| b.batches == 300 && b.frames == 600 && b.batches_lost == 0)
    );

    assert!(
        !dir.join("0000.mcap.lock").exists(),
        "the lock goes after a clean close"
    );
    let messages = read(&dir.join("0000.mcap"));
    assert!(messages.iter().all(|m| m.encoding == "json"));

    let first = messages.first().unwrap();
    assert_eq!(first.topic, "/session");
    let SessionRecord::Header(header) = parse(first) else {
        unreachable_record("the first message is the header")
    };
    assert_eq!(header.session, "2026-11-08T12:34:56Z");
    assert_eq!(header.file, 0);
    assert_eq!(header.info, info(&["can0", "can1"]));

    let last = messages.last().unwrap();
    assert_eq!(last.topic, "/session");
    let SessionRecord::End(end) = parse(last) else {
        unreachable_record("the last message is the end marker")
    };
    assert_eq!(end.buses, summary.buses);

    for bus in ["can0", "can1"] {
        let ticks = on(&messages, &format!("/can/{bus}/frames"));
        assert_eq!(ticks.len(), 300);
        for (n, m) in (0u64..).zip(&ticks) {
            assert_eq!(m.schema, "roark.can.Frames");
            let frames: Frames = parse(m);
            assert_eq!(frames.tick, n);
            assert_eq!(
                m.publish_time,
                START_NS + n * TICK_NS,
                "publish_time is the tick's wall clock"
            );
            assert_eq!(
                m.log_time, m.publish_time,
                "so Foxglove replays ticks as they happened"
            );
            assert_eq!(frames.monotonic, Stamp::from_ns(n * TICK_NS));
            assert_eq!(frames.frames.len(), 2);
            let reply = frames.frames.get(1).unwrap();
            assert_eq!(reply.id, 0x0200_01FD);
            assert_eq!(reply.direction, Direction::Rx);
            assert_eq!(reply.data, [0x80, 0x00, 0x7F, 0xFF, 0x80, 0x01, 0x00, 0xFA]);
            assert_eq!(
                reply.stamp,
                Stamp::from_ns(START_NS + n * TICK_NS + 250_000)
            );
        }
    }

    // 300 ticks is 1.2 s: a clock record at the start and one a second later.
    let clocks = on(&messages, "/clock");
    assert_eq!(clocks.len(), 2);
    let clock: Clock = parse(clocks.get(1).unwrap());
    assert_eq!(clock.monotonic, Stamp::from_ns(250 * TICK_NS));
    assert_eq!(clock.wall, Stamp::from_ns(START_NS + 250 * TICK_NS));

    let json: serde_json::Value =
        serde_json::from_slice(&std::fs::read(dir.join("session.json")).unwrap()).unwrap();
    assert_eq!(json["session"], "2026-11-08T12:34:56Z");
    assert_eq!(json["git_revision"], "0213129");
    assert_eq!(json["stage"], "vcan");
    assert_eq!(json["buses"][1]["name"], "can1");
    assert_eq!(
        json["buses"][1]["adapter_firmware"],
        serde_json::Value::Null
    );
}

#[expect(clippy::panic, reason = "test helper: the wrong record fails the test")]
fn unreachable_record(what: &str) -> ! {
    panic!("{what}")
}

/// Guards: protocol - a full ring drops the newest batch and leaves a gap record where the hole is, logging.md 8.4.
#[test]
fn a_full_ring_leaves_a_gap_in_the_file_and_recovers() {
    let root = Dir::new("gap");
    let session = Session::start(&root.0, info(&["can0"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    let (mut recording, mut buses) = Recording::new(session, 2);

    assert!(record(&mut buses, 0, &tick(0)));
    assert!(record(&mut buses, 0, &tick(1)));
    assert!(
        !record(&mut buses, 0, &tick(2)),
        "a full ring drops the newest batch"
    );
    assert!(!record(&mut buses, 0, &tick(3)));
    recording.step(0, START_NS).unwrap();
    assert!(
        record(&mut buses, 0, &tick(4)),
        "the ring took batches again once drained"
    );
    recording.step(TICK_NS, START_NS + TICK_NS).unwrap();
    let summary = recording.close(buses, START_NS + 5 * TICK_NS).unwrap();

    let bus = summary.buses.first().unwrap();
    assert_eq!((bus.batches, bus.batches_lost, bus.frames_lost), (3, 2, 4));
    let messages = read(&dir.join("0000.mcap"));
    let topics: Vec<_> = messages
        .iter()
        .filter(|m| m.topic != "/clock" && m.topic != "/session")
        .map(|m| m.topic.as_str())
        .collect();
    assert_eq!(
        topics,
        [
            "/can/can0/frames",
            "/can/can0/frames",
            "/recorder/gap",
            "/can/can0/frames"
        ],
        "the gap sits where the hole is"
    );
    let gap: Gap = parse(on(&messages, "/recorder/gap").first().unwrap());
    assert_eq!(
        (
            gap.bus.as_str(),
            gap.batches,
            gap.frames,
            gap.first_tick,
            gap.last_tick
        ),
        ("can0", 2, 4, 2, 3)
    );
}

/// Guards: protocol - control's events go to `/event` with their kind, their limb, joint and bus by name, their rule,
/// and a wall time mapped from their monotonic one, before or after the clocks were read; events a full ring dropped are counted in the end marker, and the events still
/// in the ring at close are written (safety.md section 8, logging.md section 8.4).
#[test]
fn control_events_are_written_by_name_and_their_losses_counted() {
    let root = Dir::new("events");
    let session = Session::start(&root.0, info(&["can0", "can1"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    let (mut recording, buses) = Recording::new(session, 2);
    let mut events = recording.events(vec!["shoulder".to_owned(), "elbow".to_owned()], 2);
    let stop = Event {
        mono_ns: 3 * TICK_NS,
        level: Level::Error,
        kind: EventKind::LimbStopped,
        limb: Some("left_arm"),
        joint: Some(1),
        bus: Some(1),
        rule: Some("host.mode"),
        reason: None,
        tag: Some(7),
    };
    recording.step(5 * TICK_NS, START_NS + 5 * TICK_NS).unwrap();
    assert!(events.record(stop));
    assert!(events.record(Event {
        kind: EventKind::EnableSucceeded,
        level: Level::Info,
        ..stop
    }));
    assert!(!events.record(stop), "a full ring drops the event");
    recording.step(6 * TICK_NS, START_NS + 6 * TICK_NS).unwrap();
    assert!(events.record(Event {
        kind: EventKind::LimbCleared,
        // Newer than the recorder's last reading of the clocks.
        mono_ns: 8 * TICK_NS,
        joint: None,
        bus: None,
        rule: None,
        ..stop
    }));
    let summary = recording.close(buses, START_NS + 7 * TICK_NS).unwrap();

    assert_eq!(
        summary.events,
        EventTotals {
            written: 3,
            lost: 1
        }
    );
    let messages = read(&dir.join("0000.mcap"));
    let written: Vec<EventMessage> = on(&messages, "/event").into_iter().map(parse).collect();
    let first = written.first().unwrap();
    assert_eq!(
        (
            first.kind,
            first.limb.as_deref(),
            first.joint.as_deref(),
            first.bus.as_deref(),
            first.rule.as_deref(),
            first.tag,
            first.level,
        ),
        (
            EventKind::LimbStopped,
            Some("left_arm"),
            Some("elbow"),
            Some("can1"),
            Some("host.mode"),
            Some(7),
            Level::Error
        )
    );
    assert_eq!(first.monotonic, Stamp::from_ns(3 * TICK_NS));
    assert_eq!(
        first.wall,
        Stamp::from_ns(START_NS + 3 * TICK_NS),
        "mapped through the clocks"
    );
    let kinds: Vec<_> = written.iter().map(|e| e.kind).collect();
    assert_eq!(
        kinds,
        [
            EventKind::LimbStopped,
            EventKind::EnableSucceeded,
            EventKind::LimbCleared
        ]
    );
    let last = written.last().unwrap();
    assert_eq!(last.joint, None);
    assert_eq!(
        last.wall,
        Stamp::from_ns(START_NS + 8 * TICK_NS),
        "an event after the clock reading is mapped forward, not clamped to it"
    );
}

/// Guards: protocol - loss right before a stop is still written as a gap, logging.md section 8.4.
#[test]
fn batches_dropped_just_before_a_stop_are_still_in_the_file() {
    let root = Dir::new("stop");
    let session = Session::start(&root.0, info(&["can0"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    let (recording, mut buses) = Recording::new(session, 1);

    assert!(record(&mut buses, 0, &tick(0)));
    assert!(!record(&mut buses, 0, &tick(1)));
    assert!(!record(&mut buses, 0, &tick(2)));
    let summary = recording.close(buses, START_NS + 3 * TICK_NS).unwrap();

    let bus = summary.buses.first().unwrap();
    assert_eq!((bus.batches, bus.batches_lost, bus.frames_lost), (1, 2, 4));
    let messages = read(&dir.join("0000.mcap"));
    let gap: Gap = parse(on(&messages, "/recorder/gap").first().unwrap());
    assert_eq!((gap.batches, gap.first_tick, gap.last_tick), (2, 1, 2));
    assert_eq!(
        on(&messages, "/session").len(),
        2,
        "the gap is written before the end marker"
    );
    assert_eq!(messages.last().unwrap().topic, "/session");
}

/// Guards: protocol - frames past a batch's capacity are counted in the file, logging.md section 8.4.
#[test]
fn frames_past_a_ticks_capacity_are_counted_not_lost_silently() {
    let root = Dir::new("burst");
    let session = Session::start(&root.0, info(&["can0"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    let (recording, mut buses) = Recording::new(session, 4);

    let mut batch = TickBatch::new(0, 0, START_NS);
    let pushed = (0..MAX_FRAMES_PER_TICK + 6)
        .filter(|&k| batch.push(frame(0x0200_01FD, START_NS + k as u64, Direction::Rx)))
        .count();
    assert_eq!(pushed, MAX_FRAMES_PER_TICK);
    assert_eq!(batch.omitted(), 6);
    assert!(record(&mut buses, 0, &batch));
    let summary = recording.close(buses, START_NS + TICK_NS).unwrap();

    assert_eq!(summary.buses.first().unwrap().frames_omitted, 6);
    let messages = read(&dir.join("0000.mcap"));
    let frames: Frames = parse(on(&messages, "/can/can0/frames").first().unwrap());
    assert_eq!(
        (frames.frames.len(), frames.omitted),
        (MAX_FRAMES_PER_TICK, 6)
    );
}

/// Guards: protocol - stamps are exact for JSON readers that parse numbers as doubles, units-and-frames.md section 5.
#[test]
fn stamps_one_nanosecond_apart_stay_apart_in_the_json() {
    let root = Dir::new("stamps");
    let session = Session::start(&root.0, info(&["can0"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    let (recording, mut buses) = Recording::new(session, 4);

    let mut batch = TickBatch::new(0, 0, START_NS);
    assert!(batch.push(frame(1, START_NS + 1, Direction::Rx)));
    assert!(batch.push(frame(2, START_NS + 2, Direction::Rx)));
    assert!(record(&mut buses, 0, &batch));
    recording.close(buses, START_NS + TICK_NS).unwrap();

    let messages = read(&dir.join("0000.mcap"));
    let text = String::from_utf8(
        on(&messages, "/can/can0/frames")
            .first()
            .unwrap()
            .data
            .clone(),
    )
    .unwrap();
    // A JSON reader that parses numbers as doubles (JavaScript, so Foxglove) can't tell 1794141296000000001 from
    // ...002; seconds and nanoseconds as separate fields stay exact.
    assert!(
        text.contains(r#""stamp":{"sec":1794141296,"nsec":1}"#),
        "{text}"
    );
    assert!(
        text.contains(r#""stamp":{"sec":1794141296,"nsec":2}"#),
        "{text}"
    );
}

/// A file that takes `budget` bytes and then fails every write, or fails only its final sync.
struct Failing {
    inner: Cursor<Vec<u8>>,
    budget: usize,
    fail_sync: bool,
}

impl Write for Failing {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        if buf.len() > self.budget {
            return Err(io::Error::other("disk full"));
        }
        self.budget -= buf.len();
        self.inner.write(buf)
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

impl Seek for Failing {
    fn seek(&mut self, pos: SeekFrom) -> io::Result<u64> {
        self.inner.seek(pos)
    }
}

impl Sink for Failing {
    fn sync(&mut self) -> io::Result<()> {
        if self.fail_sync {
            Err(io::Error::other("fsync failed"))
        } else {
            Ok(())
        }
    }
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper: a session that can't start fails the test"
)]
fn failing(
    root: &Path,
    budget: usize,
    fail_sync: bool,
) -> (Recording<Failing>, Vec<BusRecorder>, PathBuf) {
    let session = Session::start_with(root, info(&["can0"]), START_NS, |_| {
        Ok(Failing {
            inner: Cursor::new(Vec::new()),
            budget,
            fail_sync,
        })
    })
    .unwrap();
    let lock = session.dir().join("0000.mcap.lock");
    let (recording, buses) = Recording::new(session, 500);
    (recording, buses, lock)
}

/// Guards: safety - a recording that can't be written refuses the next enable (PLAN item 6, Logging row).
#[test]
fn a_write_that_fails_mid_session_marks_the_recording_failed_and_keeps_the_lock() {
    let root = Dir::new("write-fails");
    // Room for the header but not the first chunk.
    let (mut recording, mut buses, lock) = failing(&root.0, 128, false);
    let health = recording.health();
    assert!(!health.failed());

    let mut stepped = Ok(());
    for n in 0..300 {
        assert!(
            record(&mut buses, 0, &tick(n)),
            "the bus side never sees the failure as a full ring"
        );
        stepped = stepped.and(recording.step(n * TICK_NS, START_NS + n * TICK_NS));
    }
    assert!(
        stepped.is_err(),
        "the chunk closed after a second can't be written"
    );
    assert!(health.failed(), "the enable gate sees it");
    assert!(recording.close(buses, START_NS + 300 * TICK_NS).is_err());
    assert!(
        lock.exists(),
        "a file that didn't close cleanly keeps its lock"
    );
}

/// Guards: safety - a file that didn't close cleanly is never marked clean (PLAN item 6 Logging row, logging.md 8.5).
#[test]
fn a_close_that_cant_finish_or_sync_is_an_error_and_keeps_the_lock() {
    for (budget, fail_sync) in [(128, false), (usize::MAX, true)] {
        let root = Dir::new(if fail_sync {
            "sync-fails"
        } else {
            "finish-fails"
        });
        let (mut recording, mut buses, lock) = failing(&root.0, budget, fail_sync);
        for n in 0..10 {
            assert!(record(&mut buses, 0, &tick(n)));
            recording.step(n * TICK_NS, START_NS + n * TICK_NS).unwrap();
        }
        let health = recording.health();
        assert!(
            recording.close(buses, START_NS + 10 * TICK_NS).is_err(),
            "budget {budget}, sync {fail_sync}"
        );
        assert!(health.failed());
        assert!(lock.exists());
    }
}

/// Guards: protocol - closing the recorder writes every batch the buses handed it, logging.md section 8.4.
#[test]
fn the_recorder_thread_writes_every_batch_it_was_given_by_close() {
    let root = Dir::new("thread");
    let session = Session::start(&root.0, info(&["can0"]), START_NS).unwrap();
    let dir = session.dir().to_owned();
    let (recording, mut buses) = Recording::new(session, 500);
    let recorder = Recorder::spawn(recording).unwrap();
    assert!(!recorder.health().failed());
    for n in 0..200 {
        assert!(record(&mut buses, 0, &tick(n)));
    }
    let summary = recorder.close(buses).unwrap();

    assert_eq!(summary.buses.first().unwrap().batches, 200);
    let messages = read(&dir.join("0000.mcap"));
    assert_eq!(on(&messages, "/can/can0/frames").len(), 200);
    assert!(!dir.join("0000.mcap.lock").exists());
}
