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

- **Channel names are paths by what they carry,** never by limb or milestone: `/can/<bus>/rx`, `/can/<bus>/tx`, `/joint_state`,
  `/command`, `/event`, `/fault_injected` (sim only), `/session`. Joints are fields inside the messages, not separate channels.
- **Every channel declares a schema stored in the file** (MCAP's rule for anything that isn't self-describing). Schemas come from
  the Rust types, never hand-written. **Why:** a recording from milestone 1 must still open after the code has changed. With the
  schema inside the file, Foxglove and Python can read it without our build.
- **Two times per message:** MCAP's `log_time` is when the recorder wrote it; `publish_time` is when it happened at the source
  (the kernel RX timestamp for CAN frames). Replay and analysis use `publish_time`.
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

- **One MCAP message per bus per tick** on `/can/<bus>/frames`, holding that tick's frames in order. Each frame inside keeps its
  own kernel timestamp, direction (`tx`/`rx`), ID, length and data. **Why:** this halves the size compared with one message per
  frame and matches how the bus thread works (one batch per tick), so a replay sees ticks as they happened.
- **Frames that arrive outside a tick** (late replies, error frames, parameter replies in the slack) go in the next tick's
  message with their own timestamps. Nothing is dropped for arriving late.
- **TX records what the bus thread handed to the socket and when**, plus anything the socket refused (`ENOBUFS`, deadline
  passed) as its own entry. A command that was meant to go but didn't is as important as one that went.
- **Error frames are recorded as frames,** decoded into the bus error enum ([can.md](can.md)), not only as log lines.
- **Decoded joint state** goes on `/joint_state` once per tick, from the same replies. Text logs never carry per-frame or
  per-tick data.
- **Channels are per bus,** so a reader can open one bus without decoding the others, and a missing bus is visible as a missing
  channel.

### 8.3 The path from bus thread to disk

- **The bus thread copies each tick's frames into a fixed-size slot** in its own single-producer ring (`rtrb`, PLAN item 3). The
  slot is a plain struct sized for the most frames a tick can hold. No allocation, no lock, no system call. **Why:** the bus
  thread's only job is the tick; anything that can block it can make a drive time out.
- **The ring holds at least 2 seconds of worst-case traffic per bus.** That rides out a slow SD card write or a compression
  hiccup without loss.
- **If the ring is full, the newest batch is dropped and counted,** never blocking. The count per bus becomes an event
  (`recorder.dropped`, `error` level, because lost data is an error), a metric, and a line in the session summary.
- **One recorder thread** drains every bus ring, builds MCAP messages, compresses chunks with zstd and writes. It runs at normal
  priority, on a core the bus threads aren't pinned to.
- **Chunks are written about once a second.** A crash or power cut loses at most about a second of the MCAP; the `candump` black
  box covers that second.
- **On a stop, drives are disabled before the recorder flushes** (PLAN item 3). The recorder then writes the stop's events and
  closes the file cleanly.

### 8.4 Two independent records

- **MCAP from the runtime** has everything: raw frames, decoded state, commands, events, injected faults.
- **`candump -L` per bus** (PLAN) sees what the kernel saw, independent of our code. If the runtime crashes, hangs or has a bug
  in its recorder, the black box still has the frames.
- **They can be checked against each other.** An analysis script compares frame counts and timestamps per bus per session; a
  mismatch means a drop or a recorder bug. The bench soak (PLAN item 5) runs this check.
- **`candump` files are compressed and rotated by `deploy/`** (for example hourly files, compressed with zstd as they close), so
  a long soak can't fill the disk with text.

### 8.5 Disk and retention

- **Session data goes on an SSD, not the SD card.** At these rates an SD card wears out and its write stalls are the most likely
  reason a ring fills. Which drive the Pi uses is a hardware choice; the software requirement is sustained writes of a few MB/s
  with no long stalls.
- **A disk floor:** below a set amount of free space, the runtime refuses the next enable (PLAN item 6, "Logging" row) and says
  why. A running motion is never stopped for it.
- **Nothing deletes MCAP sessions automatically.** Sessions from bench procedures and faults are the most valuable data we have.
  Clearing old sessions is a deliberate command that lists what it will delete. Rotated `candump` files may be pruned
  automatically after a set number of days, since the MCAP holds the same frames.
- **Long sessions split by size:** past about 1 GB, the recorder closes the file and continues in a new numbered file in the
  same session directory, so no single file is too big to copy or open.

### 8.6 Reading it back

- **Foxglove** opens the MCAP directly, per bus and per joint.
- **Replay:** the replay tool feeds a session's recorded replies into the runtime's decode and control path, and `canplayer`
  can replay a `candump` file onto `vcan` to drive `sim-drive` or the runtime unchanged.
- **Analysis scripts** read MCAP with the official MCAP libraries (Rust or Python), never with a parser of our own.

### 8.7 CAN metrics

Counted by the bus thread as plain integers in its snapshot, exported by the non-realtime side (section 5 naming):
`can_frames_total{bus,dir}`, `can_bus_load_ratio{bus}`, `can_errors_total{bus,kind}`, `can_tx_dropped_total{bus,reason}`,
`can_replies_missed_total{bus,joint}`, `can_reply_latency_seconds{bus}` (histogram), `can_ticks_late_total{bus}`,
`recorder_dropped_total{bus}`.

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

- MCAP specification and registry (schemas stored in the file, `log_time` and `publish_time`): https://mcap.dev/spec and
  https://mcap.dev/spec/registry
- Prometheus metric and label naming: https://prometheus.io/docs/practices/naming/
- rerun CODE_STYLE (errors never silent, handled once, `warn_once!`): https://github.com/rerun-io/rerun/blob/main/CODE_STYLE.md
- uv STYLE.md (stdout and stderr, `NO_COLOR`, output readable without colour): https://github.com/astral-sh/uv/blob/main/STYLE.md
- copper-rs CONTRIBUTING (determinism and replay as features; resimulate before adding instrumentation):
  https://github.com/copper-project/copper-rs/blob/master/CONTRIBUTING.md
- OpenTelemetry semantic conventions (shared attribute names across a system): https://opentelemetry.io/docs/specs/semconv/
