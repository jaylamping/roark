# Kernel comparison on the Pi 5, 2026-11-13

**Result:** under the same heavy load, the worst timer wake-up was 676 µs on the stock kernel, 253 µs on the stock
kernel with two isolated cores, 116 µs on Raspberry Pi's `PREEMPT_RT` kernel, and 158 µs on that kernel with two
isolated cores. Which kernel the robot runs is not decided here; the Pi was left on the stock kernel.

The [baseline](../2026-11-13/README.md) on the stock kernel was 294 µs worst case under CPU and memory load. This
compares four setups under a heavier load, to answer PLAN item 3's question (is `PREEMPT_RT` needed) and deploy.md
section 5's (which cores to isolate) with numbers from our own Pi.

## Setups

| Run | Kernel | Command line |
|---|---|---|
| `stock` | `6.18.60+rpt-rpi-2712` (`PREEMPT`, 16K pages) | stock |
| `stock-isolated` | same | stock plus `isolcpus=2,3 irqaffinity=0,1` |
| `rt` | `6.18.60+rpt-rpi-v8-rt` (`PREEMPT_RT`, 4K pages) | stock |
| `rt-isolated` | same | stock plus `isolcpus=2,3 irqaffinity=0,1` |

Facts that shaped this:

- The RT kernel is Raspberry Pi's own package, `linux-image-rpi-v8-rt`, at the stock kernel's version. Its config has
  `CONFIG_PREEMPT_RT=y`, 4K pages, `HZ=250`, and the `mcp251xfd` and `pwm-fan` drivers as modules. There is no Pi 5
  specific (`2712`) RT package.
- Neither kernel has `CONFIG_RCU_NOCB_CPU` or `CONFIG_NO_HZ_FULL`, so `rcu_nocbs=` and `nohz_full=` do nothing on them.
  Isolation here is `isolcpus` and `irqaffinity` only.
- On the stock setup every device interrupt lands on CPU 0 (both SPI controllers through RP1, the SD card, Wi-Fi's SDIO,
  USB); only the timer is spread over all four cores.

## Method

Same load and measurement for every run, one hour each, governor `performance`, detached with `systemd-run`:

```bash
stress-ng --vm 2 --vm-bytes 50% --cpu 4 --hdd 1 --hdd-bytes 256M --sock 2 --timeout 65m
cyclictest --mlockall --smp --priority=80 --interval=1000 --distance=0 --duration=1h --histogram=2000 \
  --histfile=cyclictest-hist.txt --quiet
```

The load adds SD card writes and socket traffic to the baseline's. On the isolated runs `cyclictest` runs on the isolated
cores only (`--affinity=2,3 --threads=2` in place of `--smp`) and `stress-ng` is kept on cores 0 and 1 with `taskset`.

Each setup other than `stock` is a one-shot trial boot (`tryboot.txt` and `reboot '0 tryboot'`): `config.txt` and
`cmdline.txt` are never edited, and a plain reboot or a power cycle returns to the stock kernel and command line.

