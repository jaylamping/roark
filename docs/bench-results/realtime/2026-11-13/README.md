# Realtime baseline, 2026-11-13: stock kernel, Pi 5

One hour of `cyclictest` under `stress-ng` memory and CPU load on the robot's Pi 5, as
[docs/pi-setup.md](../../../pi-setup.md) section 12 describes. This is the measurement deploy.md section 5 and PLAN
step 8 ask for. The runtime was not running (it isn't deployed yet), so this is the kernel's number, not the runtime's.

| | |
|---|---|
| Kernel | `6.18.60+rpt-rpi-2712` (`PREEMPT`, not `PREEMPT_RT`); full line in [uname.txt](uname.txt) |
| OS, storage | Raspberry Pi OS Lite 64-bit (trixie), SD card |
| CPU governor | `performance` |
| Started, finished | 2026-11-13 10:04:22 to 11:09:23 (UTC-06:00) |
| CAN HAT | Waveshare 2-CH CAN FD HAT fitted and detected; `can0` and `can1` down, nothing sent |
| Temperature | 35 °C before, 60 °C after, peak 62.0 °C; fan about 4,400 RPM; `throttled=0x0` on every sample |

## Result

| Core | Min µs | Avg µs | Max µs |
|---|---|---|---|
| 0 | 1 | 6 | 161 |
| 1 | 1 | 6 | 281 |
| 2 | 1 | 6 | 294 |
| 3 | 1 | 7 | 191 |

**Worst latency: 294 µs.** No sample over the 1000 µs histogram limit, in 3.6 million samples per core.

Whether 294 µs is inside the budget, and so whether `PREEMPT_RT` or CPU isolation is needed, is not decided here: PLAN
item 3 sets the budget. For scale, deploy.md quotes about 100 to 225 µs for `PREEMPT_RT` on a Pi 5 and over 9 ms for a
stock kernel under stress; this run is far below the second and a little above the first.

## Commands

Run as root, detached with `systemd-run`:

```bash
echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
stress-ng --vm 2 --vm-bytes 50% --cpu 4 --timeout 65m > stress-ng.txt 2>&1 &
cyclictest --mlockall --smp --priority=80 --interval=1000 --distance=0 --duration=1h \
  --histogram=1000 --histfile=cyclictest-hist.txt --quiet > cyclictest-summary.txt
```

## Files

- [cyclictest-hist-nonzero.txt](cyclictest-hist-nonzero.txt): the histogram file's comment lines and its 167 rows with a
  count. The 833 all-zero rows (0 µs, and everything from 295 to 999 µs among them) are left out; the column sums match
  the `# Total` line. Columns: latency in µs, then the count for cores 0 to 3.
- [temp-fan.txt](temp-fan.txt): temperature, fan speed, fan drive and `throttled` once a minute.
- [stress-ng.txt](stress-ng.txt): the load generator's own report.
- `cyclictest-summary.txt` held one line because of `--quiet` (`# /dev/cpu_dma_latency set to 0us`) and is not kept.

## The run before this one

An earlier run the same morning is not a baseline: the cooler's fan was not turning, the Pi reached 81 °C and throttled
(`throttled=0xe0000`), and the worst latency was 614 µs. Check `vcgencmd get_throttled` and the fan before trusting a run.
