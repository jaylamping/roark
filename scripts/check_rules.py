#!/usr/bin/env python3
"""Repo rules that the compiler and clippy can't check (rust.md section 13, testing.md "Automated checks", docs.md 5).

  deps    crate dependencies only point the way architecture.md section 3 allows
  lines   no source file passes 800 lines
  guards  every test has a `Guards:` line directly above it
  sleep   no sleeping in test code
  todo    no bare TODO; write TODO(name) or link an issue
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


CHECKS = {"deps": check_deps, "lines": check_lines, "guards": check_guards, "sleep": check_sleep, "todo": check_todo,
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
