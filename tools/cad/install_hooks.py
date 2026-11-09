#!/usr/bin/env python3
"""Install the repo's git hooks (pre-commit, pre-push) into this clone.

    python3 tools/cad/install_hooks.py            install or update
    python3 tools/cad/install_hooks.py --check    exit 1 if they are missing or out of date

pre-commit: tools/cad/hooks/pre_commit.py (staged sizes; layout + writer lock when CAD is staged),
            then <hook>.local if present.
pre-push:   tools/cad/hooks/pre_push.py (pushed sizes, LFS budget), then <hook>.local if present,
            then `git lfs pre-push` (fails if Git LFS is missing), so nothing is uploaded for a
            push a check refuses.
Run it from the main checkout: it refuses in a linked worktree, since the hooks it writes are
shared by every worktree of the clone. Does not set core.hooksPath; a worktree whose
checkout has no tools/cad/hooks skips the CAD checks with a warning (pre-push still runs Git LFS).
Git LFS's own stock pre-push hook (only the git-lfs presence check and `git lfs pre-push "$@"`)
is replaced, since ours runs it; a copy is kept as pre-push.lfs-orig. Any other existing hook,
including one that runs git lfs among other things, is kept as <hook>.local and still runs.
Run it once per clone (the CAD workstation, any laptop that commits CAD); re-run after `git lfs install`.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitlfs import REPO_ROOT, git

MARK = "# repo-cad-hooks v3"

# Worktrees share one hooks folder, so a worktree whose checkout has no tools/cad/hooks (a branch from
# before them) skips the CAD checks with a warning instead of failing every commit and push.
PRELUDE = """TOP=$(git rev-parse --show-toplevel)
HOOKS=$(git rev-parse --git-path hooks)
"""

FIND_PY = """  for c in python3 python py; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(sys.version_info < (3, 9))" >/dev/null 2>&1; then
      PY=$c; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "cad hooks: Python 3.9+ not found; install it (or bypass once with --no-verify)" >&2
    exit 1
  fi
"""

SKIP = """  echo "cad hooks: no tools/cad/hooks in $TOP (branch from before them); CAD checks skipped" >&2
"""

HOOKS = {
    "pre-commit": f"""#!/bin/sh
{MARK}
{PRELUDE}if [ -f "$TOP/tools/cad/hooks/pre_commit.py" ]; then
{FIND_PY}  "$PY" "$TOP/tools/cad/hooks/pre_commit.py" || exit 1
else
{SKIP}fi
if [ -x "$HOOKS/pre-commit.local" ]; then
  exec "$HOOKS/pre-commit.local" "$@"
fi
exit 0
""",
    "pre-push": f"""#!/bin/sh
{MARK}
{PRELUDE}input=$(cat)
if [ -f "$TOP/tools/cad/hooks/pre_push.py" ]; then
{FIND_PY}  printf '%s\\n' "$input" | "$PY" "$TOP/tools/cad/hooks/pre_push.py" "$@" || exit 1
  NEED_LFS=1
else
{SKIP}  grep -qs 'filter=lfs' "$TOP/.gitattributes" && NEED_LFS=1
fi
if [ -x "$HOOKS/pre-push.local" ]; then
  printf '%s\\n' "$input" | "$HOOKS/pre-push.local" "$@" || exit 1
fi
# Last, once every check has passed: Git LFS must upload the objects, or the remote gets
# pointers with no content.
if command -v git-lfs >/dev/null 2>&1; then
  printf '%s\\n' "$input" | git lfs pre-push "$@" || exit 1
elif [ -n "$NEED_LFS" ]; then
  echo "cad hooks: git-lfs not found; install Git LFS before pushing (https://git-lfs.com)" >&2
  exit 1
fi
exit 0
""",
}


def is_stock_lfs_hook(name: str, text: str) -> bool:
    """Git LFS's own pre-push hook: nothing but the git-lfs presence check and `git lfs pre-push "$@"`."""
    if name != "pre-push":
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    rest = [ln for ln in lines if not ln.startswith("command -v git-lfs")]
    return rest == ['git lfs pre-push "$@"']


def hooks_dir(root: Path = REPO_ROOT) -> Path:
    p = Path(git("rev-parse", "--git-path", "hooks", root=root).decode().strip())
    return p if p.is_absolute() else root / p


def linked_worktree(root: Path = REPO_ROOT) -> bool:
    """True in a `git worktree add` checkout: its git dir is not the clone's common dir."""
    paths = []
    for flag in ("--git-dir", "--git-common-dir"):
        p = Path(git("rev-parse", flag, root=root).decode().strip())
        paths.append((p if p.is_absolute() else root / p).resolve())
    return paths[0] != paths[1]


def install(root: Path = REPO_ROOT) -> list[str]:
    if linked_worktree(root):
        raise SystemExit(
            "cad hooks: this is a linked worktree, and the hooks are shared by every worktree of the clone; "
            "run install_hooks.py from the main checkout"
        )
    d = hooks_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    done = []
    for name, body in HOOKS.items():
        path = d / name
        if path.exists():
            old = path.read_text(encoding="utf-8", errors="replace")
            if "-cad-hooks v" in old:
                pass  # an older version of ours: overwrite
            elif is_stock_lfs_hook(name, old):
                # Git LFS's own hook: ours already runs `git lfs pre-push`; keep a copy that does not run
                orig = d / f"{name}.lfs-orig"
                if orig.exists() and orig.read_text(encoding="utf-8", errors="replace") != old:
                    raise SystemExit(f"{orig} already exists and differs; merge them by hand")
                path.replace(orig)
                done.append(
                    f"replaced Git LFS's {name} hook (ours runs git lfs; copy in {name}.lfs-orig)"
                )
            else:
                local = d / f"{name}.local"
                if local.exists():
                    raise SystemExit(
                        f"{path} is not ours and {local} already exists; merge them by hand"
                    )
                path.rename(local)
                done.append(f"kept the existing {name} hook as {local.name}")
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        done.append(f"installed {name}")
    return done


def is_current(root: Path = REPO_ROOT) -> bool:
    d = hooks_dir(root)
    for name, body in HOOKS.items():
        path = d / name
        if (
            not path.exists()
            or path.read_text(encoding="utf-8", errors="replace") != body
        ):
            return False
        if os.name != "nt" and not os.access(path, os.X_OK):
            return False
    return True


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        ok = is_current()
        print(
            "hooks installed and current"
            if ok
            else "hooks missing or out of date: python tools/cad/install_hooks.py"
        )
        return 0 if ok else 1
    if argv:
        print(__doc__)
        return 2
    for line in install():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
