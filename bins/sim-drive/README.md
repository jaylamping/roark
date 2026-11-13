# sim-drive

Simulated RobStride drives on `vcan` (PLAN item 4), so the runtime, the bus layer and every stop rule run unchanged against
something that answers like the real drives before any real drive is enabled.

## What it does

- **`SimDrive`** is one simulated drive, sans-IO: host frames in (`receive`), its frames out when they fall due
  (`pop_due`), with the time passed in by the caller (testing.md rule 6). It answers each host frame the way the manuals
  say a drive does, with the delays measured on the bench (PLAN [item 2](https://github.com/jaylamping/roark/blob/main/PLAN.md#2-lift-the-hard-won-knowledge-first) and
  [item 4](https://github.com/jaylamping/roark/blob/main/PLAN.md#4-simulated-drives-on-vcan)): the wait from Enable to Run, the silence after a Disable, and the
  blackout some time after a Set Zero on an enabled drive. `canTimeout` drops an enabled drive to Reset; a reboot
  (`Fault::Reboot`) puts every parameter back to its default (`canTimeout` 0); active reports go out on a fixed period
  while on, each showing the joint as it was when it fell due. Every
  delay comes from the seed it's given, so a run replays exactly.
- **The plant:** a first-order joint (`plant.rs`). In Run, the MIT law `kp (p_t - p) + kd (v_t - v) + t_ff` drives a
  damper (`DAMPING` in `plant.rs`, 1 N·m·s/rad, a sim value), so a target is reached with time constant
  `(DAMPING + kd) / kp`; torque stops at `limit_torque` and speed at `limit_spd`, the caps preflight writes. That a real drive holds those two caps in MIT mode
  is a sim assumption until a bench capture shows it (PLAN item 6). Out of Run the joint rests where it is. No inertia
  or gravity yet. A read of the position or speed register gives the joint as it is, unless a value was injected.
- **Fault injection** (`Fault`, PLAN item 4): a silent drive, late, lost or doubled frames, fault bits, a mode the host
  didn't ask for, a register that reads out of window (VBUS, the damper), a temperature, a reboot mid-run, writes
  answered but not kept, and lost Disables. `inject` applies one now; `schedule` fires one on a `Trigger` (the drive's
  nth MIT command or Enable, or a time: the drive is brought up to it, so timed faults land in time order), at most `FAULT_PLAN`
  at once. Both refuse a fault the drive can't honour (`FaultRefused`: a `Late` past `MAX_LATE`, a temperature a
  status can't carry, a register value of the wrong type) and a time the drive is already past; `schedule` also
  refuses `OnMit(0)` and `OnEnable(0)`. Transport faults apply as each frame falls due, so they reach replies already waiting but never
  a frame due before they fired, however seldom the host reads. Every injection is recorded once (`take_injected`, up
  to `INJECTED_LOG` untaken; `injections_lost` counts the rest), so a replay shows what was injected. A duplicate ID or a wrong UID needs no fault: build two drives with one ID, or one
  with another UID.
- **`serve`** (Linux) runs a set of `SimDrive`s on one bus's `vcan` socket until told to stop, handing each injection
  to its caller as it takes effect.
- **The `sim-drive` binary** simulates every drive the skeleton puts on each bus, one thread per bus.

Where neither the manuals nor a bench capture says what a drive does, the sim says so in a comment: it answers nothing to
the version query or the reporting switch, answers a set-ID from its new ID (the manual says a type-0 frame, not from
which ID), and most parameter defaults are sim values. An RS00 answers no
status until its MIT scales are settled (PLAN item 2); `dropped` counts what it couldn't send. A fault bit leaves the
mode as it is: no capture says a drive changes mode on a fault. Bus-level faults (bus-off, an interface going away) are
the bus's, not a drive's.

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
