# runtime

The one realtime process (PLAN item 3, [architecture.md](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md)
section 1): the only program that writes to the robot's CAN buses. It loads the skeleton, records the session, runs one bus
thread per wired bus and the control thread on one schedule origin, and takes the operator's requests.

## What it does

- **`plan`** maps the skeleton onto bus threads: one per bus with a joint on it, slots limb by limb in file order, each
  bus's limb indices naming the skeleton limb they stand for. A joint with no bus is offline and on none (`offline`); a
  skeleton with no joint on any bus is refused.
- **`Runtime::start`** reads the skeleton once (the session records the hash of exactly what was parsed), starts the
  session (`telemetry`), every bus thread (`can::spawn`) and the control thread, all on one schedule origin a few ticks
  out. Nothing is enabled: the runtime never enables on its own, not at start and not after a restart (PLAN item 3). A
  start that fails ends every thread it started.
- **The control thread** runs once a tick, a quarter of the slack after the buses' collect deadline. It takes each bus's
  newest snapshot (handed on as a `View` when asked for) and its re-arm answers, turns the operator's stops and then
  clears into each bus's orders, and publishes the next tick's batch. Hold only for now: every batch is empty, which still
  tells each bus control is alive. It counts what it can't do on time (`ControlExit`): stale snapshots, ticks it slept
  through, dropped batches, replies and views.
- **Stops** (`Runtime::stop(Scope)`) go through a latch, never a queue: always accepted, never waiting, and taken each tick
  before any clear (PLAN item 3a). A stop a bus's full order ring didn't take is pushed again each tick, ahead of anything
  else for that bus.
- **Clears** (`Clear`, through the in-process queue `Runtime::clears`) re-arm one stopped limb on every bus it is on,
  answered by one `Reply` per bus under the requester's tag. A clear behind a stop still waiting for its bus is refused
  (`Busy`), as is one to a bus thread that has ended (`BusEnded`) and one of a limb on no bus (`Offline`).
- **The run ends** with `Runtime::end` (or SIGINT and SIGTERM in the binary): every bus stops its limbs and ends once
  control has taken a snapshot with every limb at rest, then the session closes. It also ends on its own if control loses
  its clock or a bus thread ends: `Runtime::finished` is set, and the binary then ends the runtime and exits with failure.

Preflight, enable and hold, the `api` socket, `mlockall`, `SCHED_FIFO` and the systemd units come in the PRs that follow
(PLAN step 7). A clear of a limb on two buses can be taken on one and refused on the other; nothing can enable it yet,
and enable (4b-2) will need every bus's clear.

## Must never

Enable a drive on its own. Send Disables in a batch: a stop is an order to the bus (step 7 design, D2). Let a clear reach a
bus before a stop asked before it. Block the control thread on a client: stops go through a latch, clears and replies
through bounded rings, and a full ring drops and counts.

## Talks to

`can` (bus threads and their rings), `skeleton` (the file it runs), `telemetry` (the session). The sim suite drives it on
`vcan` (`crates/sim-suite/tests/runtime.rs`). See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

```bash
runtime [--skeleton <file>] [--sessions <dir>] [--hz <n>]
# on the dev box, with vcan up and sim-drive serving the skeleton's buses:
scripts/devbox.sh run cargo run -p runtime -- --sessions /tmp/sessions
```

Defaults: `config/skeleton.yaml`, `/var/lib/robot/sessions`, 250 Hz. It logs what it checked at startup (build, skeleton
hash, each bus's settings and joints, the offline joints) and, at the end, control's counts. The build's git revision,
with `-dirty` for a changed tree, is embedded at build time and recorded in every session.

In code, the plan and the routing are pure. With the test robot in `tests/skeleton.yaml`, whose right arm spans two
buses:

```rust
use skeleton::LimbName;

let text = std::fs::read_to_string("tests/skeleton.yaml").unwrap();
let plans = runtime::plan(&skeleton::parse(&text).unwrap()).unwrap();
let stop = runtime::route_stop(&plans, runtime::Scope::Limb(LimbName::RightArm));
assert_eq!(stop.count(), 2);
assert_eq!(runtime::route_clear(&plans, LimbName::LeftLeg).count(), 0);
```
