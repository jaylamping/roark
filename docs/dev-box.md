# The Linux dev box

**Status:** set up 2026-11-08 (Joey's PC, configured by an agent with Joey). This page is the one place that says how it
works; if the box and this page disagree, fix whichever is wrong in the same PR.

The Mac can't run Linux-only things: virtual CAN (`vcan`), SocketCAN, and so the `sim-drive` suite (PLAN item 4). Joey's
Windows PC is always on, so it runs an Ubuntu (in WSL, Windows' built-in Linux VM) that does. You keep editing on the Mac;
[`scripts/devbox.sh`](../scripts/devbox.sh) copies your checkout over and runs a command there.

CI on GitHub is still the gate (rust.md section 13). The box is for your own loop: running the `vcan` tests before you push,
long soaks, big builds. It has 32 cores and 31 GB of memory (WSL's default, half the PC's 64 GB, kept on purpose: Joey,
2026-11-08). `ssh joey-wsl 'nproc; free -g'` shows the current numbers.

**On the Mac you need:** Tailscale connected, the key `~/.ssh/id_ed25519` (authorized on the box, see "Connecting a new
Mac"), the `~/.ssh/config` lines below, and the stock `ssh`, `rsync` and `nc`.

## Start here

From any roark checkout on the Mac:

```bash
scripts/devbox.sh doctor
```

It checks each hop below in order and stops at the first one that fails, with the fix. When it prints `ready`:

```bash
scripts/devbox.sh run ./scripts/check.sh           # the whole local check, on Linux
scripts/devbox.sh run cargo nextest run -p can     # any command; the cargo toolchain is on PATH
scripts/devbox.sh shell                            # an interactive shell in the copy
```

`run` copies the working tree as it is, uncommitted changes included, to `~/code/<checkout folder name>` on the box, then
runs the command there. Each checkout folder gets its own copy, so two worktrees don't overwrite each other. Build output
(`target/`) stays on each side and is never copied. Nothing is copied back: if a command writes a file you need, fetch it with
`scp joey-wsl:code/<folder>/<path> .`

**`run` or plain `ssh`?** Use `run` for anything that builds or tests the repo: it copies your checkout first and puts cargo
on PATH. For a one-off command that doesn't need the code (`candump`, `ip link`, `nproc`), plain `ssh joey-wsl '<command>'` is
fine and skips the copy; cargo isn't on PATH there unless you start with `. ~/.cargo/env`.

**Smoke test that frames flow on `vcan`** (`doctor` only checks the buses are up):

```bash
ssh joey-wsl 'timeout 2 candump -n 1 can1 & sleep 0.3; cansend can1 123#DEADBEEF; wait'
# prints:  can1  123   [4]  DE AD BE EF
```

## How it connects

```
 Mac ──Tailscale──▶ joey-pc (Windows, OpenSSH, port 22) ──wsl.exe──▶ Ubuntu-24.04 in WSL (sshd on 127.0.0.1:2222)
       ssh joey-pc                                            ssh joey-wsl (ProxyCommand through joey-pc)
```

| Hop | What answers | How it's reached | Auth |
|---|---|---|---|
| 1. The PC on the tailnet | `joey-pc.tail0b414.ts.net` | Tailscale on the Mac and on Windows | Tailscale login (already done on both) |
| 2. Windows | OpenSSH Server for Windows 9.5, port 22, user `joeyl` (an administrator) | `ssh joey-pc` | The Mac's `~/.ssh/id_ed25519` key, listed in `C:\ProgramData\ssh\administrators_authorized_keys` |
| 3. Ubuntu in WSL | `sshd` listening on `127.0.0.1:2222` inside WSL, key only | `ssh joey-wsl`, whose ProxyCommand runs `wsl -d Ubuntu-24.04 -- nc 127.0.0.1 2222` on Windows | The same key, in `/home/joeyl/.ssh/authorized_keys` |

Why hop 3 goes through `wsl.exe` and `nc`: WSL's network is private to the PC, so nothing on the tailnet can reach it
directly. Running `nc` through `wsl.exe` pipes the SSH connection into WSL, and it starts WSL if it was stopped. Nothing
needed a second Tailscale login or a port opened on Windows.

The `~/.ssh/config` lines on the Mac (`scripts/devbox.sh ssh-config` prints them):

```
Host joey-pc
  HostName joey-pc.tail0b414.ts.net
  HostKeyAlias joey-pc
  User joeyl
  IdentityFile ~/.ssh/id_ed25519

Host joey-wsl
  User joeyl
  IdentityFile ~/.ssh/id_ed25519
  HostKeyAlias joey-wsl
  ProxyCommand ssh joey-pc wsl -d Ubuntu-24.04 -- nc 127.0.0.1 2222
```

`HostKeyAlias` stores each host key under the short name, so the connection keeps working if the tailnet name or IP changes.

## What's on the box

| Piece | Where | Notes |
|---|---|---|
| Windows | Joey's PC, 64 GB RAM | Other WSL distros live on it (JetPack SDK, Docker Desktop, an older Ubuntu, Debian). Leave them alone. |
| WSL | 3.0.3, kernel 6.18.54.1-microsoft-standard-WSL2 | The stock kernel has `CONFIG_CAN_VCAN=m`; nothing custom |
| `%UserProfile%\.wslconfig` | Windows | `vmIdleTimeout=-1` and `instanceIdleTimeout=-1` so WSL keeps running when no session is open; memory stays at the default. Takes effect after the next `wsl --shutdown`; until then WSL may stop when idle, which the ProxyCommand handles by starting it again. |
| Ubuntu | distro `Ubuntu-24.04`, default user `joeyl`, systemd on (`/etc/wsl.conf`) | |
| `sshd` | `/etc/ssh/sshd_config.d/10-roark.conf`: port 2222, `127.0.0.1` only, no passwords, no root | `ssh.service` enabled |
| Virtual buses | `roark-vcan.service` (`/etc/systemd/system/`) creates `can0` to `can4` at boot | The skeleton's bus names (PLAN item 4), so the runtime runs unchanged. Up already; tests never need root. |
| Rust | `rustup` in `~/.cargo`, toolchain pinned by `rust-toolchain.toml` (rustfmt, clippy, the aarch64 target) | After a pin bump: `scripts/devbox.sh run rustup toolchain install` |
| Test tools | `cargo-nextest` 0.9.151 and `cargo-deny` 0.20.2 in `~/.cargo/bin` | The versions CI pins |
| Packages | `build-essential`, `pkg-config`, `can-utils` (`candump`, `cansend`, `cangen`), `rsync`, `netcat-openbsd`, `openssh-server`, `curl` | |

## Rules

- **The box has no CAN hardware.** Its `can0` to `can4` are `vcan`, so anything goes there (CLAUDE.md: `vcan` is always
  fine). It never talks to a real drive.
- **Root inside WSL:** `ssh joey-pc wsl -d Ubuntu-24.04 -u root -- <command>`. `sudo` as `joeyl` asks for a password nobody
  has given an agent; don't set one or add sudo rules. Most work needs no root.
- **Ask Joey before restarting WSL** (`wsl --shutdown`, `wsl --terminate`) or rebooting the PC. It ends his open WSL
  terminals and the other distros. **Why:** he works on the PC too.
- **Install what a task needs, and record it here** in the same PR, so the next rebuild matches. The box is rebuilt from this
  page, never from memory.
- **No secrets on the box.** It holds only the Mac's public key and the code. Nothing in it is a credential.

## Connecting a new Mac (or a new key)

Joey does this once on the PC, in PowerShell as Administrator, with the new Mac's public key (`cat ~/.ssh/id_ed25519.pub` on
that Mac):

```powershell
$k = '<the public key line>'
Add-Content "$env:ProgramData\ssh\administrators_authorized_keys" $k
icacls "$env:ProgramData\ssh\administrators_authorized_keys" /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

`joeyl` is an administrator, and Windows' sshd reads administrators' keys only from that file, and ignores it unless only
Administrators and SYSTEM can read it (the `icacls` line). Then, from a Mac that already connects, add the key to WSL too:

```bash
ssh joey-wsl 'cat >> ~/.ssh/authorized_keys' <<< '<the public key line>'
```

On the new Mac: add the `scripts/devbox.sh ssh-config` lines to `~/.ssh/config`, then `ssh joey-pc echo ok` and
`ssh joey-wsl echo ok`, accepting each host key once. Compare it with `ssh-keygen -F joey-pc -l` on the old Mac.

## When it breaks

`scripts/devbox.sh doctor` names the failing hop. By symptom:

| Symptom | Cause | Fix |
|---|---|---|
| `can't reach ... port 22` | Tailscale off on the Mac, or the PC asleep or off | `tailscale status \| grep joey-pc`. Offline means the PC: ask Joey to wake it. |
| `Host key verification failed` | The PC's key changed (Windows reinstalled) or the alias is new | Ask Joey whether the PC was rebuilt before accepting a new key |
| `joey-pc refused this Mac's key` | The key isn't in `administrators_authorized_keys`, or the file's permissions are wrong | Joey reruns the PowerShell block above |
| `Windows answers but WSL's sshd doesn't` | WSL stopped and sshd didn't come up, or `nc` is missing | `ssh joey-pc wsl -d Ubuntu-24.04 -u root -- systemctl restart ssh`; if `nc` is missing, `ssh joey-pc wsl -d Ubuntu-24.04 -u root -- apt-get install -y netcat-openbsd` |
| `missing vcan canN` | `roark-vcan.service` didn't run | `ssh joey-pc wsl -d Ubuntu-24.04 -u root -- systemctl restart roark-vcan`, then `journalctl -u roark-vcan` |
| `pinned toolchain not installed` | `rust-toolchain.toml` was bumped | `scripts/devbox.sh run rustup toolchain install` (it reads the pin) |
| A long command dies when the SSH session ends | `.wslconfig`'s idle settings aren't applied yet (WSL not restarted since 2026-11-08) | Keep the session open (`run` does), or ask Joey to restart WSL |
| PowerShell output comes back as spaced-out letters | `wsl.exe` writes UTF-16 | Pipe it through `iconv -f UTF-16LE -t UTF-8` |

## Rebuilding the box

From scratch on a Windows PC with WSL and Tailscale installed and the OpenSSH Server optional feature on (Settings → System
→ Optional features), signed in as an administrator. Every step is safe to rerun.

1. **Ubuntu:** `wsl --install -d Ubuntu-24.04` in PowerShell (creates user `joeyl`). Put this in `/etc/wsl.conf` and run
   `wsl --shutdown`:

   ```ini
   [boot]
   systemd=true

   [user]
   default=joeyl
   ```

2. **Windows key:** the PowerShell block in "Connecting a new Mac".
3. **`.wslconfig`** in `%UserProfile%`, then `wsl --shutdown`:

   ```ini
   [general]
   instanceIdleTimeout=-1

   [wsl2]
   vmIdleTimeout=-1
   ```

4. **Packages, sshd, the WSL key and the buses**, from the Mac (`scripts/devbox.sh` can't reach WSL yet, so this goes
   through `wsl -u root`):

   ```bash
   ssh joey-pc 'wsl -d Ubuntu-24.04 -u root -- bash -s' <<'EOF'
   export DEBIAN_FRONTEND=noninteractive
   apt-get update -qq
   apt-get install -y -qq openssh-server rsync netcat-openbsd can-utils build-essential pkg-config curl
   printf 'Port 2222\nListenAddress 127.0.0.1\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' \
     >/etc/ssh/sshd_config.d/10-roark.conf
   install -d -m 700 -o joeyl -g joeyl /home/joeyl/.ssh
   echo '<the Mac public key line>' >>/home/joeyl/.ssh/authorized_keys
   chown joeyl:joeyl /home/joeyl/.ssh/authorized_keys && chmod 600 /home/joeyl/.ssh/authorized_keys
   systemctl disable --now ssh.socket; systemctl enable --now ssh.service; systemctl restart ssh.service
   cat >/etc/systemd/system/roark-vcan.service <<'U'
   [Unit]
   Description=Virtual CAN buses can0..can4 for roark's sim tests
   After=systemd-modules-load.service

   [Service]
   Type=oneshot
   RemainAfterExit=yes
   ExecStart=/usr/sbin/modprobe vcan
   ExecStart=/bin/sh -c 'for b in can0 can1 can2 can3 can4; do ip link show "$b" >/dev/null 2>&1 || ip link add dev "$b" type vcan; ip link set "$b" up; done'
   ExecStop=/bin/sh -c 'for b in can0 can1 can2 can3 can4; do ip link del "$b" 2>/dev/null; done; true'

   [Install]
   WantedBy=multi-user.target
   U
   systemctl daemon-reload && systemctl enable --now roark-vcan.service
   EOF
   ```

   `ssh.socket` is turned off so `sshd` runs as a plain service that reads its own config.

5. **Rust and the test tools**, as `joeyl` (the versions match `.github/workflows/ci.yml`):

   ```bash
   ssh joey-wsl 'bash -s' <<'EOF'
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
   . ~/.cargo/env
   curl -LsSf https://get.nexte.st/0.9.151/linux | tar zxf - -C ~/.cargo/bin
   curl -LsSf https://github.com/EmbarkStudios/cargo-deny/releases/download/0.20.2/cargo-deny-0.20.2-x86_64-unknown-linux-musl.tar.gz \
     | tar zxf - --strip-components=1 -C ~/.cargo/bin cargo-deny-0.20.2-x86_64-unknown-linux-musl/cargo-deny
   EOF
   ```

6. **Check:** `scripts/devbox.sh run rustup toolchain install` (installs the pinned toolchain), then `scripts/devbox.sh doctor`
   and `scripts/devbox.sh run ./scripts/check.sh`.
