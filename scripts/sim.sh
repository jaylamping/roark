#!/usr/bin/env bash
# CI gate 7, rust.md section 13: the sim suite against sim-drive on vcan. Linux only, with vcan can0 to can4 up (the dev
# box has them at boot, docs/dev-box.md; CI creates them). From the Mac: scripts/devbox.sh run ./scripts/sim.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# The disable tests run the real runtime and robot-cli binaries, which nextest doesn't build for another package's tests.
cargo build --workspace --bins --locked
cargo nextest run --workspace --locked --profile sim
