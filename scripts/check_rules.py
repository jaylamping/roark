#!/usr/bin/env python3
"""Repo rules that the compiler and clippy can't check (rust.md section 13, testing.md "Automated checks", docs.md 5).

  deps    crate dependencies only point the way architecture.md section 3 allows
  lines   no source file passes 800 lines
  guards  every test has a `Guards:` line directly above it
  sleep   no sleeping in test code
  todo    no bare TODO; write TODO(name) or link an issue
  docs    every package's README is its crate doc, with the sections and example rust.md section 11 asks for
  count   print the number of tests per crate (information, never fails)

Run with no arguments for all checks. Exits non-zero if any check fails.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# architecture.md section 3. Each workspace crate lists the workspace crates it may depend on. A crate missing from this
# table fails the check: add it here and to the map in the same PR.
ALLOWED_DEPS = {
    "robstride": set(),
    "skeleton": {"robstride"},
    "sim-drive": {"robstride", "skeleton"},
    "sim-suite": {"robstride", "sim-drive"},
}

# rust.md section 11. Each workspace package's README.md is its crate doc, by kind: a library shows its API in a Rust
# example that runs as a doc test; a binary or the sim suite shows its commands. A package missing here fails the check.
DOC_KIND = {
    "robstride": "library",
    "skeleton": "library",
    "sim-drive": "library",  # its library is what the sim suite drives; the README also covers the binary
    "sim-suite": "tests",
}
DOC_INCLUDE = '#![doc = include_str!("../README.md")]'
DOC_SECTIONS = ["## What it does", "## Must never", "## Talks to", "## Using it"]
ARCHITECTURE_URL = "https://github.com/jaylamping/roark/blob/main/conventions/architecture.md"
# A relative link resolves on GitHub but not in rustdoc (target/doc/<crate>/), and rustdoc doesn't warn.
RELATIVE_LINK = re.compile(r"\]\((?!https?://|#)")
# `[`Item`]` is a rustdoc link that GitHub shows as literal brackets; name items in plain backticks.
ITEM_LINK = re.compile(r"\[`[^`]+`\](?!\()")
RUST_FENCE = re.compile(r"^```rust\s*$")

MAX_LINES = 800
GUARDS = re.compile(r"^\s*///\s*Guards: (bug|safety|protocol|number) - \S")
TEST_ATTR = re.compile(r"^\s*#\[(test|tokio::test)\b")
SLEEP = re.compile(r"\b(thread::sleep|tokio::time::sleep)\b")
BARE_TODO = re.compile(r"\bTODO\b(?!\()")
ISSUE_LINK = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/issues/\d+")


def rust_files():
    return sorted(p for p in ROOT.rglob("*.rs") if "target" not in p.parts)


def check_deps():
    meta = json.loads(
        subprocess.run(
            ["cargo", "metadata", "--format-version", "1", "--no-deps"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
    )
    names = {p["name"] for p in meta["packages"]}
    errors = []
    for pkg in meta["packages"]:
        name = pkg["name"]
        if name not in ALLOWED_DEPS:
            errors.append(f"{name}: not in the dependency table; add it to architecture.md section 3 and this script")
            continue
        for dep in pkg["dependencies"]:
            if dep["name"] in names and dep["name"] not in ALLOWED_DEPS[name]:
                errors.append(f"{name} -> {dep['name']}: edge not allowed by architecture.md section 3")
    return errors


def check_docs():
    meta = json.loads(
        subprocess.run(
            ["cargo", "metadata", "--format-version", "1", "--no-deps"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
    )
    errors = []
    for pkg in meta["packages"]:
        name = pkg["name"]
        kind = DOC_KIND.get(name)
        if kind is None:
            errors.append(f"{name}: not in DOC_KIND; give it a README (rust.md section 11) and add it here")
            continue
        manifest = Path(pkg["manifest_path"])
        readme = manifest.parent / "README.md"
        where = readme.relative_to(ROOT)
        if not readme.is_file():
            errors.append(f"{where}: missing; it is the crate doc (rust.md section 11)")
            continue
        targets = {t["kind"][0]: Path(t["src_path"]) for t in pkg["targets"]}
        root = targets.get("lib") or targets.get("bin")
        first = next((l for l in root.read_text().splitlines() if l.strip()), "")
        if first.strip() != DOC_INCLUDE:
            errors.append(f"{root.relative_to(ROOT)}: must open with {DOC_INCLUDE}")
        text = readme.read_text()
        lines = text.splitlines()
        for section in DOC_SECTIONS:
            if section not in lines:
                errors.append(f"{where}: no '{section}' section")
        if ARCHITECTURE_URL not in text:
            errors.append(f"{where}: link the map, {ARCHITECTURE_URL}")
        fenced = False
        for i, line in enumerate(lines):
            if line.startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            prose = re.sub(r"`[^`]*`(?!\])", "", line)
            if RELATIVE_LINK.search(prose):
                errors.append(f"{where}:{i + 1}: relative link; use a full GitHub URL (it breaks in rustdoc)")
            if ITEM_LINK.search(line):
                errors.append(f"{where}:{i + 1}: rustdoc item link; GitHub shows it as brackets, use plain backticks")
        has_rust = any(RUST_FENCE.match(l) for l in lines)
        has_shell = any(l.strip() == "```bash" for l in lines)
        if kind == "library" and not has_rust:
            errors.append(f"{where}: a library README needs a ```rust example that runs (not ignore or no_run)")
        if kind in ("binary", "tests") and not has_shell:
            errors.append(f"{where}: needs a ```bash block showing how to run it")
    return errors


def check_lines():
    errors = []
    for path in rust_files():
        n = len(path.read_text().splitlines())
        if n > MAX_LINES:
            errors.append(f"{path.relative_to(ROOT)}: {n} lines, cap is {MAX_LINES}")
    return errors


def is_test_code(path, lines, i):
    return "tests" in path.parts or any("#[cfg(test)]" in line for line in lines[:i])


def check_guards():
    errors = []
    for path in rust_files():
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if not TEST_ATTR.match(line):
                continue
            j = i - 1
            # Skip the attributes between the doc comment and #[test], including ones that span lines.
            while j >= 0 and not lines[j].strip().startswith("///"):
                stripped = lines[j].strip()
                if stripped.startswith("#["):
                    j -= 1
                    continue
                k = j
                while k >= 0 and not lines[k].strip().startswith("#[") and not lines[k].strip().startswith("///"):
                    k -= 1
                if k >= 0 and lines[k].strip().startswith("#[") and (stripped.endswith("]") or stripped.endswith(",")
                                                                      or stripped.endswith("(")):
                    j = k - 1
                    continue
                break
            docs = []
            while j >= 0 and lines[j].strip().startswith("///"):
                docs.append(lines[j])
                j -= 1
            if not any(GUARDS.match(d) for d in docs):
                errors.append(f"{path.relative_to(ROOT)}:{i + 1}: test without a `/// Guards: <kind> - ...` line")
    return errors


def check_sleep():
    errors = []
    for path in rust_files():
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if SLEEP.search(line) and is_test_code(path, lines, i):
                errors.append(f"{path.relative_to(ROOT)}:{i + 1}: sleeping in test code; pass the time in instead")
    return errors


def check_todo():
    errors = []
    skip = {"target", ".git"}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or skip & set(path.parts) or path.suffix not in {".rs", ".md", ".toml", ".yaml", ".yml", ".py", ".sh"}:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        for i, line in enumerate(path.read_text().splitlines()):
            # A TODO quoted as code is prose about TODOs; one with an issue link on its line is tracked.
            if BARE_TODO.search(re.sub(r"`[^`]*`", "", line)) and not ISSUE_LINK.search(line):
                errors.append(f"{path.relative_to(ROOT)}:{i + 1}: bare TODO; write TODO(name) or link an issue")
    return errors


def count_tests():
    out = subprocess.run(
        ["cargo", "nextest", "list", "--message-format", "json"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    per_crate = {}
    for suite in json.loads(out)["rust-suites"].values():
        crate = suite["package-name"]
        per_crate[crate] = per_crate.get(crate, 0) + len(suite["testcases"])
    for crate, n in sorted(per_crate.items()):
        print(f"tests  {crate}: {n}")
    return []


CHECKS = {"deps": check_deps, "lines": check_lines, "guards": check_guards, "sleep": check_sleep, "todo": check_todo, "docs": check_docs,
          "count": count_tests}


def main(args):
    failed = False
    for name in args or [k for k in CHECKS if k != "count"]:
        errors = CHECKS[name]()
        for e in errors:
            print(f"{name}: {e}")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
