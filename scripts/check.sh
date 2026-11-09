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
# The file size limit, LFS pointers included (conventions/cad.md rule 5). It reads git's file list, so it runs only in a git
# checkout: the dev box's copy has no .git, and the same tree was checked on the machine it came from.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  python3 tools/check_file_sizes.py
else
  echo "file size check: not a git checkout, skipped"
fi
