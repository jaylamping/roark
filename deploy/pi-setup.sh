#!/usr/bin/env bash
# One-off setup of the robot's Pi 5 after the first boot: docs/pi-setup.md sections 3 to 12, for a Pi running
# from the SD card (no NVMe yet). Run once as:   sudo bash pi-setup.sh   (better: the systemd-run line below)
# Safe to run again: the upgrade, the bootloader, fstab and config.txt steps happen once; the small config files,
# the journald restart and the firewall rules are written again on every run. It never reboots by itself.
#
# Run it detached, so a dropped SSH session can't stop it half-way:
#   sudo systemd-run --unit=pi-setup --collect bash /home/joey/setup/pi-setup.sh && sudo journalctl -fu pi-setup
#
# Left for the operator afterwards (they need a browser or a decision): `tailscale up`, and the reboot.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=/var/log/robot-pi-setup.log
exec > >(tee -a "$LOG") 2>&1
step() { printf '\n=== %s ===\n' "$*"; }
export DEBIAN_FRONTEND=noninteractive
APT="apt-get -y -o Dpkg::Options::=--force-confold"

grep -q 'VERSION_CODENAME=trixie' /etc/os-release || { echo "not trixie: stop (pi-setup.md section 2)"; exit 1; }
grep -q 'Raspberry Pi 5' /proc/device-tree/model || { echo "not a Pi 5: stop"; exit 1; }

WARNINGS=""
warn() { echo "WARNING: $*"; WARNINGS="$WARNINGS\n  - $*"; }

step "3. update once"
# Once only: a later run (say, to refresh the firewall rules) must not upgrade a set-up robot. Updates after
# setup are a deliberate step with drives disabled (deploy.md section 6). UPGRADE=1 forces it.
UPGRADED=/var/lib/robot-pi-setup.upgraded
if [ ! -e "$UPGRADED" ] || [ "${UPGRADE:-0}" = 1 ]; then
  apt-get update
  $APT full-upgrade
  touch "$UPGRADED"
else
  echo "already upgraded once ($UPGRADED): skipped"
  apt-get update
fi

step "3. freeze: no automatic updates"
if dpkg -s unattended-upgrades >/dev/null 2>&1; then $APT purge unattended-upgrades; fi
HOLD=$(dpkg-query -W -f='${Package}\n' 'linux-image-rpi-*' raspi-firmware rpi-eeprom 2>/dev/null || true)
if [ -n "$HOLD" ]; then
  # shellcheck disable=SC2086  # a list of package names, split on purpose
  apt-mark hold $HOLD
else
  warn "no kernel, firmware or EEPROM package found to hold"
fi
systemctl mask rpi-eeprom-update.service

step "12. tools: can-utils, rt-tests, stress-ng; 10. chrony; 9. ufw"
$APT install can-utils rt-tests stress-ng chrony ufw

step "4. bootloader: PSU_MAX_CURRENT=5000 (BOOT_ORDER left alone: SD card for now)"
if rpi-eeprom-config | grep -q '^PSU_MAX_CURRENT=5000'; then
  echo "already set"
else
  T=$(mktemp)
  rpi-eeprom-config | grep -v '^PSU_MAX_CURRENT=' > "$T"
  echo 'PSU_MAX_CURRENT=5000' >> "$T"
  # Staged; applied at the next reboot. With no image named, --apply also moves the bootloader to the newest
  # release in the rpi-eeprom package: the setup session's one deliberate bootloader update (deploy.md
  # section 6). Don't cut power during that reboot.
  rpi-eeprom-config --apply "$T"
  rm -f "$T"
fi

