# Kernel comparison on the Pi 5, 2026-11-13

**Status:** in progress. The method and the facts found before the first run are here; the result table fills in as each
run finishes.

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

Not covered: the runtime on `vcan` as extra load (it isn't deployed on the Pi yet), and the CAN round trip itself.
`cyclictest` measures how late a timer wake is; the buses' real margin is `can-bench`'s to measure, on wired buses.
Both CAN interfaces stayed down throughout.

## Results

The heavier load alone more than doubles the stock kernel's worst case: 676 µs here against 294 µs in the baseline, and
the average rises from 6 µs to between 13 and 19 µs. No sample went over 2000 µs.

| Run | Worst µs | Per core max µs | Peak °C | Throttled |
|---|---|---|---|---|
| `stock` | 676 | 541, 513, 494, 676 | 65.3 | no |
| `stock-isolated` | | | | |
| `rt` | | | | |
| `rt-isolated` | | | | |
