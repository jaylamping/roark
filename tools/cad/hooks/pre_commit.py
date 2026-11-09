#!/usr/bin/env python3
"""pre-commit: no staged file over the size limit; commits touching CAD respect the layout and the writer lock.

Installed by tools/cad/install_hooks.py. Skips the CAD checks when nothing staged is CAD.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from gitlfs import REPO_ROOT, git


def cad_extensions() -> set[str]:
    layout = json.loads((REPO_ROOT / "cad" / "manifests" / "cad-layout.json").read_text(encoding="utf-8"))
    return {e.lower() for e in layout["cadExtensions"]}


def touches_cad(paths: list[str]) -> bool:
    ext = cad_extensions()
    return any(p.startswith("cad/") or PurePosixPath(p).suffix.lower() in ext for p in paths)


def run(*args: str) -> int:
    return subprocess.run(
        [sys.executable, *args], cwd=REPO_ROOT, check=False
    ).returncode


def main() -> int:
    staged = [
        p
        for p in git("diff", "--cached", "--name-only", "-z").decode().split("\0")
        if p
    ]
    failed = run(str(REPO_ROOT / "tools" / "check_file_sizes.py"), "--staged") != 0
    if touches_cad(staged):
        sys.path.insert(0, str(HERE.parent))
        import cad_lock

        # refresh both proves CAD_WRITER holds the lock and keeps it alive, in one step under the
        # lock's mutex, so a takeover can't slip in between a check and the commit
        try:
            ok, msg = cad_lock.refresh(os.environ.get("CAD_WRITER"))
        except cad_lock.Busy as err:
            ok, msg = False, str(err)
        if not ok:
            print(f"pre-commit: {msg}")
            failed = True
        # --repo checks the index (what is being committed), not untracked files in the tree
        failed |= run(str(HERE.parent / "check_cad_layout.py"), "--repo") != 0
    if failed:
        print("pre-commit: fix the above (see conventions/cad.md).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