step "5. storage: noatime on /, swap off, data folder"
if awk '$2=="/" && $4 !~ /noatime/ {f=1} END{exit !f}' /etc/fstab; then
  cp -a /etc/fstab /etc/fstab.before-robot-setup
  # Write beside it, check, sync, rename (deploy.md section 2): a power cut never leaves half an fstab.
  awk 'BEGIN{OFS="\t"} $1 !~ /^#/ && $2=="/" && $4 !~ /noatime/ {$4=$4",noatime"} {print}' \
    /etc/fstab > /etc/fstab.new
  findmnt --verify --tab-file /etc/fstab.new || { rm -f /etc/fstab.new; echo "fstab check failed: left as it was"; exit 1; }
  chmod --reference=/etc/fstab /etc/fstab.new
  sync -f /etc/fstab.new
  mv /etc/fstab.new /etc/fstab
fi
mkdir -p /etc/rpi/swap.conf.d
printf '[Main]\nMechanism=none\n' > /etc/rpi/swap.conf.d/50-robot.conf

step "6. journald: persistent, capped"
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=persistent\nSystemMaxUse=512M\nCompress=yes\n' > /etc/systemd/journald.conf.d/robot.conf
systemctl restart systemd-journald

step "7. accounts and folders"
id robot >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin robot
id agent >/dev/null 2>&1 || useradd --create-home --shell /bin/bash agent
mkdir -p /var/lib/robot /etc/robot /opt/robot/releases
chown robot:robot /var/lib/robot
# Passwordless sudo for `agent` (remote-access.md section 4), checked before it is put in place.
T=$(mktemp)
echo 'agent ALL=(ALL) NOPASSWD:ALL' > "$T"
visudo -cf "$T" && install -m 440 -o root -g root "$T" /etc/sudoers.d/020_agent
rm -f "$T"
# The agent account's key (remote-access.md section 4: agents never log in as Joey). If the key file was put next
# to this script, install it for `agent` and take the same key out of joey's list.
if [ -s "$HERE/agent-key.pub" ]; then
  install -d -m 700 -o agent -g agent /home/agent/.ssh
  install -m 600 -o agent -g agent "$HERE/agent-key.pub" /home/agent/.ssh/authorized_keys
  # The key itself is the field after the key type, wherever that is (a line may start with options).
  keyblob='{for (i = 1; i < NF; i++) if ($i ~ /^(ssh-|ecdsa-|sk-)/) {print $(i+1); exit}}'
  KEY=$(awk "$keyblob" "$HERE/agent-key.pub")
  JK=/home/joey/.ssh/authorized_keys
  [ -n "$KEY" ] || { echo "agent-key.pub holds no public key: stop"; exit 1; }
  has_key='{for (i = 1; i <= NF; i++) if ($i == k) f = 1} END {exit !f}'
  if [ -f "$JK" ] && awk -v k="$KEY" "$has_key" "$JK"; then
    # Drop only lines that hold exactly this key; keep comments and every other key.
    awk -v k="$KEY" '{for (i = 1; i <= NF; i++) if ($i == k) next} {print}' "$JK" > "$JK.new"
    if grep -qE '^[^#]*(ssh-|ecdsa-|sk-)' "$JK.new"; then
      chown joey:joey "$JK.new" && chmod 600 "$JK.new"
      sync -f "$JK.new"
      mv "$JK.new" "$JK"
    else
      rm -f "$JK.new"
      warn "the agent's key is Joey's only key, so it was left in his list: the agent can still log in as Joey. Add Joey's own key, then run this again"
    fi
  fi
fi
# sshd keeps the first value it reads, so this file has to sort before 50-cloud-init.conf and the rest.
rm -f /etc/ssh/sshd_config.d/robot.conf
printf 'PasswordAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/00-robot.conf
sshd -t
systemctl reload ssh
sshd -T | grep -qx 'passwordauthentication no' || { echo "sshd still allows passwords: stop"; exit 1; }
sshd -T | grep -qx 'permitrootlogin no' || { echo "sshd still allows root logins: stop"; exit 1; }

