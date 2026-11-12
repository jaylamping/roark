# robot-cli

The operator's command line. Today it has one command, `disable`: the independent stop that systemd runs after the
runtime exits (`ExecStopPost`, PLAN item 3). Scan, set-ID, parameter reads and checks join it as clients of the runtime's
`api` once that socket exists (PLAN item 3a).

## What it does

- **`targets`** reads the (bus, ID) pairs from the skeleton, with each joint's name for the report. Nothing else in the
  skeleton changes what is sent. A joint with no bus is offline and gets nothing.
- **`disable`** opens each bus itself, one thread and one socket per bus, so a bus that is gone or slow never delays
  another (PLAN item 2, Stop).
- **`stop::BusStop`** is one bus's stop as plain values, timed from when it began:
  - A Disable to every drive at once, sent again every 4 ms to each drive not yet read in Reset, for 100 ms.
  - Each drive's active reporting off once its post-Disable silence is over. That is 54 ms after its Reset is read, or
    150 ms for a drive never read in Reset, because a drive drops every frame in that silence.
  - Each reporting off is followed by a 50 ms watch. A report read more than 15 ms after it (a drive reports every
    10 ms) means it didn't take, and it is sent again, up to three times in all.
  - The stop ends by 310 ms. A full queue leaves a frame due for the next wake. Any other socket error fails that bus
    alone.
- **The outcome per drive** is what was read, not just what was sent:
  - `stopped`: read in Reset after a Disable.
  - `silent`: never answered (unpowered or not wired).
  - Failures: answered but never in Reset, still reporting, or a frame that never left.
- **`claim`** takes the runtime's lock (`LOCK_PATH`, `/run/robot/runtime.lock`, or `--lock`). The runtime holds it for as
  long as it runs, so `disable` refuses while a runtime is alive. The kernel drops the lock when the runtime dies, by
  `kill -9` too. `disable` keeps the lock while it sends, so a runtime can't start mid-stop. If the lock's directory
  doesn't exist or the lock can't be checked, `disable` goes on: a Disable is never the unsafe direction.

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
```

Exit 0 when every drive was read in Reset or never answered; 1 when any drive needs a person; 2 when it refused (the
runtime is alive, bad arguments, or a skeleton that won't load).

One bus's stop, driven by hand: a drive read in Reset gets its reporting off once its silence is over.

```rust
use robot_cli::stop::{BusStop, Outcome, RESEND_NS, SILENCE_NS};
use robstride::{DeviceId, Frame, decode};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let id = DeviceId::new(11)?;
    let mut stop = BusStop::new([id]);
    let mut sent: Vec<Frame> = Vec::new();

    stop.step(0, &mut |f| Ok(sent.push(f)));
    assert_eq!(sent.len(), 1); // the Disable

    // Drive 11 answers in Reset 1 ms later (type 2, mode 0); nothing more is due until its silence is over.
    let reset = decode(0x0200_0BFD, &[0x80, 0, 0x80, 0, 0x80, 0, 0, 0xFA])?;
    stop.heard(1_000_000, &reset);
    let off_at = 1_000_000 + SILENCE_NS + RESEND_NS;
    stop.step(off_at - 1, &mut |f| Ok(sent.push(f)));
    assert_eq!(sent.len(), 1);
    stop.step(off_at, &mut |f| Ok(sent.push(f)));
    assert_eq!(sent.len(), 2); // reporting off

    let (_, outcome) = stop.outcomes().remove(0);
    assert_eq!(outcome, Outcome::Stopped);
    Ok(())
}
```
