# Architecture conventions

How Roark's pieces fit together and the rules for changing that shape. [TENETS.md](../TENETS.md) says what is right,
[PLAN.md](../PLAN.md) says what to build, [rust.md](rust.md) says how to write Rust and [testing.md](testing.md) says how to
test. If any of them disagree with the tenets, the tenets win and the other file gets fixed.

This file is also the **architecture map** tenet 7 asks for. Any change that moves a seam (a new process, crate, queue, port or
owner) updates this file in the same PR. Until code exists, the map shows the target.

## 1. The map

```
 Pi 5                                                                    off the Pi
 +--------------------------------------------------------------+
 | runtime (one process, the only CAN writer)                   |
 |                                                              |
 |  bus thread can0 --+                                         |
 |  bus thread can1 --+-- safety --- control                    |      ui/ (browser)
 |  ...    one per bus|     ^            ^                      |         |
 |                    |     | requests   | requests             |         v
 |      snapshots     v     |  (rtrb)    |                      |   ui bridge (thin) ----+
 |   +---------------------------------------------+            |                        |
 |   | api server (non-realtime): commands in,     |<-----------+---- mcp/ (agents) -----+
 |   | snapshots and events out                    |            |                        |
 |   +---------------------------------------------+            |   robot-cli -----------+
 |   | telemetry thread: MCAP, metrics, logs       |---> disk, Prometheus/Grafana
 |   +---------------------------------------------+            |
 +--------------------------------------------------------------+
   systemd: watchdog on runtime (fed while control's progress count rises); ExecStopPost = robot-cli disable (independent of runtime)
   candump -L per bus: independent black box

 Dev box or CI: sim-drive on vcan can0..can4 (the skeleton's names) stands in for the drives; runtime runs unchanged.
 Later: Jetson (perception) is another api client, never a CAN writer.
```

| Piece | Owns | Talks to | Must never |
|---|---|---|---|
| `runtime` bus threads | One CAN socket each, that bus's drive state, each limb's stop latch (`can`'s `BusTick`) | `robstride` codec, `safety`, rtrb queues | Allocate, lock, log or wait without a deadline in the tick |
| `safety` | Preflight results, fault latches, limit checks | Bus threads, `control` | Be bypassed: every command to a drive passes it |
| `control` | The active control mode per limb | `safety`, `dynamics` | Talk to a socket |
| `api` server | The one external interface | Clients over the network; the realtime side over queues | Block the realtime side, or write hardware facts |
| `telemetry` | MCAP files, metrics, structured logs | Event queues in, disk and Prometheus out | Be in the stop path (a slow disk never delays a stop) |
| `ui/`, `mcp/`, `robot-cli` | Nothing about the hardware | `api` only | Open a CAN socket (the one exception below) |
| `robot-cli disable` | Nothing | The bus directly, after `runtime` has exited; the runtime's lock (`/run/robot/runtime.lock`), which the runtime holds while it runs and `disable` refuses while held | Run while `runtime` is alive |
| `sim-drive` | Simulated drive state | `vcan` through the same `robstride` codec (its drive side, `robstride::drive`) | Be linked into `runtime`, or open an interface that isn't `vcan` |
| `can-bench` | Nothing about the robot | One CAN interface, with its own frames that no drive acts on ([comparison](../docs/can-interface-comparison.md)) | Run with a drive or another host on the bus, or alongside `runtime` |

The queues between the control thread and each bus thread, all bounded `rtrb` rings made before the first tick
(`can::BusLinks`):

| Ring | From → to | When full |
|---|---|---|
| Command batches | control → bus | Control's push fails and that batch is never sent. The bus empties the ring each tick and takes the newest; a batch for another tick, or none, sends nothing, and an expired one for the tick sends only its Disables and reporting off |
| Orders (stop a limb, stop the bus, re-arm a stopped limb) | control → bus | Control's push fails and the order isn't taken; control keeps a stop it couldn't push and pushes it next tick. The bus takes every order at each tick's start, before its drain, in push order |
| Re-arm answers, one per re-arm order | bus → control | Dropped and counted (`rearms_dropped`); the limb's state and generation still show in the snapshots |
| Slow requests (parameter reads, allowlisted writes, get-ID) | control → bus | Control's push fails and that request gets no result. The bus takes them only as its slots free up |
| Slow results, one per request | bus → control | Dropped and counted (`slow_results_dropped`); the requester times out |
| Snapshots | bus → control | The newest is dropped and counted (`snapshots_dropped`) |
| Recorded frames | bus → telemetry | Counted in the recording as a loss, never blocking the tick |

And between the control thread and the rest of `runtime` (`runtime::Runtime`), until the `api` takes its side:

| Ring or latch | From → to | When full |
|---|---|---|
| Stop latch (robot, or a limb) | operator → control | Never full: a bit per scope, so a stop asked again before control takes it is the same stop. Control takes it each tick before any clear (PLAN item 3a) |
| Clears | operator → control | The operator's push fails; nothing was asked. Control takes them after the stops, in push order |
| Clear replies, one per bus the limb is on, or one refusal | control → operator | Dropped and counted (`replies_dropped`); the limb's state and generation still show in the views |
| Enables, each of a set of joints | operator → control | The operator's push fails; nothing was asked. Control takes them after its reads, one running at a time: the rest are refused `Busy` |
| Enable replies, one per enable | control → operator | Dropped and counted (`replies_dropped`); the limbs' states still show in the views |
| Views, each bus's newest snapshot once a tick (only when asked for) | control → operator | Dropped and counted (`views_dropped`) |
| Progress, a count of passes in which every bus was on time (`Runtime::progress`; the rule is `control::progressing`) | control → the binary's watcher, which feeds systemd's watchdog while it rises | Never full: a counter |

## 2. Process boundaries are failure domains

- **One process owns motion.** Only `runtime` transmits on a robot bus (tenet 5); `robot-cli disable` after it has
  exited, and `can-bench` on a bench bus with no drive, are the named exceptions. Every other process can crash, hang or
  be restarted and the motors don't notice. **Why:** the legacy stack had several bus writers (motor-repl, an MCP tool that stopped the
  service and launched its own owner), and nobody could say who moved a joint.
