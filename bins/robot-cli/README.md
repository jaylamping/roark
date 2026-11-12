# robot-cli

The operator's command line. Today it has one command, `disable`: the independent stop that systemd runs after the
runtime exits (`ExecStopPost`, PLAN item 3). Scan, set-ID, parameter reads and checks join it as clients of the runtime's
`api` once that socket exists (PLAN item 3a).

## What it does

- **`targets`** reads the (bus, ID) pairs from the skeleton, with each joint's name for the report. Nothing else in the
  skeleton changes what is sent. A joint with no bus is offline and gets nothing.
- **`disable`** opens each bus itself, one named thread (`disable-<bus>`) and one socket per bus, so a bus that is gone
  or slow never delays another (PLAN item 2, Stop). Each wake reads at most 64 frames before it steps the stop, so a
  flooded bus still gets its Disables on time, and the stop isn't over while frames are still queued. Error frames are
  read too; bus-off is the class that counts, as in the runtime (can.md, Errors and bus-off).
- **`stop::BusStop`** is one bus's stop as plain values, timed from when it began:
  - A Disable to every drive at once, sent again every 4 ms to each drive not yet read in Reset, for 100 ms.
  - Each drive's active reporting off once its post-Disable silence is over. That is 54 ms after its Reset is read, or
    150 ms for a drive never read in Reset, because a drive drops every frame in that silence.
  - Each reporting off is followed by a 50 ms watch. A report read more than 15 ms after it (a drive reports every
    10 ms) means it didn't take, and it is sent again, up to three times in all.
  - The stop ends by 310 ms. A full queue leaves a frame due for the next wake. Any other write error fails that bus
    alone and nothing more is sent on it, even after a read error; a read error lets the frames go on but confirms
    nothing on that bus.
- **The outcome per drive** (`stop::Outcome`) is what was read, not just what was sent:
  - `stopped`: read in Reset after a Disable, not seen out of Reset since, and watched after its reporting off.
  - `silent`: never answered (unpowered or not wired) on a bus that never went bus-off. Warning, passive and ACK
    error frames, which a bus with no powered drive sends, don't count.
  - Everything else needs a person: answered but not in Reset when last read (a later Run withdraws a Reset and
    starts its Disables and reporting off over), still reporting, the stop ending before its watch did, a frame that
    never left, a failed bus, or silence on a bus that went bus-off or whose error frames can't be read.
- **`claim`** takes the runtime's lock (`LOCK_PATH`, `/run/robot/runtime.lock`, or `--lock`). The runtime makes it and
  holds it for as long as it runs, so `disable` refuses while a runtime is alive. The kernel drops the lock when the
  runtime dies, by `kill -9` too. `disable` opens it read-only, which any user who can read it may lock, and keeps it
  while it sends, so a runtime can't start mid-stop.
  - Held: `disable` refuses.
  - Can't be opened or locked (permissions, for one): whether a runtime holds it isn't known, so `disable` refuses.
  - Doesn't exist: no runtime using that path is running, so `disable` goes on. A runtime started by hand during the
    stop would make the file and run alongside it; systemd never does this, as the file exists through `ExecStopPost`.
    A runtime started with another `--lock` can't be seen: pass the same `--lock` to both.
- **The build's git revision** is embedded (the runtime's build script) and printed to stderr at start.

## Must never

- Send anything but Disable (type 4, fault-clear byte unset) and active reporting off (type 24). The frames come from
  `robstride::encode`.
- Run while the runtime is alive
  ([architecture.md](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md) section 1: one process
  owns motion).
- Depend on anything but the skeleton's (bus, ID) pairs and the bus. No session, no `api`, no runtime state.
- Wait without a deadline.

## Talks to

The CAN buses directly, after the runtime has exited: the one exception to "clients talk to `api` only" on the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md). It uses `robstride` for frames and
`skeleton` to read the file.

## Using it

On the Pi, systemd runs it after every runtime exit (`deploy/systemd/runtime.service`). By hand, with the runtime stopped:

```bash
robot-cli disable --skeleton /etc/robot/skeleton.yaml
# can1 11 left_shoulder_pitch: stopped; 1 Disables, Reset read at 0.4 ms, 1 reporting off, last at 54.4 ms
# ...
# disable: 0 of 9 drives need a person
robot-cli disable --skeleton /etc/robot/skeleton.yaml --json   # the same, as one JSON document
```

`--json` prints `{build, buses: [{bus, fault: {kind, detail} | null, error_frames, bus_off, errors_unseen, drives:
[{id, joint, outcome, ok, disables, reset_ms, reporting_offs, reporting_off_ms}]}], need_a_person, drives}`. `outcome` is
one of `stopped`, `silent`, `silent_on_faulty_bus`, `not_reset`, `still_reporting`, `watch_cut`, `queue_full` and
`bus_failed`; `fault.kind` one of `open`, `spawn`, `write` and `read`. A refusal prints no document.

Exit 0 when every drive was read in Reset or never answered on a healthy bus; 1 when any drive needs a person; 2 when it
refused (a runtime holds the lock, or the lock can't be checked, bad arguments, or a skeleton that won't load).

One bus's stop, driven by hand: a drive read in Reset gets its reporting off once its silence is over.

```rust
use std::time::Duration;

use robot_cli::stop::{BusStop, Outcome, RESEND, SILENCE};
use robstride::{DeviceId, Frame, decode};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let id = DeviceId::new(11)?;
    let mut stop = BusStop::new([id]);
    let mut sent: Vec<Frame> = Vec::new();

    stop.step(Duration::ZERO, &mut |f| Ok(sent.push(f)));
    assert_eq!(sent.len(), 1); // the Disable

    // Drive 11 answers in Reset 1 ms later (type 2, mode 0); nothing more is due until its silence is over.
    let reset = decode(0x0200_0BFD, &[0x80, 0, 0x80, 0, 0x80, 0, 0, 0xFA])?;
    let read_at = Duration::from_millis(1);
    stop.heard(read_at, &reset);
    let off_at = read_at + SILENCE + RESEND;
    stop.step(off_at - Duration::from_millis(1), &mut |f| Ok(sent.push(f)));
    assert_eq!(sent.len(), 1); // a millisecond early: still nothing
    stop.step(off_at, &mut |f| Ok(sent.push(f)));
    assert_eq!(sent.len(), 2); // reporting off

    // Watched for 50 ms after its reporting off with no report read: stopped.
    let (_, outcome) = stop.outcomes(off_at + Duration::from_millis(50)).remove(0);
    assert_eq!(outcome, Outcome::Stopped);
    Ok(())
}
```
