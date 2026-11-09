# sim-suite

The sim suite (testing.md, "Where tests live"): the tests that put frames on `vcan` against `sim-drive`, the same way the
runtime runs. CI gate 7 (rust.md section 13).

## What it does

Holds every test that needs Linux and a real `vcan` socket, in `tests/`; the library itself is empty. Today:

- `vcan.rs`: `sim-drive` refuses anything that isn't `vcan`, and a simulated drive answers the host's frames through
  the kernel.
- `bus.rs`: `can::spawn` refuses anything that isn't `vcan`, and the bus thread runs two simulated drives through
  enable, hold and a shutdown stop, recorded by `telemetry`; the recording is checked frame by frame against an
  independent `candump -L -x` capture (needs `can-utils`). Also a thread started after the schedule joining it.
- `slow.rs`: slow requests (get-ID, a write, its read-back) reaching a drive and coming back.
- `faults.rs`: a fault injected into one drive is caught by the bus thread before the next send, stopping only that
  drive's limb; a drive gone silent, and one that also loses its Disable, stop their limb for the silence. The rest of
  the fault tests (PLAN item 4, "Done when") join them as the safety layer lands.

Each test file uses a bus of its own, because every frame on a bus reaches every socket on it. The test binaries that
share `can0` (`slow`, `faults`) run one test at a time (nextest's `can0` test group, `.config/nextest.toml`); a new test
on a shared bus joins that group.

nextest's default profile leaves this crate out, so `scripts/check.sh` stays runnable on any machine; the `sim` profile
runs only this crate.

## Must never

Open an interface without checking it is `vcan` first (`sim_drive::ensure_vcan`, and `can::spawn`'s own check): the
sim's buses carry the robot's real names, so a test run on the Pi must not reach a real drive (testing.md rule 8). Never
sleep to wait: wait on a reply with a deadline (testing.md rule 6).

## Talks to

`sim-drive` (the drives under test), `can` (the bus thread under test), `telemetry` (its recording, read back),
`robstride` (the host's frames and the decoder), `vcan` through `socketcan`, and `candump`. See the
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
