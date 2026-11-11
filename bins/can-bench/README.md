# can-bench

Measures a CAN interface the way the bus loop uses it, with **no drive on the bus**, so interfaces can be compared on the
numbers PLAN item 3 depends on before any of them carries a real drive. The procedure that runs it and the options it
compares: [can-interface-comparison.md](https://github.com/jaylamping/roark/blob/main/docs/can-interface-comparison.md).

## What it does

Two ends of one short bus, both terminated:

- **`can-bench respond`** stands in for a limb's drives. It answers every request to one of its slots at once, echoing
  the request's data. Run it on a second Linux machine (the dev box) through a reference adapter, so the Pi under test
  does only the host's work.
- **`can-bench host`** does to the interface under test what the runtime's bus thread does each tick (can.md section 2):
  wake on an absolute monotonic deadline, read what came late, send one frame per slot, read replies until 90 % of the
  period, never retry a frame the queue refused. Default: 250 Hz, 6 slots (a leg: 12 frames a tick), one hour.

The host writes two files to `--out`:

- **`ticks.csv`**: one row per tick: how late the wake was, when the tick's last reply was read, how many were missing,
  and when each slot's reply was read, all in nanoseconds from the tick's scheduled start.
- **`summary.txt`**, also printed: the interface's driver and whether it gives hardware timestamps; median, 99 %, 99.9 %,
  99.99 % and worst for the wake, the round trip, each reply's time from tick start and each tick's last reply; the share
  of replies read by the collect deadline (`--deadline-pct`, 60 by default); missing, late and duplicate replies, frames
  the queue refused, error and bus-off frames; and how the kernel's link counters (`ip -details -statistics`) changed.

Times are read with `CLOCK_MONOTONIC` when the program gets each frame: the time the runtime would act on, which includes
USB, driver and wake-up delay. That delay is what the comparison is for.

## Must never

- **Send a frame a drive could act on.** Its frames use communication types 31 and 30, which no RobStride manual defines,
  addressed to 0x80 and above, past every drive ID (`src/frames.rs`).
- **Run with a drive or another host on the bus.** Both ends listen for a second first and refuse if anything else talks.
  A powered drive with reporting off is silent, so the procedure says to unplug every drive; the check catches the rest.
- **Run alongside `runtime`, or on a robot bus in use.** Both ends take the runtime's lock (`/run/robot/runtime.lock`, the
  one `robot-cli disable` checks) for the whole run and refuse while a runtime holds it. It is a bench tool, never
  installed as a service.

## Talks to

No workspace crate: only `socketcan`, `nix` and `serde_json` (for `ip`'s JSON), so a measurement can't depend on the code
it is measuring for. It is one of the binaries `deny.toml` lets open a CAN socket; see the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md), section 3.

## Using it

Bring both interfaces up at the robot's settings first (docs/pi-setup.md), then, on the dev box and the Pi:

```bash
# Dev box, reference adapter on can0: answer as six drives, under realtime priority.
sudo chrt -f 80 can-bench respond --bus can0 --slots 6

# Pi, interface under test on can1: a one-hour leg-sized run, pinned to the isolated core.
sudo chrt -f 80 taskset -c 3 can-bench host --bus can1 --hz 250 --slots 6 --seconds 3600 --out runs/gs_usb-leg
```

A short run on `vcan` checks the setup before any hardware: `ip link add dev vcan0 type vcan && ip link set vcan0 up`,
then both ends on `vcan0` with `--seconds 10`; every reply should arrive and none should be missing. Nothing in CI runs
it: it measures hardware, and the procedure is how it is run.
