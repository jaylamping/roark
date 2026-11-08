# sim-drive

Simulated RobStride drives on `vcan` (PLAN item 4), so the runtime, the bus layer and every stop rule run unchanged against
something that answers like the real drives before any real drive is enabled.

## What it does

- **`SimDrive`** is one simulated drive, sans-IO: host frames in (`receive`), its frames out when they fall due
  (`pop_due`), with the time passed in by the caller (testing.md rule 6). It answers each host frame the way the manuals
  say a drive does, with the delays measured on the bench (PLAN [item 2](https://github.com/jaylamping/roark/blob/main/PLAN.md#2-lift-the-hard-won-knowledge-first) and
  [item 4](https://github.com/jaylamping/roark/blob/main/PLAN.md#4-simulated-drives-on-vcan)): the wait from Enable to Run, the silence after a Disable, and the
  blackout some time after a Set Zero on an enabled drive. `canTimeout` drops an enabled drive to Reset; `power_cycle`
  puts every parameter back to its default (`canTimeout` 0); active reports go out on a fixed period while on. Every
  delay comes from the seed it's given, so a run replays exactly.
- **`serve`** (Linux) runs a set of `SimDrive`s on one bus's `vcan` socket until told to stop.
- **The `sim-drive` binary** simulates every drive the skeleton puts on each bus, one thread per bus.

Where neither the manuals nor a bench capture says what a drive does, the sim says so in a comment: it answers nothing to
set-ID, the version query or the reporting switch, and most parameter defaults are sim values. An RS00 answers no
status until its MIT scales are settled (PLAN item 2); `dropped` counts what it couldn't send. The plant holds position:
MIT targets move nothing yet.

## Must never

Open an interface that isn't `vcan`: its buses carry the robot's real names, and `can1` may be the real one. `serve`
and the binary check with `ensure_vcan` before the first frame. Never be linked into `runtime` (architecture.md
section 1).

## Talks to

`robstride` for every frame in and out (its drive side, `robstride::drive`), `skeleton` for which drives sit on which bus,
and `vcan` sockets through `socketcan`. The sim suite (`sim-suite`) drives it. See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

In a test, step a `SimDrive` by hand: give it host frames at chosen times and read what falls due.

```rust
use std::time::{Duration, Instant};

use robstride::drive::command;
use robstride::{DeviceId, Drive, Inbound, Mode, Model, Uid, decode, encode};
use sim_drive::SimDrive;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let id = DeviceId::new(14)?;
    let mut elbow = SimDrive::new(Drive::new(id, Model::Rs02), Uid([0; 8]), 7);
    let start = Instant::now();

    let enable = encode::enable(id);
    let host = command(enable.id(), &enable.data())?.ok_or("not a host frame")?;
    elbow.receive(start, host);

    // Run comes at most 11 ms after the enable.
    let reply = elbow.pop_due(start + Duration::from_millis(11)).ok_or("no reply")?;
    let Inbound::Status(status) = decode(reply.id(), &reply.data())? else {
        return Err("not a status".into());
    };
    assert_eq!(status.header.mode, Mode::Run);
    Ok(())
}
```

On Linux, the binary simulates every drive on the skeleton's buses (all of them, or those named with `--bus`); `--seed`
picks the delays. Each bus must be a `vcan` interface; on the dev box they are up at boot (docs/dev-box.md).

```bash
cargo run -p sim-drive -- --bus can1 --seed 3 &   # runs until killed
candump can1 &
cansend can1 0000FD0B#0000000000000000   # get_id to drive 11: it answers 00000BFE with its UID
```

`crates/sim-suite` runs `serve` with a drive on `vcan` and checks it answers the host (`scripts/sim.sh`, CI gate 7). It
doesn't start the binary, so the binary's argument parsing and skeleton filter are checked only by running it as above.