Both CAN interfaces stayed down throughout. What this method does not cover is under [Limits](#limits).

## Results

All four on 2026-11-13, one hour each, 3.6 million samples per measured core, no sample over the 2000 µs histogram
limit, `throttled=0x0` on every per-minute sample, `stress-ng` passed 9 of 9, and no filesystem, SD card, under-voltage,
RCU stall or hung-task lines in the kernel log.

| Run | Cores measured | Avg µs per core | Max µs per core | Worst µs | Rows over 100 µs | Peak °C |
|---|---|---|---|---|---|---|
| `stock` | 0 to 3 | 13, 19, 19, 17 | 541, 513, 494, 676 | **676** | 264 | 65.3 |
| `stock-isolated` | 2, 3 | 2, 1 | 182, 253 | **253** | 29 | 59.8 |
| `rt` | 0 to 3 | 13, 17, 17, 16 | 115, 112, 116, 112 | **116** | 13 | 64.8 |
| `rt-isolated` | 2, 3 | 1, 1 | 158, 119 | **158** | 10 | 59.8 |

Times (UTC-06:00): `stock` 12:48:46 to 13:53:52, `stock-isolated` 14:55:35 to 16:00:43, `rt` 16:18:33 to 17:23:37,
`rt-isolated` 17:38:26 to 18:43:37.

What the numbers say:

- **The load matters as much as the kernel.** SD card writes and socket traffic more than double the stock kernel's worst
  case: 676 µs here against 294 µs in the baseline, with the average up from 6 µs to between 13 and 19 µs.
- **`PREEMPT_RT` fixes the tail and leaves the average alone.** 676 µs becomes 116 µs with the measured threads sharing
  all four cores with the load; the average stays at 13 to 17 µs.
- **Isolation fixes the average on either kernel** (1 to 2 µs), and on the stock kernel it also cuts the tail to 253 µs.
  The isolated cores carry nothing else, so this is what realtime threads on reserved cores would see, at the price of two
  cores for everything else.
- **RT with isolation was not better than RT alone on the worst case.** Its 158 µs is one sample on core 2 (the next are
  151 and 142 µs; core 3's worst is 119 µs). With one hour per case, 116 against 158 µs is within run-to-run spread: it
  shows isolation did not help the RT kernel's worst case here, not that it hurt.
- In both isolated runs `stress-ng` stayed on cores 0 and 1, `cyclictest` on cores 2 and 3, and the device interrupts
  (both SPI controllers, both SD/SDIO controllers) on CPU 0.

## Limits

- One hour per case, one run each. Differences of a few tens of µs between cases are not established.
- `cyclictest` measures how late a timer wake-up is. The CAN round trip through the SPI HAT and the `mcp251xfd` driver is
  `can-bench`'s to measure, on wired buses; under `PREEMPT_RT` interrupt handlers become threads, and their priorities
  against the bus threads may need setting.
- The runtime was not part of the load (it isn't deployed on the Pi yet). SD card, not NVMe; Wi-Fi, not Ethernet.
- The RT kernel is the generic arm64 build with 4K pages, where the stock Pi 5 kernel uses 16K. What that costs the
  runtime in throughput was not measured.
- Neither kernel has `RCU_NOCB_CPU` or `NO_HZ_FULL`, so the isolation tested is `isolcpus` and `irqaffinity` only.

## A run that does not count

A first `stock` run (11:35:38 to 12:40:47) had the RT kernel package being installed inside it, from 12:30:23 to
12:34:02. It reached 794 µs (per core 640, 532, 499, 794). The histogram has no timestamps, so the install's share of
that can't be separated out; the run was repeated and is not in the table.

## Files

One folder per run (`stock/`, `stock-isolated/`, `rt/`, `rt-isolated/`):

- `run.txt`: `uname -a`, start and end, temperature and `throttled` before and after, and the two commands as run.
- `cyclictest-hist-over-100us.txt`: the histogram file's comment lines and every row above 100 µs with a count. Columns:
  latency in µs, then the count per measured core. These rows were transcribed from the files on the Pi, not copied
  byte for byte; in each, the row counts and the highest row per core agree with the file's own `# Max Latencies` line.
  The full histograms (2000 rows each) and the per-minute temperature and fan logs are kept off the repo.
- `stress-ng.txt`: the load generator's report.

The command line in every run was the image's stock one, with ` isolcpus=2,3 irqaffinity=0,1` appended on the isolated
runs.

## State left on the Pi

Stock kernel and stock command line by default, verified after a plain reboot. `config.txt`, `cmdline.txt` and the stock
kernel image match their checksums from before the comparison; `tryboot.txt` and the trial command-line file are removed.
The four RT packages (`linux-image-rpi-v8-rt` and its three dependencies, 1:6.18.60-1+rpt1) are installed and held, with
`kernel8_rt.img` and `initramfs8_rt` on the boot partition. Both CAN interfaces were down in every boot and nothing was
sent on them.
