# Comparing CAN interfaces on the Pi 5

**Purpose:** pick the CAN interface for every bus on measured numbers instead of the research's arithmetic. Run the same
test on each candidate, with no drive on the bus, and compare it against the realtime budget PLAN item 3 and
"Open with Joey" item 9 set. It moves the no-Enable half of PLAN step 8 ahead of the first drive, so the timing numbers
in `can::Timing` stop being guesses.

Nothing here sends a frame to a drive, so the Real hardware rule doesn't apply. Every drive is unplugged from the bus
anyway (`can-bench` README, "Must never").

## The candidates

The Pi's USB ports face out the back of the robot and stay free for external use (Joey, 2026-11-11), so the buses
connect through the GPIO header over SPI.

| Interface | Driver | What it tests |
|---|---|---|
| The Waveshare 2-CH isolated CAN HAT already on the Pi (MCP2515 + SN65HVD230) | `mcp251x` | The interface we have. The MCP2515 holds two received frames, so a host stall drops replies |
| Waveshare 2-CH isolated CAN **FD** HAT (MCP2518FD + MCP2562FD, about $55) | `mcp251xfd` | The same SPI path with the MCP2518FD's 2 KB on-chip RAM: a stall makes replies late instead of lost, with no USB in the path |

Each HAT tests itself: one channel runs the host, the other the responder, wired together on one short bus. A run where
the MCP2515 loses replies can't say which channel lost them, but the host channel's kernel counters (`rx over_errors`,
`dropped`) do; on the MCP2518FD a pass is a pass for both ends.

If the MCP2518FD passes, the robot's buses (five limbs, plus two if the hands get their own) need one MCP2518FD and
isolated transceiver per bus on a small CAN board on the header, which is the hardware side's design. Stacked HATs don't
fit the 33 mm Pi bay. Only if SPI misses the budget: a USB adapter on an internal hub (gs_usb, MKS CANable V1.0 Pro) or
a PCIe CAN card behind a PCIe switch, run through the same steps.

## Hardware

- The Pi 5 with the robot's image (docs/pi-setup.md), cooler fitted, `PSU_MAX_CURRENT` set, one HAT fitted at a time
  with its overlay (Waveshare's `mcp2515` or `mcp251xfd` lines in `config.txt`).
- One short bus between the HAT's two channels: about 1 m of twisted pair, CAN_H, CAN_L and GND, both channels'
  termination jumpers on. With power off, CAN_H to CAN_L reads about 60 Ω.

## Preconditions

- [ ] No drive on the bus: every drive's CAN lead unplugged, not just disabled.
- [ ] `runtime` stopped and masked for the session: `sudo systemctl mask --runtime --now runtime.service` (a reboot
  undoes it). `can-bench` refuses to start while the unit could start.
- [ ] Both interfaces up at 1 Mbit/s, sample point 0.75, no `restart-ms` (pi-setup.md section 11).
- [ ] CPU governor `performance` on the Pi (pi-setup.md section 12); `can-utils`, `rt-tests` and `stress-ng` installed.
- [ ] The `can-bench` commit noted.
- [ ] A 10 s run on `vcan` passes on the Pi first (README, "Using it").

## Steps, for each candidate

1. **Identify it.** Record `ip -details link show <if>` for both channels and `dmesg | grep -i mcp251`. The summary
   records the driver and whether it gives hardware timestamps.
2. **Start the responder** on the HAT's other channel, on its own core:
   `sudo chrt -f 80 taskset -c 2 can-bench respond --bus <other channel> --slots 6`.
3. **Quiet run, 10 minutes**, nothing else loading the Pi:
   `sudo chrt -f 80 taskset -c 3 can-bench host --bus <if> --slots 6 --seconds 600 --out runs/<candidate>-quiet`.
4. **Loaded run, 1 hour.** Start the load on the other cores, then the same host command with `--seconds 3600` and
   `--out runs/<candidate>-loaded`:
   `taskset -c 0-1 stress-ng --vm 2 --vm-bytes 50% --cpu 2 --timeout 65m`.
5. **Bus-off.** Start a 60 s host run, short CAN_H to CAN_L for about 2 s at 20 s, then release. The summary counts the
   bus-off frames. `ticks.csv` shows whether replies came back by themselves and how long after the short, which says
   whether the interface restarts the bus on its own. Note whether
   `ip -details link show` says `BUS-OFF` until it is set down and up.

Then, once the CAN board exists:

6. **Every bus at once.** One host per bus on the Pi, each bus wired to a responder on a second
   CAN board, started together under the same load. This shows whether the buses slow each other down on the
   Pi's SPI controllers and interrupt lines. One process per bus stands in for the runtime's bus threads, so the pass
   mark is the same per bus.

The same steps also run with `--slots 5` for an arm-sized bus; the leg (6 slots, 12 frames a tick) is the tight case.

## Pass mark

The first two rows are PLAN [Open with Joey](../PLAN.md#open-with-joey) item 9 (the defaults until Joey changes them).
The rest are this bench's own, proposed with it: each is a loss the runtime would act on. `can-bench` fails a run on
any of them, on the loaded run:

| What | Pass |
|---|---|
| Wake late, 99.9 % | under 500 µs |
| Replies read by the collect deadline (60 %, 2.4 ms at 250 Hz) | 99.9 % or more |
| Missing replies | none over the hour (proposed) |
| Requests refused by a full queue, wakes past the send window, ticks skipped | none (proposed) |
| Kernel `rx over_errors` and `dropped` | no change (proposed) |
| Bus-off | counted in the summary; the interface's own restart behaviour recorded |

A candidate that passes with margin at 250 Hz, 6 slots, is good for every bus. One that passes only at 5 slots is good
for an arm, not a leg.

## Data

Each run's `--out` folder (`ticks.csv`, `summary.txt`), plus the identify output from step 1 and the operator's notes.

## After

- Commit each run's `summary.txt` and the identify output under `docs/bench-results/can-interfaces/<date>/`, with a short
  README: the commit, which interface ran where, and anything that went wrong. The CSVs are too big for the repo
  (`tools/check_file_sizes.py`); keep them on the Pi's data partition and name where.
- The choice and its numbers go into PLAN (the adapter row of "When the hardware is ready", and item 5), and the
  hardware side's STATUS.md through Joey.
- If the chosen interface's collect timing differs from what `can::Timing` assumes (60 % of the period), that change is
  its own PR, with the numbers linked.
- Hardware left as found: the MCP2515 HAT and its overlay back on the Pi unless the result replaces it.
