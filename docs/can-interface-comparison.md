# Comparing CAN interfaces on the Pi 5

**Purpose:** pick the CAN interface for every bus on measured numbers instead of the research's arithmetic. Run the same
test on each candidate, with no drive on the bus, and compare it against the realtime budget PLAN item 3 and
"Open with Joey" item 9 set. It moves the no-Enable half of PLAN step 8 ahead of the first drive, so the timing numbers
in `can::Timing` stop being guesses.

Nothing here sends a frame to a drive, so the Real hardware rule doesn't apply. Every drive is unplugged from the bus
anyway (`can-bench` README, "Must never").

## The candidates

| Interface | Driver | What it tests | Why it's in |
|---|---|---|---|
| MKS CANable **V1.0** Pro (STM32F072, isolated) with mainline candleLight | `gs_usb` | The pick in PLAN and the research: a USB adapter that buffers on its own chip | The default |
| The same board with its stock slcan firmware | `slcan` | The same hardware over a serial protocol | Shows what the firmware choice is worth |
| PEAK PCAN-USB FD (isolated) | `peak_usb` | High-speed USB (125 µs frames, against full-speed's 1 ms) | The upgrade if USB jitter eats the budget |
| Waveshare 2-CH isolated CAN FD HAT (MCP2518FD) | `mcp251xfd` | SPI with deep on-chip FIFOs: no USB in the path | The non-USB option; 2 buses per HAT |
| The MCP2515 HAT now fitted | `mcp251x` | The old interface, two receive buffers | The baseline that failed on the legacy stack |

Left out: Kvaser and Ixxat (the same class as PEAK; one premium sample is enough), the mjbots pi3hat (built for moteus,
Pi 5 support unconfirmed), and EtherCAT (RobStride drives speak only CAN). The MKS **V2.0** Pro uses an STM32G431, which
mainline candleLight doesn't support; check the chip before buying.

A second MKS V1.0 Pro with candleLight is the **reference adapter** on the dev box for every run, so only the interface
on the Pi changes between runs.

## Hardware

- The Pi 5 with the robot's image (docs/pi-setup.md), cooler fitted, `PSU_MAX_CURRENT` set.
- The dev box (docs/dev-box.md) with the reference adapter. Running the responder on a second machine keeps its work off
  the Pi.
- One short bus: about 1 m of twisted pair, CAN_H, CAN_L and GND between the two interfaces, 120 Ω at each end (each
  adapter's termination jumper or switch on). With power off, CAN_H to CAN_L reads about 60 Ω.
- For the five-at-once run: a powered multi-TT USB 2.0 hub (the Pi 5 has four USB ports).

## Preconditions

- [ ] No drive on the bus: every drive's CAN lead unplugged, not just disabled.
- [ ] `runtime` stopped on the Pi (`systemctl is-active runtime` says inactive).
- [ ] Both interfaces up at 1 Mbit/s, sample point 0.75, no `restart-ms` (pi-setup.md section 11). For slcan:
      `sudo slcand -o -c -s8 /dev/ttyACM0 slcan0 && sudo ip link set slcan0 up` (`-s8` is 1 Mbit/s).
- [ ] CPU governor `performance` on the Pi (pi-setup.md section 12); `can-utils`, `rt-tests` and `stress-ng` installed.
- [ ] The same `can-bench` build on both machines; note the commit.
- [ ] A 10 s run on `vcan` passes on each machine first (README, "Using it").

## Steps, for each candidate

1. **Identify it.** Record `ip -details link show <if>`, `dmesg | grep -iE 'gs_usb|slcan|peak|mcp251'`, and for a
   candleLight board its firmware version (`dmesg` prints it on plug-in). The summary records the driver and whether it
   gives hardware timestamps.
2. **Start the responder** on the dev box: `sudo chrt -f 80 can-bench respond --bus <reference> --slots 6`.
3. **Quiet run, 10 minutes**, nothing else loading the Pi:
   `sudo chrt -f 80 taskset -c 3 can-bench host --bus <if> --slots 6 --seconds 600 --out runs/<candidate>-quiet`.
4. **Loaded run, 1 hour.** Start the load on the other cores, then the same host command with `--seconds 3600` and
   `--out runs/<candidate>-loaded`:
   `taskset -c 0-2 stress-ng --vm 2 --vm-bytes 50% --cpu 2 --timeout 65m`.
5. **Bus-off.** Start a 60 s host run, short CAN_H to CAN_L for about 2 s at 20 s, then release. The summary counts the
   bus-off frames. `ticks.csv` shows whether replies came back by themselves and how long after the short, which says
   whether the interface restarts the bus on its own (candleLight does after about 100 ms, PLAN item 3). Note whether
   `ip -details link show` says `BUS-OFF` until it is set down and up.

Then, once the winner is bought for every bus (PLAN item 5: "only then buy adapters for the other buses"):

6. **Five at once.** All five interfaces on the Pi (through the hub if they are USB), each wired to its own reference
   adapter on the dev box with its own `can-bench respond`, and five hosts started together on the Pi, under the same
   load. This shows whether the interfaces slow each other down on the Pi's USB or SPI controllers. Five processes
   stand in for the runtime's five bus threads, so the pass mark is the same per bus.

The same steps also run with `--slots 5` for an arm-sized bus; the leg (6 slots, 12 frames a tick) is the tight case.

## Pass mark

From PLAN "Open with Joey" item 9 (the defaults until Joey changes them) and item 3, on the loaded run:

| What | Pass |
|---|---|
| Wake late, 99.9 % | under 500 µs |
| Replies read by the collect deadline (60 %, 2.4 ms at 250 Hz) | 99.9 % or more |
| Missing replies | none over the hour |
| Kernel `rx over_errors` and `dropped` | no change |
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
- Hardware left as found: the HAT's overlays restored if they were changed, the adapters unplugged.
