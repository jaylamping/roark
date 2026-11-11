# Deploying to and running on the Pi

**Status:** proposed for Joey's review, 2026-11-08.

How files are laid out, stored, installed and run on the robot's Raspberry Pi 5. PLAN
["Repo, toolchain, CI and deploy"](../PLAN.md#repo-toolchain-ci-and-deploy) holds what's decided: cross-build, copy to
`/opt/robot`, the `runtime.service` and `candump@<bus>.service` units and their key settings, and no self-update machinery.
How to reach the Pi is in [remote-access.md](remote-access.md). Setting up a fresh Pi step by step is in
[docs/pi-setup.md](../docs/pi-setup.md). This page covers everything else on the Pi itself, so the robot
behaves the same after every boot, every deploy and every power cut.

**The principle:** the Pi is an appliance, not a workstation. Everything on it comes from this repo (`deploy/`) or from a
pinned OS image, and nobody changes it by hand without putting the change back into git.

## 1. Storage

- **The Pi boots and runs from an NVMe SSD** (on the M.2 HAT), not the SD card. An SD card can stay in as a recovery boot.
  **Why:** recordings write a few MB/s continuously (logging.md section 8); SD cards wear out under that and stall for hundreds
  of milliseconds, which is the most likely cause of lost data. The SSD itself is a hardware choice.
- **Partitions:**

  | Mount | Contents | Options |
  |---|---|---|
  | `/boot/firmware` | Firmware and kernel | read-only |
  | `/` | OS and `/opt/robot` | ext4, `noatime`; read-only with an overlay once the setup settles |
  | `/var/lib/robot` | Sessions, `candump` logs, state | its own ext4 partition, `noatime`, default `data=ordered` |

- **No swap.**
- **Never** `barrier=0` or `data=writeback`. They trade power-loss safety for speed.
- **Files that must survive a power cut are written safely:** write a temp file, `fsync`, then `rename` over the old one. Never
  overwrite in place. Recordings get the same protection by closing chunks and files regularly (logging.md section 8).
- **Power loss is normal,** first from the bench supply and later from the battery. The robot must boot cleanly after any cut.
  A pulled plug gives almost no warning (the power board has no hold-up capacitors), so ext4 journaling and the safe writes
  above are what protect the data.
- **A low pack is a planned shutdown.** The power board's power-fail line and the software low-pack limits are specified in
  [REV_B_PARTS.md](../hardware/power-board/REV_B_PARTS.md) and
  [PLAN item 10](../PLAN.md#10-power-board-interface-milestone-4). One shutdown path in the runtime handles every trigger, in
  this order: stop the motors (the normal stop sequence), record the event, close the recording, `sync`, remount
  `/var/lib/robot` read-only, then `systemctl poweroff`. It's tested on `vcan` with the trigger simulated.

**Why:** Raspberry Pi's own whitepaper on resilient file systems recommends exactly this set. Each item protects against a way
a sudden power cut corrupts data.

## 2. File layout

| Path | Holds | Set up by |
|---|---|---|
| `/opt/robot/releases/<git-rev>/` | Binaries and `deploy/` files for one build | The deploy script |
| `/opt/robot/current` | Symlink to the running release | The deploy script |
| `/etc/robot/` | `skeleton.yaml`, `dynamics.yaml` and other config from the repo | The deploy script (`ConfigurationDirectory=robot`) |
| `/var/lib/robot/sessions/` | One directory per session (PLAN "Observability") | The runtime (`StateDirectory=robot`) |
| `/var/lib/robot/candump/` | Rotated, compressed black-box logs | The `candump@` units |
| `/run/robot/` | The runtime's lock (`runtime.lock`, held while it runs; `robot-cli disable` refuses while it is held), later the `api` socket | systemd (`RuntimeDirectory=robot`) |

- **No robot name in paths,** units or users (tenet 7). It's `robot`, not the robot's current name.
- **Bulk data lives in `/var/lib/robot`, not `/var/log`.** `/var/log` and journald are for text logs.
- **Keep the last three releases** so a rollback is one symlink swap.

## 3. Deploying

The deploy script (in the repo, run from a laptop or an agent over SSH) does, in order:

1. **Refuse if any drive is enabled.** It asks the runtime through `robot-cli`; no answer means refuse. Deploying stops the
   runtime, and that must never happen in the middle of a motion.
2. Copy the build to a **new** release directory, `releases/<git-rev>/`.
3. **Verify** every file against a checksum manifest that includes the git revision.
4. Install config to `/etc/robot/` (the safe write from section 1).
5. **Switch `current` atomically:** make a temporary symlink and `mv -T` it over `current`. (`ln -sfn` is not atomic: it deletes
   and then creates.)
6. Restart the runtime, which starts with every drive disabled (PLAN item 3).
7. Check the runtime is up and reports the expected git revision and skeleton hash.

**Rollback** is the same switch pointed at a previous release. If the project ever packages releases as `.deb` files
(`cargo-deb`), the package must not start or restart the runtime by itself.

## 4. Services

PLAN lists the units and their main settings. The conventions for writing them:

- **The runtime runs as its own system user** (`robot`), never root. It gets exactly the capabilities it needs through
  `AmbientCapabilities=` with the same list in `CapabilityBoundingSet=`: realtime scheduling (`CAP_SYS_NICE`), memory locking
  (`CAP_IPC_LOCK`), raw CAN sockets (`CAP_NET_RAW`), and `CAP_NET_ADMIN` only if it must set socket buffers beyond the default.
- **Hardening that doesn't fight realtime:** `NoNewPrivileges=yes`, `ProtectSystem=strict` with `ReadWritePaths=/var/lib/robot`,
  `PrivateTmp=yes`, `CPUSchedulingResetOnFork=yes` (child processes don't inherit realtime priority). **Never
  `RestrictRealtime=yes`**: it blocks the realtime threads.
- **The runtime starts after its CAN interfaces exist** (`After=` and `BindsTo=` on each bus's device unit), but **doesn't depend
  on the network, Tailscale or the internet**.
- **CAN links are configured by systemd-networkd files in `deploy/`:** a `.link` file per adapter matched on its USB serial
  (stable name, short TX queue), and a `.network` file per bus (bitrate, sample point). `RequiredForOnline=no`, so boot doesn't
  wait for CAN. No shell scripts calling `ip link` (PLAN item 2: don't copy the legacy `can-up.sh`).
- **The `api` socket's group and mode** enforce motion authority together with the runtime's own rules
  ([remote-access.md section 4](remote-access.md#4-accounts-on-the-pi)).
- **journald is persistent with a size cap** (for example `SystemMaxUse=512M`) and compressed. No `log2ram` or RAM-only
  journald: they lose exactly the logs you need after a crash or power cut.

## 5. Realtime tuning

PLAN item 3 says PREEMPT_RT only if the Pi's measurement misses its budget. How that measurement and the tuning are done:

- **Measure first, on the real image:** `cyclictest` (or `rtla timerlat`) for at least an hour **under load** (`stress-ng`
  including memory pressure, plus the runtime on `vcan`), with the result committed per kernel version. **Why:** worst case
  under load is what matters. Published Pi 5 numbers show a stock kernel can exceed 9 ms under stress, while PREEMPT_RT stays
  around 100 to 225 µs, so expect the measurement to point at RT.
- **If RT is needed:** Raspberry Pi ships no RT kernel, so it's built from the Raspberry Pi kernel tree with `PREEMPT_RT`
  (merged in mainline since 6.12), packaged, and held. Real-time Ubuntu for Pi is the alternative to evaluate.
- **CPU isolation:** realtime bus threads get their own cores (`isolcpus`, `nohz_full`, `rcu_nocbs` on those cores,
  `irqaffinity` to the others); the recorder, UI bridge and everything else stay off them. Which cores depends on the bus count
  and is decided by the measurement.
- **Check where interrupts really land** (`/proc/interrupts`). On the Pi 5, USB and GPIO interrupts arrive through the RP1 chip,
  and moving them has had kernel bugs. Don't assume it worked.
- **CPU governor `performance`** so clocks don't change under the loop.
- **Cooling and power are watched:** the official Active Cooler fitted; the runtime reads the Pi's throttling and under-voltage
  flags (`vcgencmd get_throttled`) once a second, records them, and **refuses enable** while under-voltage or throttling is
  active. **Why:** a throttled CPU misses ticks.

## 6. The OS

- **The OS image is built from config in git** (Raspberry Pi's `rpi-image-gen`), so a new SD card or SSD can be rebuilt exactly.
- **No automatic updates of anything:** no `unattended-upgrades`, kernel and firmware packages held, bootloader EEPROM updates
  applied only on purpose, Tailscale auto-update off. Never `rpi-update` (pre-release firmware).
- **Updates are a deliberate session:** drives disabled, update, reboot, re-run the realtime measurement if the kernel changed,
  note the versions.
- **EEPROM settings live in `deploy/` too:** boot order (NVMe first) and `PSU_MAX_CURRENT=5000`, because the bench supply and
  the battery don't negotiate USB power the way the official PSU does, and without it the Pi limits its USB ports.
- **Later, if OS updates become routine:** the Pi firmware's built-in A/B boot (`tryboot`) gives safe OS updates with rollback.
  Not needed now (tenet 4).

## 7. Security basics

- SSH by key only, no passwords. Access over Tailscale or the home LAN only ([remote-access.md](remote-access.md)).
- Firewall denies incoming by default.
- No services listening on anything but localhost, a Unix socket, or what `tailscale serve` publishes.

## Checklist for a change to `deploy/`

- Is every change on the Pi coming from `deploy/` or the image config, not from hand edits?
- Could a deploy or update happen with a drive enabled?
- Does a new unit run as root, use `RestrictRealtime`, or depend on the network to start?
- Does anything write to the SD card or overwrite a file in place?

## Sources

- Raspberry Pi whitepaper, "Making a more resilient file system":
  https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-003610-WP-3-Making%20a%20more%20resilient%20file%20system.pdf
- Raspberry Pi USB power delivery on the Pi 5 (`PSU_MAX_CURRENT`):
  https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009856-WP-1-USB%20Power%20delivery%20on%20Raspberry%20Pi%205.pdf
- NVMe boot on the Pi 5: https://www.jeffgeerling.com/blog/2023/nvme-ssd-boot-raspberry-pi-5
- systemd service settings: https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html
- Atomic symlink switch: https://deployer.org/blog/atomic-symlinks
- Pi 5 realtime latency measurements: https://spinics.net/lists/linux-rt-users/msg28144.html and
  https://arxiv.org/abs/2604.19275; RP1 interrupt affinity issue: https://github.com/raspberrypi/linux/issues/7301
- CPU isolation boot options: https://ubuntu.com/real-time/docs/how-to/cpu-boot-configs/; measuring latency:
  https://canonical-real-time-ubuntu-documentation.readthedocs-hosted.com/how-to/measure-maximum-latency/
- Throttling flags: https://www.raspberrypi.com/documentation/computers/os.html
- rpi-image-gen: https://www.raspberrypi.com/news/introducing-rpi-image-gen-build-highly-customised-raspberry-pi-software-images/
- Firmware A/B boot (`tryboot`): https://raspberrypi.com/documentation/computers/config_txt.html
- systemd-networkd for multiple CAN adapters: https://klipper.discourse.group/t/multiple-can-adapters-under-systemd/24552
