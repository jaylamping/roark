#!/usr/bin/env bash
# The local check: CI gates 1 to 5 of rust.md section 13, in CI's order. Run before every push.
set -euo pipefail
cd "$(dirname "$0")/.."

cargo fmt --all --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo nextest run --workspace --locked
cargo test --workspace --doc --locked
cargo deny check
python3 scripts/check_rules.py
python3 scripts/check_rules.py count
