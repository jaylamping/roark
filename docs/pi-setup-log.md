# Pi setup log

What was set up on the robot's Pi and when ([pi-setup.md](pi-setup.md) section 13). Newest first. No addresses, keys or
network names here: the repo is public.

## 2026-11-13: reflash for the new stack

| | |
|---|---|
| Board | Raspberry Pi 5, Active Cooler, Waveshare 2-CH CAN FD HAT (MCP2518FD) on the header |
| Storage | SD card, 128 GB. No NVMe yet: `/var/lib/robot` is a folder on `/`, `BOOT_ORDER` left at `0xf461` |
| OS | Raspberry Pi OS Lite 64-bit, Debian 13 (trixie), image `2026-10-06-raspios-trixie-arm64-lite` |
| Kernel | `6.18.60+rpt-rpi-2712` after the one full-upgrade, then held |
| Bootloader | 2026/10/30 (was 2025/12/08), `PSU_MAX_CURRENT=5000` |
| Tailscale | 1.104.7, `tag:robot`, key expiry off, auto-update off |
| Hostname, user | `robot-pi`, `joey`; accounts `robot` and `agent` |
| Network | Wi-Fi |
| Set up with | `deploy/pi-setup.sh`, then `tailscale up` and a reboot by hand |

The old card (the legacy stack) was imaged whole before the wipe; the image and the files pulled from it are kept off
the repo.

**Checks after the reboot** (pi-setup.md "Checks when done"): `throttled=0x0`; no swap; `/` mounted `noatime`; kernel,
firmware and EEPROM packages held; password SSH refused, key SSH works; the Pi is on the tailnet as `tag:robot`;
`can0` (`spi0.0`) and `can1` (`spi1.0`) on driver `mcp251xfd`, 40 MHz clock, both reporting "MCP2518FD ... successfully
initialized", left down; `vcan` loaded; chrony synced; no failed units. `ufw status verbose`: active, incoming denied,
allowed in: everything on `tailscale0`, and SSH and mDNS from the LAN's IPv4 subnet, IPv6 link-local and the LAN's IPv6 /64.

**Different from pi-setup.md, or learned:**

- The customisation (hostname, user, key, Wi-Fi) went in as a cloud-init seed on the boot partition, which is how
  Raspberry Pi Imager does it for trixie images. The image was written raw and read back against its hash.
- `tag:robot` was not in the tailnet policy, so the first `tailscale up` failed with "requested tags [tag:robot] are
  invalid or not permitted". Section 8 now says to add it first.
- With `tailscale up --ssh`, SSH over the tailnet is refused until the policy has an `ssh` rule for `tag:robot`; plain
  OpenSSH to the tailnet address is refused too, because Tailscale answers port 22 there.
- The firewall needs mDNS (UDP 5353) from the LAN, or `robot-pi.local` stops resolving. The script and section 9 have it.
- The script's SSH rule for IPv6 names the LAN's current prefix, which the ISP can change. Then SSH over global IPv6
  is refused until the script is run again (a second run leaves the packages alone); IPv4, link-local and the tailnet are unaffected.
- A cable from the Pi straight to a PC gives no address without connection sharing on the PC. Use the router or a switch.
- The Wi-Fi link dropped for short spells during setup. Wired Ethernet is the plan for the robot.
- `can-bench` was not installed by the script (no binary beside it). It was installed afterwards from CI's `pi-binaries`
  artifact, checksum checked, and has not been given a bus.
- The script that ran is the one at 6a516b6. Later changes to it (the `agent` sudoers file, `00-robot.conf` for sshd, the
  once-only upgrade, the file writes by rename) have not run on a Pi; the sudoers file and `00-robot.conf` were
  put in by hand afterwards, and `sshd -T` shows passwords and root logins off.
- `systemd-networkd` is not enabled: `deploy/` has no `.link` or `.network` files for the buses yet, so the bus names
  follow probe order (`can0` on `spi0.0`, `can1` on `spi1.0` on this boot).

**First `cyclictest` run, not a baseline.** One hour under `stress-ng` with the section 12 commands, governor
`performance`, stock kernel: worst latency 614 µs (per core 614, 473, 612, 396; averages 5 to 7 µs; no sample over
1000 µs). The Pi overheated during it: 49 °C before, 81 °C after, `throttled=0xe0000` (frequency capped, throttled, soft
temperature limit; no under-voltage), and the fan's tachometer read 0 RPM while the kernel was driving it. A throttled CPU
makes the number worthless as a baseline, so nothing went into `docs/bench-results/realtime/`. Run it again once the
cooling works.

**Not done yet:** the cooling and the `cyclictest` baseline, the NVMe drive, wired Ethernet, the `tag:agent` rules in the
tailnet policy (remote-access.md section 2).
