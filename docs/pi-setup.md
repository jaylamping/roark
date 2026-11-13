# Setting up the robot's Pi from scratch

**Status:** first version 2026-11-08; 2026-11-11: SPI CAN HATs instead of a USB adapter, the OS release, the data
partition, and the bench tools. Follows
[conventions/deploy.md](../conventions/deploy.md) and [conventions/remote-access.md](../conventions/remote-access.md); if a
step here and a convention disagree, the convention wins and this page gets fixed.

Until the repo has a `deploy/` folder and an image built with `rpi-image-gen`, these steps are done by hand. Each step that
should later move into `deploy/` or the image config is marked **(→ deploy/)**. When that happens, this page shrinks to "flash
the image, run the deploy script".

## 0. Before you wipe: back up the old Pi

Skip this if the Pi has nothing from the legacy stack on it. The legacy stack's data holds bench history and right-arm facts that PLAN still needs (milestone 2 moves the right arm onto the
new stack). Copy these to the Mac **before** wiping. Nothing here goes into git.

| Path on the old Pi | What it is | Why keep it |
|---|---|---|
| `/opt/marengo/var/` | Logs, sessions, `calibration/zero_registry.yaml` | Right-arm zeros and bench history |
| `/opt/marengo/config/` | The config actually deployed | May differ from the repo; right-arm directions and limits |
| `/var/marengo.db` | Legacy store | Session history |
| `/etc/marengo/env` | Service environment | Contains tokens: keep it private, never commit it |
| `/etc/systemd/system/marengo-*.service`, `/etc/sudoers.d/marengo-*` | Units and sudo rules | Reference only |
| Any `candump` logs, `~/marengo-validation/` | Bench captures and validation runs | Bench lessons to lift (PLAN item 2) |
| `~/.ssh/authorized_keys` | Which keys could log in | To decide which keys to keep |

From the Mac:

```bash
mkdir -p ~/robot-pi-backup-2026-11
rsync -av --progress joey@<pi-address>:/opt/marengo/var ~/robot-pi-backup-2026-11/
rsync -av --progress joey@<pi-address>:/opt/marengo/config ~/robot-pi-backup-2026-11/
ssh joey@<pi-address> 'sudo cat /var/marengo.db' > ~/robot-pi-backup-2026-11/marengo.db
ssh joey@<pi-address> 'sudo cat /etc/marengo/env' > ~/robot-pi-backup-2026-11/marengo-env   # has tokens: keep private
ssh joey@<pi-address> 'tar czf - -C /home/joey marengo-validation' > ~/robot-pi-backup-2026-11/marengo-validation.tgz
```

Also in the Tailscale admin console: note the old Pi's machine name, and **remove the old node** after the wipe so the new install
doesn't end up with a `-1` name.

## 1. Hardware

- **NVMe SSD on the M.2 HAT+** if you have it (deploy.md section 1). If not yet, set up on the SD card now and move later; the
  steps are the same, only the boot order and data partition change.
- **Official Active Cooler** fitted.
- A **microSD card** (16 GB or more) as well: it's the recovery boot (deploy.md section 1), and section 5 boots from it to
  split the NVMe drive.
- **One CAN HAT** on the header (the MCP2515 HAT or the MCP2518FD CAN FD HAT, never both), its logic-level jumper on 3.3 V.
- Power from the official 27 W USB-C supply for setup, if you have one. Bench and battery power come later (step 4 covers it).

## 2. Flash the OS

With **Raspberry Pi Imager** on the Mac:

1. Device: Raspberry Pi 5. OS: **Raspberry Pi OS Lite (64-bit)**, the current release, based on Debian 13 (trixie) or
   newer. Lite has no desktop, which the robot doesn't need. **Not the bookworm-based "Legacy" image:** the binaries are
   cross-built on the dev box's Ubuntu 24.04 and need glibc 2.39 or newer; bookworm has 2.36.
2. Target: the NVMe drive (in a USB enclosure). Flash the SD card the same way, with the same settings: it boots the Pi
   while the NVMe drive is split (section 5) and stays as the recovery boot. Without an enclosure: boot the SD card,
   and write the NVMe drive from the Pi (`rpi-imager` or `dd` of the downloaded image); the customisation in step 3
   then has to go into the image's first-boot files by hand, so an enclosure is the easier way.
