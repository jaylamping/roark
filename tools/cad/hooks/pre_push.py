#!/usr/bin/env python3
"""pre-push: no pushed file over the size limit, and the LFS budget holds.

Called by the shell hook from tools/cad/install_hooks.py with git's pre-push arguments
(remote name, URL) and stdin (one line per ref). The shell hook then runs any local hook,
then git lfs pre-push. A git failure blocks the push with git's own message.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))
import check_file_sizes
import lfs_budget
from gitlfs import REPO_ROOT, pre_push_rev_args


def known_locally(rev_args: list[str], root: Path = REPO_ROOT) -> list[str]:
    """Drop ^<remote tip> for a tip this clone never fetched (a force push over unfetched work):
    --remotes= still bounds the range, and rev-list would fail on the unknown object."""
    kept = []
    for arg in rev_args:
        if arg.startswith("^"):
            probe = subprocess.run(
                ["git", "-C", str(root), "cat-file", "-e", f"{arg[1:]}^{{commit}}"],
                capture_output=True,
                check=False,
            )
            if probe.returncode != 0:
                continue
        kept.append(arg)
    return kept


def main(argv: list[str], root: Path = REPO_ROOT, stdin: str | None = None) -> int:
    remote = argv[0] if argv else "origin"
    text = sys.stdin.read() if stdin is None else stdin
    rev_args = known_locally(pre_push_rev_args(text, remote), root)
    if not rev_args:
        return 0
    try:
        # every ref in this push is checked together, so the budget sees the whole upload
        sizes = check_file_sizes.pushed(rev_args, root=root)
        failed = check_file_sizes.report(sizes, "pushed") != 0
        ok, msgs = lfs_budget.check_push(rev_args, root=root, remote=remote)
    except subprocess.CalledProcessError as err:
        cmd = " ".join(str(a) for a in err.cmd)
        print(f"pre-push: git failed ({err.returncode}): {cmd}\n{err.stderr.decode(errors='replace')}")
        return 1
    except (OSError, KeyError, ValueError) as err:
        print(f"pre-push: can't read the LFS budget or a size: {err!r}")
        return 1
    print("\n".join(msgs))
    return 1 if failed or not ok else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
