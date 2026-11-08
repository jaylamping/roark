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
   systemd: watchdog on runtime; ExecStopPost = robot-cli disable (independent of runtime)
   candump -L per bus: independent black box

 Dev machine or CI: sim-drive on vcan0..vcan4 stands in for the drives; runtime runs unchanged.
 Later: Jetson (perception) is another api client, never a CAN writer.
```

| Piece | Owns | Talks to | Must never |
|---|---|---|---|
| `runtime` bus threads | One CAN socket each, that bus's drive state | `robstride` codec, `safety`, rtrb queues | Allocate, lock, log or wait without a deadline in the tick |
| `safety` | Preflight results, fault latches, limit checks | Bus threads, `control` | Be bypassed: every command to a drive passes it |
| `control` | The active control mode per limb | `safety`, `dynamics` | Talk to a socket |
| `api` server | The one external interface | Clients over the network; the realtime side over queues | Block the realtime side, or write hardware facts |
| `telemetry` | MCAP files, metrics, structured logs | Event queues in, disk and Prometheus out | Be in the stop path (a slow disk never delays a stop) |
| `ui/`, `mcp/`, `robot-cli` | Nothing about the hardware | `api` only | Open a CAN socket (the one exception below) |
| `robot-cli disable` | Nothing | The bus directly, after `runtime` has exited | Run while `runtime` is alive |
| `sim-drive` | Simulated drive state | `vcan` through the same `robstride` codec | Be linked into `runtime` |

## 2. Process boundaries are failure domains

- **One process owns motion.** Only `runtime` transmits on CAN (tenet 5). Every other process can crash, hang or be restarted
  and the motors don't notice. **Why:** the legacy stack had several bus writers (motor-repl, an MCP tool that stopped the
  service and launched its own owner), and nobody could say who moved a joint.
- **A dead `runtime` stops the robot.** The drives' 50 ms CAN timeout makes them go limp, systemd's watchdog kills a hung
  process, and `ExecStopPost` runs the independent disable. Nothing tries to keep motion alive after the owner dies.
- **Nothing in the stop path depends on a non-realtime piece.** Stopping never waits on disk, network, a client or a log flush.
  **Why:** the legacy shutdown flushed trace files before disabling drives.
- **Fail stop, not degrade.** A fault, a silent drive or a failed check stops the affected limb. No degraded modes, no "hold for
  a few seconds and hope". New modes need a test that requires them (tenet 4).

## 3. Dependencies point one way

```
skeleton   (leaf: types and loader, no I/O beyond reading the file)
robstride  (leaf: codec, no I/O)
   ^
  can  <-- safety <-- control <-- runtime (bin)
                         ^
                      dynamics
api       (message types; used by runtime, ui bridge, mcp, robot-cli)
telemetry (leaf for producers: takes events, depends on nothing above)
```

- Arrows only point toward the leaves. No cycles, no "utils" or "common" crate that everything imports.
- **The codec does no I/O.** `robstride` turns bytes into typed frames and back. It can be tested with plain byte arrays and
  reused by `sim-drive` and `robot-cli` unchanged.
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

- **The only swap is the bus.** Real drives on `can*`, `sim-drive` on `vcan*`, same `runtime` binary, same codec. Everything
  else runs for real. Details in [testing.md](testing.md).
- No seam exists only to make a mock possible.

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
| Tools that open the bus or stop the service | One CAN owner (tenet 5) |
| Preflights that require every joint online | Missing drives are a state (tenet 1) |
| Runtime that writes config or URDF | The skeleton is hand-agreed (tenet 2) |
| Speculative ADRs and versioned interfaces nobody uses | Build only what's needed now (tenet 4) |
