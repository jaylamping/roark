# sim-suite

The sim suite (testing.md, "Where tests live"): the tests that put frames on `vcan` against `sim-drive`, the same way the
runtime runs. CI gate 7 (rust.md section 13).

## What it does

Holds every test that needs Linux and a real `vcan` socket, in `tests/`; the library itself is empty. Today:

- `vcan.rs`: `sim-drive` refuses anything that isn't `vcan`, and a simulated drive answers the host's frames through
  the kernel.
- `bus.rs`: `can::spawn` refuses an interface it can't read or that isn't CAN, and the bus thread runs two simulated drives through
  enable, hold and a shutdown stop, recorded by `telemetry`; the recording is checked frame by frame against an
  independent `candump -L -x` capture (needs `can-utils`). Also a thread started after the schedule joining it.
- `slow.rs`: slow requests (get-ID, a write, its read-back) reaching a drive and coming back.
- `scan.rs`: every ID on a bus probed: a drive in the bus's table, one outside it and two sharing an ID are found and
  nothing else answers; a set-ID moves the stray drive to a new ID, where it answers, and its old ID falls silent. Then
  the same through the runtime and its test robot: the scan's table, an enable refused while it runs, a set-ID moved
  and confirmed, ones refused for nothing at the old ID, two drives there or a drive at the new, and one refused by the
  bus with a limb on it stopped.
- `faults.rs`: a fault injected into one drive is caught by the bus thread before the next send, stopping only that
  drive's limb; a drive gone silent, and one that also loses its Disable, stop their limb for the silence. The rest of
  the fault tests (PLAN item 4, "Done when") join them as the safety layer lands.
- `enable.rs`: `safety`'s preflight and enable sequence played as control would, over the bus layer's rings: a truthful
  drive passes and enables, another UID or a drive not in Reset is refused, each preflight failure injected in
  `sim-drive` refuses under its rule, and a drive silent after preflight fails its enable. Control stalling on the
  sequence for over 50 ms after the reporting off's echo refuses the enable with no Enable sent (`Stalled`), and an
  Enable in a batch the bus holds back as expired stops the limb as an Enable not seen to go out (`NoEnableEcho`).
- `orders.rs`: control's order to stop one limb stops it alone while the other limb runs on, and once the stop has
  ended a re-arm order (the operator's clear) is answered under its tag and gives the limb a new generation; a stop
  order naming a limb the bus doesn't have, pushed with the clear, stops both limbs in the same tick; a clear sent as
  the bus exits never undoes its stop; and a bus that ends answers every clear left in its ring `Ended`, counting the
  answers control's ring can't take and every stop order left naming a limb it doesn't have.
- `disable.rs`: the `runtime` and `robot-cli` binaries, built by `scripts/sim.sh` first. `robot-cli disable` refuses
  while the runtime holds its lock; after `kill -9` it leaves every answering drive in Reset with reporting off and
  sends nothing else; with one skeleton bus missing, only that bus's drives fail; a lock it can't check refuses; and a
  bus-off error frame mid-stop fails every drive on its bus while the other bus stops.
- `runtime.rs`: the `runtime` crate on its test robot (two buses, one limb on both, one offline), against `sim-drive`
  on `can0` and `can1`: nothing enabled, a robot stop and a limb's stop reaching it on both buses, a clear re-arming a
  limb on both buses and one of the offline limb refused, and an end with every bus at rest and the session closed.
- `blackbox.rs`: `candump-rotate` running `candump` as `candump@<bus>.service` does (needs `can-utils`): every frame
  sent lands in its files exactly once, in order, across two cuts; SIGTERM to it alone ends `candump` and closes the
  last file cleanly; and killed mid-file it leaves a file that reads back to its last one-second block.
- `exit.rs`: a bus of two active limbs told to exit with control's snapshot ring full stops every limb and returns
  once the ring takes a snapshot with every limb stopped, once control drops the ring, or after its wait when control
  never reads again, each time at the next tick's drain; a bus of two stopping limbs with no time to collect records
  its last reporting off through that drain; and a bus that ends counts the slow results control's ring can't take.

Every frame on a bus reaches every socket on it, so two tests that run at the same time never share a bus. The tests in
`exit.rs`, `slow.rs`, `faults.rs`, `enable.rs` and `orders.rs` use `can0`, `runtime.rs`, `scan.rs` and `disable.rs` use `can0` and `can1`
(the runtime's test robot's two buses), `bus.rs` uses `can1` to `can3` and `blackbox.rs` uses `can3`, so all of them run one at a time
(nextest's `can0` test group, `.config/nextest.toml`); `vcan.rs` has `can4` to itself. A new test either takes a bus no other test uses or joins that
group.

nextest's default profile leaves this crate out, so `scripts/check.sh` stays runnable on any machine; the `sim` profile
runs only this crate.

## Must never

Open an interface without checking it is `vcan` first (`sim_drive::ensure_vcan`). The sim's buses carry the robot's real
names and `can::spawn` opens a real interface that matches the skeleton, so this check is what keeps a test run on the
Pi off a real drive (testing.md rule 8). The tests' skeletons and `common::interface` name a driver no real interface
has (`sim_only`) as a second guard for `can::spawn`; `robot-cli disable` checks neither, so its tests rely on
`ensure_vcan` alone. Never
sleep to wait: wait on a reply with a deadline (testing.md rule 6).

## Talks to

`sim-drive` (the drives under test), `can` (the bus thread under test), `safety` (preflight and the enable sequence
under test), `skeleton` (their joint), `telemetry` (its recording, read back), `robstride` (the host's frames and the
decoder), `vcan` through `socketcan`, `candump`, and the `candump-rotate` binary (run, not linked). See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

Linux only, with `vcan` `can0` to `can4` up (the dev box has them at boot; CI creates them). From the Mac, through the dev
box (docs/dev-box.md):

```bash
scripts/devbox.sh run ./scripts/sim.sh
```

On a Linux machine with the buses up:

```bash
./scripts/sim.sh                     # cargo nextest run --workspace --locked --profile sim
```
