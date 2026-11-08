# Logging, recording and metrics conventions

**Status:** proposed for Joey's review, 2026-11-08.

[Tenet 8](../TENETS.md#8-observability-everywhere) says what gets recorded and which off-the-shelf tools we use.
[PLAN "Observability"](../PLAN.md#observability-tenet-8) holds the decided facts: what a session is, what goes in its MCAP file
and `session.json`, the `candump` black box, the logging thread fed by a lock-free ring, and the shared clock.
[architecture.md section 8](architecture.md#8-observability-is-part-of-the-design) says every seam emits.
[rust.md section 12](rust.md#12-logging-in-code-tenet-8) covers the Rust mechanics (`tracing` with typed fields, realtime
threads push to a ring, no `println!`). This page is the one home for field names, levels, event kinds, MCAP channels and
metric names.

This page covers **how records are named, shaped and used** across every part of the robot (runtime, `sim-drive`, tools, UI),
so that months from now a session can still be replayed and a stop at 2 a.m. can be explained from the logs alone.

## 1. Three streams, each with one job

| Stream | Answers | Where | Read by |
|---|---|---|---|
| **Recording** (MCAP per session, plus `candump`) | "What exactly happened, frame by frame?" Everything sim needs to replay a run | `<data>/sessions/...` (PLAN) | Replay tools, Foxglove, fitting scripts, agents |
| **Log** (`tracing` to journald) | "What did the system decide, and why?" State changes, refusals, stops, operator actions, startup checks | journald on the Pi | People and agents reading what happened |
| **Metrics** (Prometheus, when PLAN turns it on) | "Is something getting worse over time?" Counts, rates, latencies, temperatures | Prometheus and Grafana | Dashboards and alerts |

To decide where something goes, ask:
- Would replay or a fit need it? → recording.
- Should a person read it when something goes wrong? → log, and also an event in the recording.
- Do we want to watch its trend? → metric.

Something can go to more than one stream; a stop, for example, is an event in the recording, a log line and a counter.

**Why:** each stream is good at one thing. Per-frame data in text logs floods them and is lossy. A decision recorded only as a
metric loses the "why". A trend kept only in MCAP files can't be graphed without writing tools. The legacy stack mixed all
three into one home-grown store of about 20k lines.

## 2. Events

Events are the shared language of the robot's history. Each one is an event in the recording and a log line at the matching
level.

- **Every event has a `kind` from one closed list**, written as `area.past_tense_verb`: `drive.enabled`, `drive.went_silent`,
  `limb.stopped`, `preflight.refused`, `limit.hit`, `fault.latched`, `fault.cleared`, `operator.requested`, `skeleton.loaded`,
  `bus.off`. In Rust it's an enum, so adding a kind is a deliberate change, and the UI's types are generated from it.
- **Every event carries** a stamp (`stamp_ns`, [units-and-frames.md section 5](units-and-frames.md#5-time-and-timestamps)),
  its kind, and whichever shared fields apply (section 2a). Safety events add the measured value and the threshold.
- **Event kinds and field names are an interface.** Renaming one breaks dashboards, replay scripts and every query anyone saved.
  Change them like an `api` message: on purpose, in one PR, with the readers updated.
- **Causes are explicit.** A `limb.stopped` event says what caused it (`rule = host.silence`, or `operator`), rather than
  leaving the reader to infer it from the events around it.

**Why:** "why did the elbow stop?" should be one search, not an afternoon of reading. A closed list of kinds with consistent
fields makes the history queryable and keeps every part of the system speaking the same vocabulary. OpenTelemetry's semantic
conventions follow the same idea at a much larger scale.

## 2a. Shared field names

One set of names, used in log fields, event fields, MCAP messages, metric labels and the UI. Nothing else invents a synonym
(`motor`, `axis`, `can_id`, `node`).

| Field | Meaning | Example |
|---|---|---|
| `session` | The session ID (PLAN "Observability") | `2026-11-12T19:04:11Z` |
| `bus` | Bus name from the skeleton | `can1` |
| `device_id` | Drive ID on that bus | `14` |
| `joint` | Joint name from the skeleton | `left_elbow_pitch` |
| `limb` | Limb name | `left_arm` |
| `mode` | Drive or limb mode/state | `enabled` |
| `fault` | Fault kind or bit name | `over_temperature` |
| `rule` | Safety rule ID ([safety.md section 2](safety.md#2-each-rule-has-a-stable-id)) | `host.silence` |
| `client` | Who sent a request: UI, CLI, an agent, and the person if known | `robot-cli:joey` |

Values carry units in the name when they're bare numbers (`temp_c`, `latency_us`), per
[units-and-frames.md](units-and-frames.md). Adding a shared field is a change to this table.

## 2b. Levels

Levels mean the same thing in every language and tool:

| Level | Means | Examples |
|---|---|---|
| `error` | An operator or agent must look | A stop, a refused enable, a latched fault, a bus-off, the recorder failing |
| `warn` | Degraded but handled | A late reply, a dropped frame, a slow tick, a client that disconnected |
| `info` | State changes and operator actions | Drive enabled, limb stopped and cleared, skeleton loaded, session started |
| `debug`, `trace` | Per-frame or per-tick detail | Off by default; never needed for replay, because the recording holds the frames |

**Why:** if `error` sometimes means "look now" and sometimes "something odd happened", people stop looking. Losing data is an
`error`, not a `warn` (rerun's rule).

## 3. The recording (MCAP)

- **Channel names are paths by what they carry,** never by limb or milestone: `/can/<bus>/frames`, `/can/<bus>/tx_intent`, `/joint_state`,
  `/command`, `/event`, `/fault_injected` (sim only), `/session`. Joints are fields inside the messages, not separate channels.
- **Every channel declares a schema stored in the file** (MCAP's rule for anything that isn't self-describing). Schemas come from
  the Rust types, never hand-written. **Why:** a recording from milestone 1 must still open after the code has changed. With the
  schema inside the file, Foxglove and Python can read it without our build.
- **Both of a message's MCAP times are when it happened at the source,** on the wall clock: for a bus's tick, the tick's
  start (each frame inside carries its own kernel timestamp). **Why:** Foxglove plays a file by `log_time`, so a recorder
  `log_time` would replay a storage stall as a pause and then a burst. How far the recorder fell behind is its own number.
- **Times inside JSON messages are `{sec, nsec}` objects,** never one integer of nanoseconds. **Why:** JSON readers that
  parse numbers as doubles (JavaScript, so Foxglove) lose the last digits of a nanosecond Unix time.
- **Raw and decoded both.** Raw frames are the ground truth if the codec turns out to be wrong; decoded state is what analysis
  wants. Never only decoded.
- **Injected faults are recorded as injected,** on their own channel, so a replay shows what was real.
- **The recorder never blocks the bus threads.** When its ring fills it drops and counts (PLAN), and the count goes in the
  session's final summary so a gap in the data is never silent.

## 4. Log lines

Levels are in section 2b; the Rust mechanics are in rust.md section 12. Across every language:

- **The message is a short, constant phrase;** the values go in fields. `"drive went silent"` with `joint`, `missed = 3`, not
  `"left_elbow_pitch missed 3 replies"`. **Why:** constant messages can be searched, counted and grouped; interpolated ones
  can't.
- **One line per event,** no multi-line dumps. Large data (a frame batch, a config) belongs in the recording, and the log line
  points to it.
- **Nothing is logged from inside the realtime tick.** The tick hands events to the logging thread through the ring (PLAN).
- **Repeating problems are summarised, not repeated.** A drive late on every tick logs once when it starts, then a count per
  second while it lasts, then once when it stops. (rerun's `warn_once!` serves the same purpose.)
- **An error is handled once.** Either return it to the caller or log it where it's finally handled, not both. **Why:** an
  error logged at every level it passes through looks like five failures.
- **Nothing fails in silence.** A dropped frame, a full queue, a log file that won't open, a client that disconnected: each is
  counted and, if it matters, logged. (rerun: "an error should never happen in silence.")
- **Startup logs what was checked:** skeleton file and hash, git commit, interface settings per bus, socket filters, which
  joints are configured and which are offline. A session's first lines say exactly what the robot thought it was.

## 5. Metrics

When PLAN turns metrics on, they follow Prometheus's own naming rules:

- `snake_case`, prefixed by component: `can_replies_missed_total`, `can_reply_latency_seconds`, `drive_temperature_celsius`.
  No robot name in metric names (tenet 7: names change; the robot's name lives only in the skeleton).
- **Base units, spelled out,** as Prometheus requires: `_seconds`, `_bytes`, `_celsius`, `_volts`. This is the one place we
  write seconds where config might say `_ms`; the exporter converts.
- **Counters end in `_total`** and only go up. Gauges are current values.
- **Labels are a small, fixed set:** `bus`, `limb`, `joint`, `rule`. Never a session ID, a timestamp, an error message or a value
  as a label. **Why:** every distinct label value is a new time series; unbounded labels bring Prometheus down.

## 6. Tools, CLIs and clients

- **CLIs** (`robot-cli`, test-stand tools) print results to stdout and diagnostics to stderr. Human-readable text by default,
  `--json` for agents and scripts, with the same content. Output makes sense without colour and respects `NO_COLOR`. (uv's
  STYLE.md.)
- **Operator actions are logged by the runtime,** which is the one that acts on them, not by the UI. The UI's own logs are for
  debugging the UI.
- **Agents' actions carry the agent's identity** as the `client`, like any other client.
- **Analysis scripts read recordings, never write into them.** Derived results (a friction fit) go to their own files, citing the
  session ID they came from ([bench.md section 5](bench.md#5-recording-results)).

## 7. What never goes in a log

- Secrets, tokens, keys, passwords, API credentials.
- Personal data beyond an operator's name on their own actions.
- Full config or skeleton dumps at `info` (the hash and file path are enough; the file is in git).

## 8. CAN frame logging

CAN is the chattiest stream in the robot and the one replay depends on most, so it gets its own rules. The goal: **every frame
in and out is kept, the bus threads never wait on it, and any gap is known.**

### 8.1 How much data

Working numbers for the finished robot. They're estimates to size buffers and disks; the bench soak (PLAN item 5) measures the
real ones, and they replace these.

| Assumption | Value |
|---|---|
| Drives per bus | about 6 on each arm and leg bus (including a future hand), 1 on the waist |
| Frames per drive per tick | 2 (one command, one reply), plus a little parameter traffic in the slack |
| Tick rate | 250 Hz |

| Result | Value |
|---|---|
| Frames per second, one arm bus | about 3,000 (about 45 % load at 1 Mbit/s with extended IDs) |
| Frames per second, whole robot | about 12,500 |
| Raw frames in MCAP, one message per frame | about 2.8 GB per hour before compression (the per-message header is as big as the frame) |
| Raw frames in MCAP, one message per bus per tick | about 1.2 GB per hour before compression |
| Decoded joint state at full rate | about 0.9 GB per hour before compression |
| `candump -L` text, all buses | about 2.3 GB per hour before compression |

CAN data compresses well (repeated IDs, slowly changing values), so expect a few times smaller on disk. The soak gives the real
ratio.

### 8.2 Shape of the recording

- **One MCAP message per bus per tick** on `/can/<bus>/frames`, holding that tick's frames in order, with the tick number and
  the tick's monotonic time. **Why:** half the size of one message per frame, and it matches how the bus thread works, so a
  replay sees ticks as they happened. openpilot, which logs every CAN frame of a car, batches the same way.
- **Each frame inside carries the same fields as the ASAM MDF4 bus-logging standard,** so it converts to vendor formats without
  loss: bus, ID, extended flag, error and remote flags, length, data, kernel timestamp, and direction:
  - `rx` (from a drive);
  - `tx_echo` (our own frame coming back from the kernel, which marks that it left this socket);
  - `tx_other` (sent by another program on the Pi, which should never happen; PLAN item 3).
- **Each batch carries a `valid` flag and the kernel's drop count.** `valid` is false when the bus is unhealthy (error passive,
  bus-off, interface down). The drop count is the socket's overflow counter (`SO_RXQ_OVFL`), so frames the kernel threw away
  before we read them are visible too.
- **What the bus thread meant to send is its own record** on `/can/<bus>/tx_intent`: every frame handed to the socket, and every
  frame not sent with the reason (deadline passed, `ENOBUFS`). The echo shows what left the Pi; the intent shows what the
  software decided. (openpilot keeps sent and received CAN as separate streams for the same reason.)
- **Frames that arrive outside a tick** (late replies, error frames, parameter replies in the slack) go in the next tick's batch
  with their own timestamps. Nothing is dropped for arriving late.
- **Error frames are recorded as frames,** decoded into the bus error enum ([can.md](can.md)), not only as log lines.
- **Interface counters** (controller state, bus errors, error-warning and error-passive counts, bus-off count, RX dropped and
  overrun, the same numbers `ip -details -statistics` shows) are sampled once a second per bus onto `/can/<bus>/stats`.
- **Decoded joint state** goes on `/joint_state` once per tick, from the same replies. Text logs never carry per-frame or
  per-tick data.
- **Channels are per bus,** so a reader can open one bus without decoding the others, and a missing bus shows as a missing
  channel.
- **Our own schema.** Foxglove has no standard CAN schema, so the frame schema is ours, generated from the Rust types (section
  3). An export script converts a session to MF4 or BLF (through `python-can` or `asammdf`) for vendor tools.

### 8.3 Timestamps

- **Kernel timestamps are wall-clock time,** and NTP can step them. So each batch also carries the tick's monotonic time, and the
  recorder writes the offset between the two clocks to `/clock` once a second. Analysis uses monotonic time for intervals.
- **The timestamp source is recorded per bus:** hardware timestamps from the gs_usb adapters, software timestamps from anything
  without them (the MCP2515 HAT has none). Startup logs which each bus has.
- Use the kernel's 64-bit (`_NEW`) timestamp socket options, which keep working after 2038.

### 8.4 The path from bus thread to disk

- **The bus thread copies each tick's frames into a fixed-size slot** in its own single-producer ring (`rtrb`, PLAN item 3). The
  slot is a plain struct sized for the most frames a tick can hold. No allocation, no lock, no system call. **Why:** the bus
  thread's only job is the tick; anything that can block it can make a drive time out. copper-rs and PX4's logger work the same
  way.
- **The socket receive buffer is set explicitly** at startup (`SO_RCVBUFFORCE`) and read back and logged, so a burst can't
  overflow the kernel's default buffer.
- **The ring is sized from measured storage stalls, not the average write speed.** Start at 2 seconds of worst-case traffic per
  bus; the bench soak measures the SSD's worst write and `fsync` stall over a long run, and the ring must cover several times
  that. **Why:** PX4 found that storage pauses, not average speed, cause log dropouts; many SD cards pause for hundreds of
  milliseconds several times a minute.
- **If the ring is full, the newest batch is dropped and counted,** never blocking. The recorder writes a **gap record** into
  the file (bus, frames lost, time span), so the hole is in the data itself, not only in a counter. It's also an event
  (`recorder.dropped`, `error` level), a metric, and a line in the session summary. (PX4's log format has the same "dropout"
  record.)
- **One recorder thread** drains every bus ring, builds MCAP messages, compresses chunks with zstd and writes. Normal priority, on
  a core the bus threads aren't pinned to.
- **Chunks are closed every second or at about 4 MB, whichever comes first,** with chunk checksums on. A crash loses at most
  about a second; `mcap recover` rebuilds the index of a file cut off by a crash, and the `candump` black box covers the lost
  second. (Foxglove recommends chunks of 1 to 4 MB and flushing every few seconds.)
- **On a stop, drives are disabled before the recorder flushes** (PLAN item 3). The recorder then writes the stop's events and
  closes the file cleanly.

### 8.5 Files

- **A session is split into numbered files** in its directory, cut on a tick boundary when a file reaches about 1 GB or
  10 minutes, whichever comes first. A file being written has a `.lock` beside it. (openpilot splits every minute; CANedge
  splits by size or time.)
- **Every file starts with a header record** (session, file number, git commit, skeleton hash, bitrates, socket filters, adapter
  firmware versions, timestamp source per bus) and ends with an end marker, so any one file makes sense alone and a missing end
  marker means the file was cut off.

### 8.6 Two independent records

- **MCAP from the runtime** has everything: raw frames, intent, decoded state, events, injected faults.
- **`candump` per bus** (PLAN) sees what the kernel saw, independent of our code. If the runtime crashes, hangs or has a bug in
  its recorder, the black box still has the frames.
- **How `candump` runs:** `-L` (log format), `-x` (marks each frame R or T), `-d` (writes the kernel's drop count into the log as
  `DROPCOUNT` lines, which parsers must accept), `-r` (a larger receive buffer), and on gs_usb buses `-H -N` (hardware
  timestamps in nanoseconds).
- **`candump` can't rotate its own files,** and restarting it leaves gaps. So its output is piped into a rotator that cuts and
  compresses with zstd (for example hourly), set up in `deploy/`.
- **The two are checked against each other.** An analysis script compares frame counts and timestamps per bus per session; a
  mismatch means a drop or a recorder bug. The bench soak (PLAN item 5) runs it.

### 8.7 Disk and retention

- **Session data goes on an SSD, not the SD card.** At these rates an SD card wears out and stalls. Which drive the Pi uses is a
  hardware choice; the requirement is sustained writes of a few MB/s with short worst-case stalls (section 8.4).
- **A disk floor:** below a set amount of free space, the runtime refuses the next enable (PLAN item 6, "Logging" row) and says
  why. A running motion is never stopped for it.
- **Sessions on real hardware are never deleted automatically.** They're the most valuable data we have. A person clears them
  with a command that lists what it will delete.
- **`vcan` sessions are deleted automatically,** oldest first, when free space nears the floor. Any session can be marked
  `preserve` to keep it. Rotated `candump` files are pruned after a set number of days, since the MCAP holds the same frames.
  (openpilot and CANedge both delete automatically; we only do it for data a rerun can reproduce.)

### 8.8 Reading it back

- **Foxglove** opens the MCAP directly, per bus and per joint.
- **Replay:** the replay tool feeds a session's recorded replies into the runtime's decode and control path, and `canplayer`
  replays a `candump` file onto `vcan` to drive `sim-drive` or the runtime unchanged.
- **Analysis scripts** read MCAP with the official MCAP libraries (Rust or Python), never a parser of our own.
- **Small browsing copies, if wanted,** decimate decoded state, never raw CAN. (openpilot's small log leaves CAN out almost
  entirely; the full log is the record.)

### 8.9 CAN metrics

Counted by the bus thread as plain integers in its snapshot, exported by the non-realtime side (section 5 naming):
`can_frames_total{bus,dir}`, `can_bus_load_ratio{bus}`, `can_errors_total{bus,kind}`, `can_tx_dropped_total{bus,reason}`,
`can_kernel_dropped_total{bus}`, `can_replies_missed_total{bus,joint}`, `can_reply_latency_seconds{bus}` (histogram),
`can_ticks_late_total{bus}`, `recorder_dropped_total{bus}`.

## 9. Using the records

- **Replay before re-running.** When something goes wrong, first try to answer it from the session's recording and log, then
  replay it in sim. Only go back to hardware if the records can't answer it. (copper-rs: "prefer extraction and resimulation
  before adding new instrumentation.")
- **If the records couldn't answer a question, fix that.** Add the event or field that would have answered it, in the same PR as
  the fix. That's how logging improves: driven by real questions, not added speculatively.
- **Tests check events, not text.** A sim test for a safety rule checks that the `limb.stopped` event with the right `rule` was
  recorded ([safety.md](safety.md)). No test asserts on the wording of a log message.

## Checklist for a PR that logs something

- Which stream does it belong in (section 1)?
- Is it an event kind from the list, with the shared field names and units in its fields?
- Is the message a constant phrase with values in fields?
- Could it run in the realtime tick, repeat every tick, or carry a secret?
- If it touches CAN frames: does it follow section 8 (per-tick batches, ring never blocks, drops counted)?
- If it's a metric: base units, `_total` for counters, bounded labels?

## Sources

- openpilot logging (batched CAN events, separate sent and received streams, segment rotation, `deleter.py`):
  https://github.com/commaai/openpilot/tree/master/system/loggerd
- Foxglove on MCAP chunk size and compression: https://www.foxglove.dev/blog/understanding-mcap-chunk-size-and-compression and
  recording on a Pi from a writer thread: https://www.foxglove.dev/blog/recording-robocar-data-with-mcap
- CSS Electronics CANedge (MDF4 logging, splitting, metadata per file):
  https://canlogger.csselectronics.com/canedge-docs/ce2/filesystem/log-file.html
- PX4 logging (storage stalls, dropout records): https://docs.px4.io/main/en/dev_log/logging.html and
  https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/dev_log/ulog_file_format.md
- Linux timestamping and SocketCAN docs: https://docs.kernel.org/networking/timestamping.html,
  https://docs.kernel.org/networking/can.html; can-utils `candump.c`: https://github.com/linux-can/can-utils
- python-can file formats (MF4, BLF, candump): https://python-can.readthedocs.io/en/stable/file_io.html
- MCAP specification and registry (schemas stored in the file, `log_time` and `publish_time`): https://mcap.dev/spec and
  https://mcap.dev/spec/registry
- Prometheus metric and label naming: https://prometheus.io/docs/practices/naming/
- rerun CODE_STYLE (errors never silent, handled once, `warn_once!`): https://github.com/rerun-io/rerun/blob/main/CODE_STYLE.md
- uv STYLE.md (stdout and stderr, `NO_COLOR`, output readable without colour): https://github.com/astral-sh/uv/blob/main/STYLE.md
- copper-rs CONTRIBUTING (determinism and replay as features; resimulate before adding instrumentation):
  https://github.com/copper-project/copper-rs/blob/master/CONTRIBUTING.md
- OpenTelemetry semantic conventions (shared attribute names across a system): https://opentelemetry.io/docs/specs/semconv/
