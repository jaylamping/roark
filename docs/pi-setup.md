# Setting up the robot's Pi from scratch

**Status:** first version, 2026-11-08, written for Joey's planned wipe of the Pi. Follows
[conventions/deploy.md](../conventions/deploy.md) and [conventions/remote-access.md](../conventions/remote-access.md); if a
step here and a convention disagree, the convention wins and this page gets fixed.

Until the repo has a `deploy/` folder and an image built with `rpi-image-gen`, these steps are done by hand. Each step that
should later move into `deploy/` or the image config is marked **(→ deploy/)**. When that happens, this page shrinks to "flash
the image, run the deploy script".

## 0. Before you wipe: back up the old Pi

The legacy stack's data holds bench history and right-arm facts that PLAN still needs (milestone 2 moves the right arm onto the
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
- Power from the official 27 W USB-C supply for setup, if you have one. Bench and battery power come later (step 4 covers it).

## 2. Flash the OS

With **Raspberry Pi Imager** on the Mac:

1. Device: Raspberry Pi 5. OS: **Raspberry Pi OS Lite (64-bit)**, the current release. Lite has no desktop, which the robot
   doesn't need.
2. Target: the NVMe drive (in a USB enclosure) or the SD card.
3. In the customisation settings:
   - Hostname: a plain name such as `robot-pi` (no robot name, tenet 7).
   - User: `joey` with a strong password (needed for `sudo`, never for SSH).
   - **SSH: allow public-key authentication only**, and paste the Mac's public key.
   - Wi-Fi only if the Pi won't be on Ethernet.
   - Locale and timezone.

## 3. First boot: update once, then freeze

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

Set (deploy.md section 6) **(→ deploy/)**:

```
BOOT_ORDER=0xf416        # NVMe first, then SD, then USB; skip if running from SD for now
PSU_MAX_CURRENT=5000     # the bench supply and battery don't negotiate USB power
```

Reboot, then check: `vcgencmd get_throttled` should print `throttled=0x0`.

## 5. Storage

- **Data partition** at `/var/lib/robot`, ext4, its own partition on the NVMe (deploy.md section 1). In `/etc/fstab`:

  ```
  /dev/nvme0n1p3  /var/lib/robot  ext4  defaults,noatime  0  2
  ```

  (Partition number depends on how you split the drive; use `lsblk` and the partition's `UUID=` rather than the device name.)

- Add `noatime` to the root filesystem's options in `/etc/fstab` too.
- **Swap off:** disable whichever swap service the release uses (`sudo systemctl disable --now dphys-swapfile` on older
  releases; check `swapon --show` afterwards prints nothing).

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

- `agent` gets **no** `sudo` and isn't in any group that can open real CAN interfaces.
- `/etc/ssh/sshd_config.d/robot.conf`: `PasswordAuthentication no` and `PermitRootLogin no`, then
  `sudo systemctl restart ssh`.

## 8. Tailscale

Follows [remote-access.md](../conventions/remote-access.md).

1. In the Tailscale policy, `tag:robot` must exist with Joey as its owner (remote-access.md section 2).
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
sudo ufw enable
```

## 10. Time

Chrony keeps the clock right for logs (PLAN "Observability") **(→ deploy/)**:

```bash
sudo apt install -y chrony
chronyc tracking
```

## 11. CAN

**(→ deploy/, as systemd-networkd files)**

- Enable systemd-networkd for CAN only: `sudo systemctl enable --now systemd-networkd`. It configures only interfaces that have a
  `.network` file, so it won't fight the Ethernet or Wi-Fi setup.
- Load `vcan` for simulation at boot: `echo vcan | sudo tee /etc/modules-load.d/vcan.conf`.
- Plug in the USB-CAN adapter and check: `dmesg | grep gs_usb` and `ip -details link show`.
- Until `deploy/` has the `.link` and `.network` files, bring a bus up by hand for testing only:

  ```bash
  sudo ip link set can1 type can bitrate 1000000 sample-point 0.75
  sudo ip link set can1 up
  ```

  (No `restart-ms`, no big `txqueuelen`: PLAN item 2 says not to copy the legacy settings.)
- If the MCP2515 HAT is still fitted, decide which `canN` names it keeps before the adapter takes `can1` (PLAN "Open with Joey"
  item 2).

## 12. Tools for measuring

```bash
sudo apt install -y can-utils rt-tests stress-ng
```

`rt-tests` gives `cyclictest` for the realtime measurement in deploy.md section 5. Set the CPU governor to `performance` when
measuring: `echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` **(→ deploy/)**.

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
- `ip -details link show can1` shows the adapter (when plugged in), and `ip link add dev vcan9 type vcan && ip link del vcan9`
  works.
- `apt-mark showhold` lists the kernel and firmware packages.
