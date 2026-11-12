#!/usr/bin/env bash
# Run this checkout on the Linux dev box (Ubuntu in WSL on joey-pc) from the Mac. What it is, how it connects and how to
# rebuild it: docs/dev-box.md.
#
#   scripts/devbox.sh doctor              # check every hop, say what's wrong and how to fix it
#   scripts/devbox.sh run <command...>    # copy this checkout over, then run the command in it (cargo on PATH)
#   scripts/devbox.sh sync                # only copy this checkout over
#   scripts/devbox.sh shell               # an interactive shell in the copy
#   scripts/devbox.sh ssh-config          # the ~/.ssh/config lines this script needs
#
# Example: scripts/devbox.sh run ./scripts/check.sh
set -euo pipefail

host=${DEVBOX_HOST:-joey-wsl}      # the WSL Ubuntu, reached through the jump host
jump=${DEVBOX_JUMP:-joey-pc}       # Windows OpenSSH on the PC, over Tailscale
distro=${DEVBOX_DISTRO:-Ubuntu-24.04}
repo=$(cd "$(dirname "$0")/.." && pwd)
remote=code/$(basename "$repo")    # one copy per checkout folder, so two worktrees don't overwrite each other
buses="can0 can1 can2 can3 can4"   # created at boot by roark-vcan.service on the box

ssh_config() {
    cat <<EOF
# roark dev box (docs/dev-box.md). Windows on joey-pc, over Tailscale:
Host $jump
  HostName joey-pc.tail0b414.ts.net
  HostKeyAlias $jump
  User joeyl
  IdentityFile ~/.ssh/id_ed25519

# Ubuntu in WSL on that PC. The proxy runs nc inside WSL, which also starts WSL if it was stopped.
Host $host
  User joeyl
  IdentityFile ~/.ssh/id_ed25519
  HostKeyAlias $host
  ProxyCommand ssh $jump wsl -d $distro -- nc 127.0.0.1 2222
EOF
}

sync() {
    ssh -o ConnectTimeout=30 "$host" "mkdir -p '$remote'"
    # The working tree as it is, uncommitted changes included; .gitignore'd paths (target/) stay on each side.
    rsync -az --delete --filter=':- .gitignore' --exclude .git/ "$repo/" "$host:$remote/"
}

# The copy has no .git, so the build can't see its revision: hand it over (bins/runtime/build.rs).
revision() {
    local head
    head=$(git -C "$repo" rev-parse HEAD 2>/dev/null) || return 0   # nothing: the build warns and records unknown
    if [ -n "$(git -C "$repo" status --porcelain 2>/dev/null || echo failed)" ]; then
        echo "$head-dirty"
    else
        echo "$head"
    fi
}

run() {
    [ $# -gt 0 ] || { echo "usage: $0 run <command...>" >&2; exit 2; }
    sync
    ssh -o ConnectTimeout=30 "$host" \
        "cd '$remote' && . ~/.cargo/env && ROARK_GIT_REVISION='$(revision)' $(printf '%q ' "$@")"
}

ok() { printf '  ok    %s\n' "$1"; }
bad() {
    printf '  FAIL  %s\n' "$1"
    shift
    printf '        %s\n' "$@"
    exit 1
}

doctor() {
    echo "dev box: $host via $jump"
    # shellcheck disable=SC2088  # the ~ is message text, not a path
    ssh -G "$host" 2>/dev/null | grep -qi '^proxycommand ' \
        || bad "~/.ssh/config has no '$host' entry" "Add the lines from: $0 ssh-config"
    ok "ssh config has $jump and $host"

    local addr
    addr=$(ssh -G "$jump" 2>/dev/null | awk '/^hostname /{print $2}')
    nc -z -G 5 "$addr" 22 >/dev/null 2>&1 \
        || bad "can't reach $addr port 22" \
            "Is Tailscale connected on this Mac? 'tailscale status | grep joey-pc' should not say offline." \
            "If the PC says offline, it is asleep or off: wake it, or ask Joey."
    ok "$jump answers on port 22 over Tailscale"

    ssh -o BatchMode=yes -o ConnectTimeout=10 "$jump" "echo ok" >/dev/null 2>&1 \
        || bad "$jump refused this Mac's key" \
            "Joey authorizes the key once on the PC: docs/dev-box.md, 'Connecting a new Mac'."
    ok "Windows on $jump accepts this Mac's key"

    ssh -o BatchMode=yes -o ConnectTimeout=60 "$host" true >/dev/null 2>&1 \
        || bad "Windows answers but WSL's sshd doesn't" \
            "Restart it: ssh $jump wsl -d $distro -u root -- systemctl restart ssh" \
            "Then run this again. Still failing: docs/dev-box.md, 'When it breaks'."
    ok "Ubuntu in WSL accepts this Mac's key"

    local report
    # shellcheck disable=SC2087  # $buses, $remote and $0 expand here on purpose; \$ marks what expands on the box
    report=$(ssh "$host" "bash -s" <<EOF
. ~/.cargo/env 2>/dev/null || true
for b in $buses; do ip link show "\$b" 2>/dev/null | grep -q 'UP' || echo "missing vcan \$b"; done
rustup run "\$(sed -n 's/^channel *= *"\(.*\)".*/\1/p' ~/$remote/rust-toolchain.toml 2>/dev/null || echo none)" rustc --version >/dev/null 2>&1 \
    || echo "pinned toolchain not installed (or no copy yet: run '$0 sync')"
command -v cargo-nextest >/dev/null || echo "cargo-nextest missing"
command -v cargo-deny >/dev/null || echo "cargo-deny missing"
python3 -m pytest --version >/dev/null 2>&1 || echo "pytest missing (apt-get install python3-pytest)"
EOF
    )
    [ -z "$report" ] || bad "the box is missing pieces:" "$report" "Rebuild steps: docs/dev-box.md, 'Rebuilding the box'."
    ok "vcan $buses up; pinned Rust, nextest, cargo-deny and pytest installed"
    echo "ready: $0 run ./scripts/check.sh"
}

cmd=${1:-}
[ $# -gt 0 ] && shift
case "$cmd" in
    doctor) doctor ;;
    run) run "$@" ;;
    sync) sync ;;
    # No revision handed to the shell: the copy may be re-synced while it stays open, and a stale one would be wrong.
    shell) sync && ssh -t "$host" "cd '$remote' && exec bash -l" ;;
    ssh-config) ssh_config ;;
    *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
