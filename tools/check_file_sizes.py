#!/usr/bin/env python3
"""Fail on any file at or over the size limit: in the working tree, the index, or commits being pushed.

The limit is PLAN.md's (Repo, toolchain, CI and deploy), held in MAX_FILE_BYTES. For an LFS
pointer the real size is read from the pointer.

Usage:
    python3 tools/check_file_sizes.py                   tracked + addable working-tree files (CI)
    python3 tools/check_file_sizes.py --staged          what is staged for the next commit
    python3 tools/check_file_sizes.py --range REV...    every file added or changed in the commits
                                                        rev-list selects, e.g. origin/main..HEAD

Exit code 0 = all under the limit, 1 = at least one at or over it, 2 = bad usage,
3 = git failed or an object is missing (nothing was checked).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "cad"))
from gitlfs import (
    MAX_FILE_BYTES,
    REPO_ROOT,
    blob_sizes,
    changed_blobs,
    git,
    real_blob_size,
    real_size,
)


def working_tree(root: Path = REPO_ROOT) -> list[tuple[int, str]]:
    out = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", root=root)
    found = []
    for rel in sorted({p for p in out.decode("utf-8").split("\0") if p}):
        path = root / rel
        if path.is_file():
            found.append((real_size(path), rel))
    return found


def staged(root: Path = REPO_ROOT) -> list[tuple[int, str]]:
    changed = set(
        git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT", root=root)
        .decode()
        .split("\0")
    )
    changed.discard("")
    entries = []
    for line in git("ls-files", "-s", "-z", root=root).decode().split("\0"):
        if not line:
            continue
        meta, rel = line.split("\t", 1)  # "<mode> <blob> <stage>\t<path>"
        if rel in changed:
            entries.append((meta.split()[1], rel))
    sizes = blob_sizes([b for b, _ in entries], root=root)
    return [(real_blob_size(sizes.get(b)), rel) for b, rel in entries]


def pushed(rev_args: list[str], root: Path = REPO_ROOT) -> list[tuple[int, str]]:
    found = changed_blobs(rev_args, root=root)
    sizes = blob_sizes([b for b, _ in found], root=root)
    return [(real_blob_size(sizes.get(b)), rel) for b, rel in found]


def report(files: list[tuple[int, str]], where: str) -> int:
    too_big = sorted({(s, r) for s, r in files if s >= MAX_FILE_BYTES}, reverse=True)
    for size, rel in too_big:
        print(f"TOO BIG {size / 1e6:8.1f} MB  {rel}")
    if too_big:
        print(
            f"\n{len(too_big)} {where} file(s) at or over {MAX_FILE_BYTES / 1e6:g} MB. Keep them out of git: "
            "_wip/, _sim/ or _archive/ (gitignored), or simplify/split the file."
        )
        return 1
    print(f"OK: no {where} file is {MAX_FILE_BYTES / 1e6:g} MB or larger")
    return 0


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except subprocess.CalledProcessError as err:
        cmd = " ".join(str(a) for a in err.cmd)
        print(f"git failed ({err.returncode}): {cmd}\n{err.stderr.decode(errors='replace')}", file=sys.stderr)
        return 3
    except LookupError as err:
        print(err, file=sys.stderr)
        return 3


def run(argv: list[str]) -> int:
    if not argv:
        return report(working_tree(), "tracked or addable")
    if argv == ["--staged"]:
        return report(staged(), "staged")
    if len(argv) >= 2 and argv[0] == "--range":
        return report(pushed(argv[1:]), f"pushed ({' '.join(argv[1:])})")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