- **A dead `runtime` stops the robot.** The drives' 50 ms CAN timeout makes them go limp, systemd's watchdog kills a hung
  process, and `ExecStopPost` runs the independent disable. Nothing tries to keep motion alive after the owner dies.
- **Nothing in the stop path depends on a non-realtime piece.** Stopping never waits on disk, network, a client or a log flush.
  **Why:** the legacy shutdown flushed trace files before disabling drives.
- **Fail stop, not degrade.** A fault, a silent drive or a failed check stops the affected limb. No degraded modes, no "hold for
  a few seconds and hope". New modes need a test that requires them (tenet 4).

## 3. Dependencies point one way

```
robstride  (leaf: codec, per-model tables and unit types, no I/O)
   ^
skeleton   (types and loader, no I/O beyond reading the file; reads robstride's model table)
   ^
  can  <-- safety <-- control <-- runtime (bin)
                         ^
                      dynamics
api       (message types; used by runtime, ui bridge, mcp, robot-cli)
telemetry (leaf for producers: takes events, depends on nothing above; can hands it each tick's frames)

can --> robstride, telemetry        safety --> can, robstride, skeleton
runtime --> can, robstride, safety, skeleton, telemetry

can-bench (bin) --> nothing in the workspace
robot-cli (bin) --> robstride, skeleton        sim-drive (bin) --> robstride, skeleton
sim-suite (tests only) --> can, runtime, safety, sim-drive, skeleton, robstride, telemetry
```

- Arrows only point toward the leaves. No cycles, no "utils" or "common" crate that everything imports.
- **`skeleton` reads `robstride`'s model table**, because the loader refuses a cap above the model's range and the
  per-model ranges are manual facts that live once, in the codec (skeleton.md section 4). The SI unit types live in
  `robstride` too: the codec is where drive values become SI, and every other crate already depends on it.
- **The codec does no I/O.** `robstride` turns bytes into typed frames and back. It can be tested with plain byte arrays and
  reused by `sim-drive` and `robot-cli` unchanged.
- **A drive's frames are their own type.** `robstride::drive` (the drive's side, for `sim-drive`) builds a `DriveFrame`,
  never a `Frame`; only `robstride::encode` makes a `Frame`, and the bus layer transmits only `Frame`s. So nothing that talks
  to the robot's drives can send a drive's frame, whichever crates a build compiles together. **Why:** a cargo feature
  can't hold this, because a workspace build turns a feature on for every crate in it.
- **Only named crates open a CAN socket.** `deny.toml` bans `socketcan` except as a direct dependency of `can`,
  `can-bench`, `robot-cli` (for `disable` alone), `sim-drive` and `sim-suite`. `sim-drive` and every sim test
  check an interface is `vcan` before the first frame, because the sim's buses carry the robot's real bus names. `can`
  opens `vcan`, or a real interface only once its driver, bit timing, state and modes match the skeleton. `can-bench`
  opens real interfaces on purpose, to measure them: it sends only frames no drive acts on and refuses a bus where
  anything else talks (its README).
- **Clients depend on `api`, never on `runtime` internals.** If a client needs something, it becomes an `api` message.
- A new crate needs a separate reason to exist: a different owner, a different realtime class, or reuse by two binaries. "It
  felt big" is a reason for a module, not a crate.

## 4. Data flows

- **Commands go in as requests.** A client asks; `runtime` decides. Requests pass `safety` and can be refused, and every
  refusal comes back with a reason. No client writes a drive register or a shared variable directly.
- **State comes out as snapshots.** Each tick the bus threads publish a snapshot: every joint's position, velocity, torque,
  temperature, fault bits, mode and the **age** of its last reply. Readers never see half a tick, and a stale value is visible
  as stale, never shown as live.
- **Events are separate from snapshots.** State changes, faults, refusals, limit hits and operator actions are discrete events
  with timestamps, recorded in full. Snapshots can be sampled; events are never dropped silently (drops are counted).
