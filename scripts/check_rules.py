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

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# architecture.md section 3. Each workspace crate lists the workspace crates it may depend on. A crate missing from this
# table fails the check: add it here and to the map in the same PR.
ALLOWED_DEPS = {
    "can": {"robstride", "telemetry"},
    "can-bench": set(),
    "robot-cli": {"robstride", "skeleton"},
    "robstride": set(),
    "runtime": {"can", "robstride", "safety", "skeleton", "telemetry"},
    "safety": {"can", "robstride", "skeleton"},
    "skeleton": {"robstride"},
    "sim-drive": {"robstride", "skeleton"},
    "sim-suite": {"can", "robstride", "runtime", "safety", "sim-drive", "skeleton", "telemetry"},
    "telemetry": set(),
}

# rust.md section 11. Each workspace package's README.md is its crate doc, by kind: a library shows its API in a Rust
# example that runs as a doc test; a binary with no library, or the sim suite, shows its commands. A package missing here fails the check.
DOC_KIND = {
    "can": "library",
    "can-bench": "binary",  # no library; the README shows its commands
    "robot-cli": "library",  # its library is the stop as plain values; the README also covers the binary
    "robstride": "library",
    "runtime": "library",  # its library is what the sim suite drives; the README also covers the binary
    "safety": "library",
    "skeleton": "library",
    "sim-drive": "library",  # its library is what the sim suite drives; the README also covers the binary
    "sim-suite": "tests",
    "telemetry": "library",
}
DOC_INCLUDE = '#![doc = include_str!("../README.md")]'
DOC_SECTIONS = ["## What it does", "## Must never", "## Talks to", "## Using it"]
ARCHITECTURE_URL = "https://github.com/jaylamping/roark/blob/main/conventions/architecture.md"
# A relative link resolves on GitHub but not in rustdoc (target/doc/<crate>/), and rustdoc doesn't warn. Inline links,
# reference definitions and HTML attributes all count.
RELATIVE_LINKS = [
    re.compile(r"\]\((?!https?://|#)"),
    re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(?!https?://|#)\S"),
    re.compile(r"\b(?:href|src)\s*=\s*[\"'](?!https?://|#)"),
]
# `[`Item`]` is a rustdoc link that GitHub shows as literal brackets; name items in plain backticks.
ITEM_LINK = re.compile(r"\[`[^`]+`\](?![(\[:])")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^`]*)$")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
# rustdoc skips or doesn't run these, so an example marked with one proves nothing.
NOT_RUN = {"ignore", "no_run", "compile_fail", "should_panic"}


def markdown(lines):
    """Split a README into prose lines (outside fences) and fences (line, info string), as CommonMark does: a fence
    closes only on the same character, at least as long, with no info string."""
    prose, fences, open_fence, errors = [], [], None, []
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if open_fence is None:
            if m:
                open_fence = (m.group(1), i)
                fences.append((i, m.group(2).strip()))
            else:
                prose.append((i, line))
        elif m and m.group(1)[0] == open_fence[0][0] and len(m.group(1)) >= len(open_fence[0]) and not m.group(2).strip():
            open_fence = None
    if open_fence is not None:
        errors.append((open_fence[1], "fence never closed"))
    return prose, fences, errors


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
        if kind not in ("library", "binary", "tests"):
            errors.append(f"{name}: DOC_KIND must say library, binary or tests; give it a README (rust.md section 11)")
            continue
        manifest = Path(pkg["manifest_path"])
        readme = manifest.parent / "README.md"
        where = readme.relative_to(ROOT)
        if not readme.is_file():
            errors.append(f"{where}: missing; it is the crate doc (rust.md section 11)")
            continue
        targets = {t["kind"][0]: Path(t["src_path"]) for t in pkg["targets"]}
        root = targets.get("lib") or targets.get("bin")
        if root is None:
            errors.append(f"{name}: no lib or bin target to carry the crate doc")
        else:
            first = next((l for l in root.read_text().splitlines() if l.strip()), "")
            if first.strip() != DOC_INCLUDE:
                errors.append(f"{root.relative_to(ROOT)}: must open with {DOC_INCLUDE}")
        prose, fences, problems = markdown(readme.read_text().splitlines())
        errors += [f"{where}:{i + 1}: {p}" for i, p in problems]
        prose_lines = [line for _, line in prose]
        for section in DOC_SECTIONS:
            if section not in prose_lines:
                errors.append(f"{where}: no '{section}' section")
        if not any(ARCHITECTURE_URL in CODE_SPAN.sub("", line) for line in prose_lines):
            errors.append(f"{where}: link the map, {ARCHITECTURE_URL}")
        for i, line in prose:
            if ITEM_LINK.search(line):
                errors.append(f"{where}:{i + 1}: rustdoc item link; GitHub shows it as brackets, use plain backticks")
            text = CODE_SPAN.sub("", line)
            if any(r.search(text) for r in RELATIVE_LINKS):
                errors.append(f"{where}:{i + 1}: relative link; use a full GitHub URL (it breaks in rustdoc)")
        runnable = 0
        for i, info in fences:
            words = {w.strip() for w in re.split(r"[,\s]+", info) if w.strip()}
            if not words:
                errors.append(f"{where}:{i + 1}: unlabelled fence; rustdoc runs it as Rust, so name its language")
            elif "rust" in words and words & NOT_RUN:
                errors.append(f"{where}:{i + 1}: {', '.join(sorted(words & NOT_RUN))} example; examples run (rust.md section 11)")
            elif words == {"rust"}:
                runnable += 1
        if kind == "library" and runnable == 0:
            errors.append(f"{where}: a library README needs a ```rust example that runs")
        needs_shell = kind == "tests" or "bin" in targets
        if needs_shell and not any(info == "bash" for _, info in fences):
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
    return (
        "tests" in path.parts
        or path.name == "tests.rs"
        or any("#[cfg(test)]" in line for line in lines[:i])
    )


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


PY_GUARDS = re.compile(r"^\s*Guards: (bug|safety|protocol|number) - \S")


def check_py_guards():
    """pytest tests carry the Guards: line as the first line of their docstring."""
    errors = []
    for path in sorted(p for p in ROOT.rglob("test_*.py") if "target" not in p.parts):
        for node in ast.walk(ast.parse(path.read_text(), str(path))):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                doc = ast.get_docstring(node) or ""
                if not PY_GUARDS.match(doc.splitlines()[0] if doc else ""):
                    errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: test without a `Guards: <kind> - ...` docstring")
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


CHECKS = {"deps": check_deps, "lines": check_lines, "guards": check_guards, "py_guards": check_py_guards, "sleep": check_sleep, "todo": check_todo, "docs": check_docs,
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