step "9. firewall: deny incoming except tailscale0, and SSH and mDNS from this LAN"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow in on tailscale0
NETS="fe80::/10"
V4=$(ip -o -4 route show scope link | awk '$1 ~ /\// {print $1}')
[ -n "$V4" ] || warn "no IPv4 network was up, so SSH from the LAN is allowed over IPv6 link-local only. Run this again once the Pi has its address"
for n in $V4 $(ip -o -6 route show | awk '$1 ~ /\/64$/ && $1 !~ /^fe80/ {print $1}'); do NETS="$NETS $n"; done
for n in $NETS; do
  ufw allow from "$n" to any port 22 proto tcp
  ufw allow from "$n" to any port 5353 proto udp     # mDNS, so robot-pi.local keeps resolving
done
ufw --force enable
ufw status verbose

step "11. CAN: HAT overlays in config.txt, vcan at boot"
CFG=/boot/firmware/config.txt
if ! grep -q 'robot CAN HAT' "$CFG"; then
  cp -a "$CFG" "$CFG.before-robot-setup"
  # Whole new file, sync, rename: a power cut can't leave the marker without the overlays under it.
  { cat "$CFG"; cat <<'EOF'

[all]
# --- robot CAN HAT (docs/pi-setup.md section 11): one block live, the other commented ---
# Waveshare 2-CH CAN FD HAT (MCP2518FD), mode A (the default: CAN_0 on SPI0, CAN_1 on SPI1).
dtparam=spi=on
dtoverlay=spi1-3cs
dtoverlay=mcp251xfd,spi0-0,interrupt=25
dtoverlay=mcp251xfd,spi1-0,interrupt=24

# Waveshare 2-CH CAN HAT (MCP2515, 16 MHz crystal). Interrupts at the board's default pads: CAN_0 GPIO 23, CAN_1 GPIO 25.
#dtparam=spi=on
#dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=23
#dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=25
EOF
  } > "$CFG.new"
  sync -f "$CFG.new"
  mv "$CFG.new" "$CFG"
  sync -f "$CFG"
fi
echo vcan > /etc/modules-load.d/vcan.conf
# systemd-networkd is not enabled here: deploy/ has no .link/.network files for the buses yet.

step "12. can-bench"
if [ -s "$HERE/can-bench" ]; then
  install -m 755 "$HERE/can-bench" /usr/local/bin/can-bench
  sha256sum /usr/local/bin/can-bench
else
  echo "no can-bench next to this script: skipped"
fi

step "8. Tailscale: install only"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh

step "report (for the setup log, section 13)"
{
  date -Is
  . /etc/os-release; echo "os: $PRETTY_NAME"
  echo "kernel running: $(uname -r)"
  echo "eeprom: $(rpi-eeprom-update 2>/dev/null | grep -m1 CURRENT || true)"
  echo "tailscale: $(tailscale version 2>/dev/null | head -1)"
  echo "held: $(apt-mark showhold | tr '\n' ' ')"
  echo "throttled: $(vcgencmd get_throttled)"
  echo "storage: SD card, /var/lib/robot is a folder on / (no NVMe yet)"
} | tee "$HERE/setup-report.txt"
chown joey:joey "$HERE/setup-report.txt" 2>/dev/null || true

cat <<'EOF'

Finished. Still to do by hand:
  1. sudo tailscale up --ssh --advertise-tags=tag:robot   (opens a login link; the tailnet policy must
     already own tag:robot and have an ssh rule for it: docs/pi-setup.md section 8)
     sudo tailscale set --auto-update=false
  2. sudo reboot      (swap off, the bootloader setting and the CAN overlays take effect)
Not done by this script: the NVMe steps and BOOT_ORDER, systemd-networkd and the bus names, the CPU governor,
and the cyclictest run (docs/pi-setup.md sections 4, 5, 11 and 12).
EOF
if [ -n "$WARNINGS" ]; then printf '\nWARNINGS, read these:%b\n' "$WARNINGS"; exit 2; fi