3. In the customisation settings:
   - Hostname: a plain name such as `robot-pi` (no robot name, tenet 7).
   - User: `joey` with a strong password (needed for `sudo`, never for SSH).
   - **SSH: allow public-key authentication only**, and paste the Mac's public key.
   - Wi-Fi only if the Pi won't be on Ethernet.
   - Locale and timezone.

## 3. First boot: update once, then freeze

**Sections 3 to 12 as one script:** [deploy/pi-setup.sh](../deploy/pi-setup.sh) does everything below except
`tailscale up`, the NVMe steps and the reboot. Copy it to the Pi (with `can-bench` and the agent's public key as
`agent-key.pub` next to it, if you have them) and run it detached, so a dropped SSH session can't stop it half-way:

```bash
sudo systemd-run --unit=pi-setup --collect bash /home/joey/setup/pi-setup.sh
sudo journalctl -fu pi-setup
```

The sections stay as the description of what it does, and for doing a step by hand.

```bash
ssh joey@robot-pi.local
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

Then stop anything from changing by itself (deploy.md section 6) **(→ image)**:

```bash
sudo apt purge -y unattended-upgrades || true
sudo apt-mark hold raspi-firmware linux-image-rpi-2712 linux-image-rpi-v8
sudo systemctl mask rpi-eeprom-update
```

Write down the kernel version (`uname -r`) and OS release (`cat /etc/os-release`) in the setup log (step 13).

## 4. Bootloader settings

```bash
sudo rpi-eeprom-config --edit
```

Set (deploy.md section 6) **(→ deploy/)**. Saving also moves the bootloader to the newest release on the Pi, so
don't cut power during the reboot that follows:

```
BOOT_ORDER=0xf416        # NVMe first, then SD, then USB; skip if running from SD for now
PSU_MAX_CURRENT=5000     # the bench supply and battery don't negotiate USB power
```

Reboot, then check: `vcgencmd get_throttled` should print `throttled=0x0`.

## 5. Storage

- **Data partition** at `/var/lib/robot`, ext4, its own partition on the NVMe (deploy.md section 1). The first boot
  grows the root partition to fill the drive, so make room afterwards, booted from the **SD card**. Section 4's
  `BOOT_ORDER=0xf416` tries NVMe first, so set `BOOT_ORDER=0xf461` (SD first) for this step, boot with the SD card in,
  and set it back afterwards. From the SD card, with the NVMe drive not mounted:

  ```bash
  lsblk                                          # nvme0n1p1 is boot, nvme0n1p2 is root
  sudo e2fsck -f /dev/nvme0n1p2
  sudo resize2fs /dev/nvme0n1p2 60G              # shrink the filesystem below the new partition size first
  sudo parted /dev/nvme0n1 resizepart 2 64GiB    # root partition ends at 64 GiB (answer Yes to the warning)
  sudo resize2fs /dev/nvme0n1p2                  # grow the filesystem back to fill the partition
  sudo parted /dev/nvme0n1 mkpart primary ext4 64GiB 100%
  sudo mkfs.ext4 -L robot-data /dev/nvme0n1p3
  ```

  64 GiB of root is plenty for the OS and the releases; the rest is data. Then boot from the NVMe again and add to
  `/etc/fstab`, by UUID (`sudo blkid /dev/nvme0n1p3`), not device name:

  ```
  UUID=<uuid>  /var/lib/robot  ext4  defaults,noatime  0  2
  ```

- Add `noatime` to the root filesystem's options in `/etc/fstab` too.
- **Swap off (→ deploy/):** trixie's `rpi-swap` sets up zram and `/var/swap`. Turn it off with a drop-in, then reboot:

  ```bash
  sudo mkdir -p /etc/rpi/swap.conf.d
  printf '[Main]\nMechanism=none\n' | sudo tee /etc/rpi/swap.conf.d/50-robot.conf
  ```

  `swapon --show` prints nothing afterwards. (Older releases used `dphys-swapfile`: `sudo systemctl disable --now
  dphys-swapfile`.)

## 6. Journald

`/etc/systemd/journald.conf.d/robot.conf` **(→ deploy/)**:

```ini
[Journal]
Storage=persistent
SystemMaxUse=512M
Compress=yes
```

`sudo systemctl restart systemd-journald`

## 7. Accounts

**(→ deploy/)**

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin robot   # runs the runtime
sudo useradd --create-home --shell /bin/bash agent                         # cloud agents (remote-access.md section 4)
sudo mkdir -p /var/lib/robot /etc/robot /opt/robot/releases
sudo chown robot:robot /var/lib/robot
```

