# telemetry

The session recorder: every bus tick's CAN frames go into one MCAP file per session, and the bus threads never wait on it
(PLAN "Observability", logging.md sections 3 and 8).

## What it does

Each bus thread holds a `BusRecorder` and hands it one `TickBatch` per tick: a fixed-size `Copy` slot of up to 64
`FrameRecord`s, pushed onto that bus's lock-free `rtrb` ring (two seconds of ticks). One recorder thread (`Recorder`)
drains every ring into the session's file:

- `/can/<bus>/frames`: one message per bus per tick, with every frame, its kernel timestamp and its direction.
- `/recorder/gap`: batches a full ring dropped, written where the hole is, including any dropped just before a stop.
- `/clock`: the monotonic and wall clocks read together, once a second.
- `/event`: control's events (stops with their rule, enables, refused enables, clears; kinds from `EventKind`), from
  its own lock-free ring (`Recording::events` hands out its `EventRecorder`). Each carries its monotonic time and its
  wall time, mapped through the recorder's newest reading of the two clocks together (taken each drain, every 10 ms,
  and once more at close; `/clock` records one a second, so a reader mapping from `/clock` agrees to within the clocks'
  drift). Joints and buses are written by name. A full ring drops the event and counts it.
- `/session`: a header first (session, file number, git revision, skeleton hash, buses with their filters and
  timestamp source) and an end marker last (per-bus totals of what was written, lost and omitted, and the events written
  and lost).

Messages are JSON, and each channel's JSON Schema is generated from the types in `telemetry::wire` and stored in the
file, so Foxglove and Python read it without this code. Times inside messages are `{sec, nsec}`, so they stay exact.
Both MCAP times of a message are when it happened at the source, which lets Foxglove replay ticks as they happened.
Chunks are zstd-compressed, closed every second or at 4 MB, and carry checksums.

A session is a directory `<root>/<UTC start>/` (for example `2026-11-08T12:34:56Z`) holding `session.json` and
`0000.mcap`. `0000.mcap.lock` sits beside the file until it has closed cleanly: the end marker is written, the file is
finished and `fsync`ed, and only then is the lock removed. A file with a lock left over, or without an end marker, was
cut off.

## Must never

Block, lock, allocate or make a system call on a bus thread or the control thread (`BusRecorder::record` and
`EventRecorder::record` are a ring push and a counter). Sit in
the stop path: a slow or failed disk never delays a stop. A write error marks `Health` failed, which refuses the next
enable and leaves running motion alone (PLAN item 6, Logging row). Drop data without saying so in the file.

## Talks to

Nothing in the workspace; it depends only on outside crates (`mcap`, `rtrb`, `serde`, `schemars`, `sha2`). Its users
are the bus layer (`can`), whose bus threads hold the `BusRecorder`s, and the runtime, which starts the session and the
`Recorder` and reads its `Health` before taking each enable. The sim suite also starts a `Recorder` of its own for the bus
tests. See the [map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

Start a `Session`, make its rings with `Recording::new`, and give each bus thread its `BusRecorder`. Run the recording
on its thread with `Recorder::spawn`, or step it by hand in a test. Close it once the drives are disabled: handing the
`BusRecorder`s back to `close` means no bus can record after that.

```rust
use telemetry::{
    BusInfo, Direction, FrameRecord, RecordError, Recording, Session, SessionInfo, SkeletonRef, Stage, TickBatch,
    TimestampSource,
};

fn main() -> Result<(), RecordError> {
    let root = std::env::temp_dir().join(format!("telemetry-readme-{}", std::process::id()));
    let info = SessionInfo {
        git_revision: "0213129".to_owned(),
        operator: "joey".to_owned(),
        stage: Stage::Vcan,
        skeleton: SkeletonRef { path: "config/skeleton.yaml".to_owned(), sha256: "00".repeat(32) },
        buses: vec![BusInfo {
            name: "can1".to_owned(),
            bitrate: 1_000_000,
            timestamps: TimestampSource::Software,
            receive_filters: Vec::new(),
            error_filter: 0,
            adapter_firmware: None,
        }],
    };
    let start_ns = 1_794_141_296_000_000_000; // 2026-11-08T12:34:56Z
    let session = Session::start(&root, info, start_ns)?;
    let (mut recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);

    // The bus thread's side, once a tick: fill a batch and hand it over. This never blocks.
    let mut batch = TickBatch::new(0, 0, start_ns);
    batch.push(FrameRecord {
        id: 0x0200_0EFD,
        extended: true,
        error: false,
        remote: false,
        len: 8,
        data: [0x80, 0x00, 0x7F, 0xFF, 0x80, 0x01, 0x00, 0xFA],
        stamp_ns: start_ns + 250_000,
        direction: Direction::Rx,
    });
    let accepted = buses.first_mut().is_some_and(|can1| can1.record(batch));
    assert!(accepted);

    // The recorder's side: `Recorder::spawn(recording)` does this on its own thread; here it is stepped by hand.
    recording.step(0, start_ns)?;
    let summary = recording.close(buses, start_ns + 4_000_000)?;
    assert!(summary.buses.iter().all(|bus| bus.batches == 1 && bus.batches_lost == 0));

    std::fs::remove_dir_all(&root)?;
    Ok(())
}
```