- **Queues are bounded and one-directional.** One producer, one consumer, fixed capacity, a defined behaviour when full (drop
  oldest and count, or refuse the request). Unbounded queues hide overload until memory runs out.

## 5. Facts and configuration

- **The skeleton is read once at startup and never written by software** (tenet 2). If it's invalid, `runtime` refuses to
  start and says which line is wrong. Changing hardware facts means editing the file and restarting.
- **One fact, one place.** A joint name, limit, ID, sign or scale lives in the skeleton or in the manual-derived codec table,
  nowhere else. **Why:** the legacy stack held limits in five places with three different values for one joint.
- **Measured numbers are data with a source.** Friction fits, gravity fits and tuned gains come from a logged session and
  record which session. They live in their own files, are reviewed like code, and are never written by the running robot.
- **Runtime state is not configuration.** What the robot is doing now lives in memory and in the logs, not in a file the next
  run reads back.

## 6. State is explicit

- Each drive and each limb has a **named state machine** (for example offline, found, preflighted, enabled, stopping, faulted).
  Every transition has one trigger, is logged as an event, and illegal transitions are refused. Where the type
  system can rule a transition out at compile time, it does (rust.md section 3).
- **Faults latch.** Clearing one is an explicit operator action that is logged. Software never auto-clears and retries
  (tenet 3).
- **A missing drive is a state, not an error path.** An unbuilt limb is a limb whose drives are all offline (tenet 1). Bring-up
  of a subset works by construction; nothing requires every joint to answer.

## 7. Time

- The realtime loop runs on the **monotonic clock** with absolute deadlines. Wall-clock time is for logs only.
- Every sample carries its timestamp and its source (kernel RX timestamp for CAN frames). One shared clock across the Pi and
  the Jetson (tenet 8), so logs from different machines line up.
- Every wait has a deadline. A loop that waits for a reply without one is a bug.

## 8. Observability is part of the design

- **Every seam emits.** Each boundary in the map (bus, safety, control, api, clients) records what crossed it, so any run can
  be replayed and any question ("why did the elbow stop?") answered from logs, not by re-running on hardware (tenets 6 and 8).
- **Off-the-shelf only:** MCAP for frames and events, `tracing` for logs, Prometheus/Grafana for metrics. No home-grown log
  store, query language or viewer. **Why:** the legacy stack grew about 20k lines of its own logging and storage.
- Every binary and every recording carries the git commit it was built from.

## 9. Testing seams

- **The only I/O seam is the bus.** Real drives on `can*`, `sim-drive` on `vcan*`, same `runtime` binary, same codec.
  Everything else runs for real.
- **Pure logic is unit-tested directly**, with no bus: the codec, skeleton checks and safety rules are plain functions.
- **Time is given, not read.** Logic that depends on time (the 50 ms timeout, three missed replies, temperature pauses) takes
  the current time as an argument from the loop, so a test steps time by hand instead of sleeping. Prefer passing the
  `Instant` value over a clock trait.
- No seam exists only to make a mock possible. Details in [testing.md](testing.md).

## 10. The UI and agent tools

- **Clients are views and request senders.** `ui/`, `mcp/` and `robot-cli` show state and send requests. They hold no safety
  logic, limits or hardware facts of their own; what they display comes from `api`.
- **One schema for the interface.** `api` message types are defined once and the UI's TypeScript types are generated from them,
  never hand-copied. **Why:** two hand-kept copies of a schema drift (the legacy proto carried 12 unreferenced messages and
  about 20 deprecated fields).
- The UI bridge is thin: it translates transport, nothing more. It never writes config, the skeleton, URDF or logs.
- An agent tool that needs a capability gets an `api` message. It never stops the service to take over the bus.

## 11. Changing the shape

A PR that adds any of these says why in its description and updates this file:

- a process, a thread with its own priority, or a systemd unit;
- a crate, or a dependency edge between crates;
- a queue, a port or a message in `api`;
- a new owner for a piece of state, or a new writer of any fact.

Ask first: is this still right when the whole robot is built (tenet 0)? Does a test we are running need it now (tenet 4)?
Can an agent new to the repo still read this map and know where it lives (tenet 7)?

## 12. Legacy patterns that don't come back

Each of these was in the marengo stack and was judged against the tenets in the
[reconciliation](https://github.com/jaylamping/marengo/blob/main/review/sw-foundation-20261108/RECONCILIATION.md):

| Pattern | Why it goes |
|---|---|
| Reference, grant and journal machinery, leases | Abstraction for problems we don't have (tenet 4) |
| Degraded modes that keep drives powered after a fault | Tenet 3 says stop |
| Limits and IDs held in several files | One fact, one place (tenet 2) |
| Home-grown logging, storage and log viewers | Off-the-shelf stack (tenet 8) |
| Tools that open a robot bus or stop the service | One CAN owner (tenet 5); `can-bench` runs only on a bus with no drive |
| Preflights that require every joint online | Missing drives are a state (tenet 1) |
| Runtime that writes config or URDF | The skeleton is hand-agreed (tenet 2) |
| Speculative ADRs and versioned interfaces nobody uses | Build only what's needed now (tenet 4) |