- `agent` gets passwordless `sudo`, so agents can do setup and bench runs unattended
  ([remote-access.md section 4](../conventions/remote-access.md#4-accounts-on-the-pi) says what that costs). The file is
  checked before it goes in place, because a broken sudoers file locks everyone out of `sudo`:
  ```
  echo 'agent ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/020_agent
  sudo chmod 440 /etc/sudoers.d/020_agent && sudo visudo -cf /etc/sudoers.d/020_agent
  ```
- `/etc/ssh/sshd_config.d/robot.conf`: `PasswordAuthentication no` and `PermitRootLogin no`, then
  `sudo systemctl restart ssh`.

## 8. Tailscale

Follows [remote-access.md](../conventions/remote-access.md).

1. In the Tailscale policy, before `tailscale up`: `tag:robot` must be in `tagOwners` (without it the login fails with
   "requested tags [tag:robot] are invalid or not permitted"), and an `ssh` rule must name `tag:robot` as `dst`
   (remote-access.md sections 2 and 3). With `--ssh`, Tailscale answers port 22 on the tailnet address itself, so
   without that rule every SSH over the tailnet is refused, plain OpenSSH included.
2. On the Pi:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh --advertise-tags=tag:robot
   sudo tailscale set --auto-update=false
   ```

3. In the admin console: confirm the Pi shows `tag:robot` and key expiry is disabled, and remove the old Pi's node.
4. From the Mac: `ssh joey@<pi-name>` over the tailnet works, and Tailscale asks you to re-authenticate (check mode).

## 9. Firewall

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw allow in on tailscale0
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp   # home LAN SSH fallback; narrow to your actual subnet
sudo ufw allow from 192.168.0.0/16 to any port 5353 proto udp # mDNS, or <hostname>.local stops resolving
sudo ufw enable
```

## 10. Time

Chrony keeps the clock right for logs (PLAN "Observability") **(→ deploy/)**:

```bash
sudo apt install -y chrony
chronyc tracking
```

## 11. CAN

The buses connect through the GPIO header over SPI, never the USB ports, which face out the back of the robot for external
use (Joey, 2026-11-11). Until the robot's own CAN board exists, that's one Waveshare 2-channel HAT at a time.

**Overlays (→ image):** add the fitted HAT's block to the end of `/boot/firmware/config.txt` and reboot. Keep the other
block there commented out, so swapping HATs is one edit. The robot's buses run on the CAN FD HAT (both arms, Joey
2026-11-11), so its block is the live one.

```ini
# Waveshare 2-CH CAN FD HAT (MCP2518FD), mode A (the default: CAN_0 on SPI0, CAN_1 on SPI1).
dtparam=spi=on
dtoverlay=spi1-3cs
dtoverlay=mcp251xfd,spi0-0,interrupt=25
dtoverlay=mcp251xfd,spi1-0,interrupt=24

# Waveshare 2-CH CAN HAT (MCP2515, 16 MHz crystal). Interrupts at the board's default pads: CAN_0 GPIO 23, CAN_1 GPIO 25.
#dtparam=spi=on
#dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=23
#dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=25
```

**The skeleton names the driver.** Each bus in `config/skeleton.yaml` has a `driver`, and `runtime` refuses a bus whose
interface has another one: `mcp251xfd` for the CAN FD HAT, `mcp251x` for the MCP2515 HAT. Swapping HATs means swapping the
overlay block and those two lines. `can-bench` doesn't read the skeleton, so the interface comparison runs on either HAT
as it is.

The values are Waveshare's (the [2-CH CAN HAT](https://www.waveshare.com/wiki/2-CH_CAN_HAT) and
[2-CH CAN FD HAT](https://www.waveshare.com/wiki/2-CH_CAN_FD_HAT) wiki pages). If a board's interrupt pads were moved, the
`interrupt=` value moves with them. Neither page lists the Pi 5, so the check below is what proves it.

**Check after the reboot:**

```bash
dmesg | grep -i -E 'mcp251|spi'           # each channel probed, no "failed" or "clock" errors
ip -details link show type can             # two interfaces
ls -l /sys/class/net/can*/device           # which SPI device (spi0.0, spi0.1, spi1.0) each name has
```

The `canN` names follow probe order, not the label on the board, so read the HAT's channel off the SPI device. Waveshare's
udev renaming rules match a Pi 4 device path and don't apply to the Pi 5. Stable names come from `.link` files matched on
the SPI device path, in `deploy/` **(→ deploy/)**.

**Bringing a bus up (→ deploy/, as systemd-networkd files):**

- Enable systemd-networkd for CAN only: `sudo systemctl enable --now systemd-networkd`. It configures only interfaces that
  have a `.network` file, so it won't fight the Ethernet or Wi-Fi setup.
- Load `vcan` for simulation at boot: `echo vcan | sudo tee /etc/modules-load.d/vcan.conf`.
- Until `deploy/` has the `.link` and `.network` files, bring a bus up by hand for testing only, classic CAN at the
  robot's settings:

  ```bash
  sudo ip link set can0 type can bitrate 1000000 sample-point 0.75
  sudo ip link set can0 up
  ```

  No `restart-ms`, no `fd on`, no big `txqueuelen`: Waveshare's examples set all three, and PLAN item 2 says not to copy
  the legacy settings either.

## 12. Tools for measuring

```bash
sudo apt install -y can-utils rt-tests stress-ng
```

`can-utils` stays installed: its `candump` is what the black box runs (`candump@<bus>.service`, logging.md section 8.6).

`rt-tests` gives `cyclictest`. Set the CPU governor to `performance` when measuring (it resets at reboot)
**(→ deploy/)**:

```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

**`can-bench`** ([docs/can-interface-comparison.md](can-interface-comparison.md)): CI builds the Pi's binaries on every
commit and keeps them for 30 days as the `pi-binaries` artifact (with `GIT_REV` and `SHA256SUMS`). Fetch the one for
the commit being measured and copy it over:

```bash
gh run download --repo jaylamping/roark --name pi-binaries --dir /tmp/pi-binaries   # the latest run; -h for a given one
(cd /tmp/pi-binaries && sha256sum -c SHA256SUMS && cat GIT_REV)
scp /tmp/pi-binaries/can-bench joey@<pi-name>:setup/
```

Or cross-build it on the dev box and copy it over. The dev box needs the cross linker once (`.cargo/config.toml` names it):
`ssh -t joey-wsl 'sudo apt install -y gcc-aarch64-linux-gnu'`. Then, from the checkout at the commit being measured:

```bash
scripts/devbox.sh run cargo build --release --target aarch64-unknown-linux-gnu -p can-bench
scp joey-wsl:code/<folder>/target/aarch64-unknown-linux-gnu/release/can-bench /tmp/   # <folder>: the checkout's folder name
scp /tmp/can-bench joey@<pi-name>:/tmp/ && ssh joey@<pi-name> 'sudo install -m 755 /tmp/can-bench /usr/local/bin/'
```

It's a bench tool, never a service, and stays out of `/opt/robot` (the `deploy/` releases). Note the commit it was built
from in the run's notes.

**The first realtime measurement** (deploy.md section 5, PLAN step 8; no HAT or drive needed). One hour of `cyclictest`
under memory and CPU load, governor on `performance`:

```bash
mkdir -p ~/rt && cd ~/rt
stress-ng --vm 2 --vm-bytes 50% --cpu 4 --timeout 65m &
sudo cyclictest --mlockall --smp --priority=80 --interval=1000 --distance=0 --duration=1h \
  --histogram=1000 --histfile=cyclictest-hist.txt --quiet > cyclictest-summary.txt
```

The worst latency per core (`Max:` in the summary, `# Max Latencies` in the histogram file) is the number deploy.md compares against the budget. Commit both files
under `docs/bench-results/realtime/<date>/` with the kernel version (`uname -a`), and re-run after every kernel change.

## 13. Record what you set up

Keep a short setup log in the repo (for example `docs/pi-setup-log.md`): date, OS release, kernel version, EEPROM version
(`rpi-eeprom-update`), Tailscale version, NVMe or SD, and anything you did differently from this page. That's what lets the
next wipe come out the same, and it's the starting list for moving these steps into `deploy/` and the image config.

## Checks when done

- `vcgencmd get_throttled` prints `throttled=0x0`.
- `swapon --show` prints nothing.
- `findmnt /var/lib/robot` shows the ext4 data partition with `noatime`.
- `ssh` with a password is refused; key and Tailscale SSH work.
- `tailscale status` shows the Pi tagged `tag:robot`.
- `ip -details link show type can` shows the HAT's two channels, and `ip link add dev vcan9 type vcan && ip link del vcan9`
  works.
- `apt-mark showhold` lists the kernel and firmware packages.
