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
  newest snapshot (handed on as a `View` when asked for) and its re-arm answers, steps the operator's enable and holds
  every enabled joint into the next tick's batches, turns the operator's stops (and any its enables and holds asked) and
  then clears into each bus's orders, and publishes the batches. A batch with nothing in it still tells its bus control
  is alive. It counts what it can't do on time (`ControlExit`): stale snapshots, ticks it slept through, dropped batches,
  replies and views.
- **Enables** (`Enable`, through `Runtime::enables`, of joints named by `Runtime::joints`) are answered by one
  `EnableReply`. One runs at a time. An enable is refused before anything is sent if it names nothing, a joint already
  enabled or of a limb held on any bus, or a joint whose skeleton entry can't pass (a null fact or cap, no bus, a model without settled MIT scales),
  or while the session's recording has failed (`host.logging`). Otherwise every named joint's preflight runs (`safety`,
  over its bus's slow requests); in the tick the last one passes every enable sequence starts, and once every drive is
  in Run and MIT mode the enable is answered `Ok`. A refusal before any Enable may have gone stops nothing; a failure
  after one stops every limb the enable named. A limb is one limb over every bus it is on: a part of it stopped on any
  bus fails the enable, so a limb over two buses enables only once both are cleared. Another host's frame on a named
  joint's bus during the enable fails it too, since its writes could change what preflight proved, as does a named
  drive its bus hasn't shown within preflight's answer window.
- **The hold**: every enabled joint gets a slack MIT command each tick from the tick its own drive is in Run (zero gains,
  zero torque: watched by the bus's rules, holding nothing, so the motion rules have nothing to check yet) until real
  control modes and gains exist. A joint stops being held when its limb stops on any bus, and a stop on one bus is then
  asked of the whole limb. While a limb is held, a drive of it on any bus that this host never enabled, seen out of
  Reset or not seen at all, stops the whole limb (`safety::limb_mates`, `host.mode`, PLAN item 6); the same clause fails
  the enable running once an Enable of it may have gone, so it is never answered `Ok` over such a mate.
- **Stops** (`Runtime::stop(Scope)`) go through a latch, never a queue: always accepted, never waiting, and taken each tick
  before any clear (PLAN item 3a). A stop a bus's full order ring didn't take is pushed again each tick, ahead of anything
  else for that bus.
- **Clears** (`Clear`, through the in-process queue `Runtime::clears`) re-arm one stopped limb on every bus it is on,
  answered by one `Reply` per bus under the requester's tag. A clear behind a stop still waiting for its bus is refused
  (`Busy`), as is one to a bus thread that has ended (`BusEnded`), one while the run ends (`Ending`, once per bus), and one
  of a limb on no bus (`Offline`, once). A clear pushed after the run has finished gets no reply.
- **The run ends** with `Runtime::end` (or SIGINT and SIGTERM in the binary): every bus stops its limbs and ends once
  control has taken a snapshot with every limb at rest, then the session closes. It also ends on its own if control loses
  its clock or a bus thread ends: `Runtime::finished` is set, and the binary then ends the runtime and exits with failure.

The `api` socket (and so any way for the binary's operator to enable), `mlockall`, `SCHED_FIFO` and the systemd units
come in the PRs that follow (PLAN step 7). Stops that control asks (an enable's failure, `host.mode`) reach the bus as
operator stops, and control's enables and refusals emit no event yet: the session records them only as limb stops until
a stop carries its cause and control has an event queue, the next PR, before any real drive is enabled (step 8).

Known limits, each failing closed or only delaying a stop by a pass: control decides on the newest snapshots, so a stop
seen on one bus reaches the limb's other buses a control pass later; a limb-mate's view carries no age, so a bus that
missed its tick shows its last one; a bus with no snapshot yet when an enable is taken counts every other host's frame
it later reports as new, refusing the enable; the recording's `Health` fails on write errors only, not on frames the
recorder's ring dropped; a drive that reboots after its preflight passed, while its enable waits for a mate's proof,
loses its `canTimeout` with nothing on the bus to say so (whether a real RobStride leaves a trace is for the bench); and
a full slow ring is reported as `NoStatus`.

## Must never

Enable a drive on its own, or one an enable didn't name. Send an Enable before every named joint's preflight has passed. Send Disables in a batch: a stop is an order to the bus (step 7 design, D2). Let a clear reach a
bus before a stop asked before it. Block the control thread on a client: stops go through a latch, clears and replies
through bounded rings, and a full ring drops and counts.

## Talks to

`can` (bus threads and their rings), `safety` (preflight and the enable sequence), `robstride` (the hold's MIT
frames), `skeleton` (the file it runs), `telemetry` (the session). The sim suite drives it on
`vcan` (`crates/sim-suite/tests/runtime.rs`). See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

```bash
runtime [--skeleton <file>] [--sessions <dir>] [--hz <n>]
# on the dev box, with vcan up and sim-drive serving the skeleton's buses:
scripts/devbox.sh run cargo run -p runtime -- --sessions /tmp/sessions
```

Defaults: `config/skeleton.yaml`, `/var/lib/robot/sessions`, 250 Hz. It logs what it checked at startup (build, skeleton
hash, each bus's settings and joints, the offline joints) and, at the end, control's counts. SIGUSR1 also ends it: the binary raises it itself when the run ends on its own. The build's git revision,
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
