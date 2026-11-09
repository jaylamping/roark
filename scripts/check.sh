#!/usr/bin/env bash
# The local check: CI gates 1 to 5 of rust.md section 13, in CI's order. Run before every push.
set -euo pipefail
cd "$(dirname "$0")/.."

cargo fmt --all --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo nextest run --workspace --locked
cargo test --workspace --doc --locked
# The crate READMEs are the crate docs (rust.md section 11): rustdoc's lints (broken item links, bad HTML tags, bare
# URLs, unknown code-block attributes) fail here. Markdown that merely renders wrong does not.
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps --locked
cargo deny check
python3 scripts/check_rules.py
python3 scripts/check_rules.py count
# No file of 100 MB or more, LFS pointers included (conventions/cad.md rule 5).
python3 tools/check_file_sizes.py
# The tracked CAD layout and the CAD tool tests (conventions/cad.md section 5).
python3 tools/cad/check_cad_layout.py --repo --quiet
python3 -m pytest -q tools/cad
