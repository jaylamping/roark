# runtime

The one realtime process (PLAN item 3, [architecture.md](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md)
section 1): the only program that writes to the robot's CAN buses. It loads the skeleton, records the session, runs one bus
thread per wired bus and the control thread on one schedule origin, and takes the operator's requests.

## What it does

- **`plan`** maps the skeleton onto bus threads: one per bus with a joint on it, slots limb by limb in file order, each
  bus's limb indices naming the skeleton limb they stand for. A joint with no bus is offline and on none.
- **`Runtime::start`** starts the session (`telemetry`), every bus thread (`can::spawn`) and the control thread, all on
  one schedule origin a few ticks out. Nothing is enabled: the runtime never enables on its own, not at start and not
  after a restart (PLAN item 2).
- **The control thread** runs once a tick, after the buses' collect deadline. It takes each bus's newest snapshot (handed
  on as a `View`) and its re-arm answers, turns the operator's requests into each bus's orders (`route`), and publishes
  the next tick's batch. Hold only for now: every batch is empty, which still tells each bus control is alive.
- **Requests** (`Request`, through the in-process queue `Runtime::requests`): `Stop(Scope)` is always taken; a stop a
  bus's full order ring didn't take is pushed again each tick, ahead of anything else for that bus. `Clear` re-arms one
  stopped limb on every bus it is on, answered by one `Reply` per bus under the requester's tag; a clear behind a stop
  still waiting for its bus is refused (`Busy`), and one of a limb on no bus is refused (`Offline`).
- **`Runtime::stop`** (or SIGINT and SIGTERM in the binary) ends the run: every bus stops its limbs and ends once control
  has taken a snapshot with every limb at rest, then the session closes.

Preflight, enable and hold, the `api` socket, `mlockall`, `SCHED_FIFO` and the systemd units come in the PRs that follow
(PLAN step 7).

## Must never

Enable a drive on its own. Send Disables in a batch: a stop is an order to the bus (step 7 design, D2). Block the control
thread on a client: requests and replies go through bounded rings, and a full ring drops and counts.

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

Defaults: `config/skeleton.yaml`, `/var/lib/robot/sessions`, 250 Hz.

In code, the plan is pure:

```rust
use std::path::Path;

use skeleton::LimbName;

let skeleton = skeleton::load(Path::new("../../config/skeleton.yaml")).unwrap();
let plans = runtime::plan(&skeleton).unwrap();
let left = plans.iter().find(|p| p.limb_index(LimbName::LeftArm).is_some()).unwrap();
assert!(!left.drives.is_empty());
let stop = runtime::route(&plans, runtime::Request::Stop(runtime::Scope::Limb(LimbName::LeftArm)));
assert_eq!(stop.count(), 1);
```
