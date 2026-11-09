#!/usr/bin/env python3
"""Promotion check (Windows, SolidWorks): every file an assembly or part references resolves
to a file under cad/ that git will hold (not a scratch folder, not outside cad/).

    python tools/cad/check_sw_refs.py cad\\arm\\arm_left_asm.SLDASM [more files...]
    python tools/cad/check_sw_refs.py --all      every SLDPRT/SLDASM/SLDDRW in cad/ outside the scratch folders

Run it after staging a promoted part or assembly (git add), before committing: every
reference must be committed or staged. Reads references with
ISldWorks.GetDocumentDependencies2 (no document is opened) in this session's own hidden
SolidWorks instance (tools/solidworks/sw_instance.py, see tools/solidworks/RULES.md).
Exit code 0 = every file was read and every reference resolves inside tracked cad/; 1 = a bad
reference, or a file that can't be checked (not staged, changed since staging, an LFS pointer, or an
assembly or drawing SolidWorks reports no references for); 2 = usage.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Set as AbstractSet
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitlfs import REPO_ROOT, git, parse_pointer

CAD_ROOT = REPO_ROOT / "cad"
SCRATCH = {"_wip", "_sim", "_archive", ".checkpoints"}
NATIVE = {".sldprt", ".sldasm", ".slddrw"}


def is_lfs_pointer(p: Path) -> bool:
    """An unpulled LFS file: SolidWorks can't read references out of a pointer."""
    try:
        return p.stat().st_size <= 1024 and parse_pointer(p.read_bytes()) is not None
    except OSError:
        return False


def classify(
    ref: str,
    cad_root: Path = CAD_ROOT,
    ignored: AbstractSet[str] | None = None,
    indexed: AbstractSet[str] | None = None,
    unstaged: AbstractSet[str] | None = None,
) -> str | None:
    """None if the reference is fine, else why not. The sets hold lower-case cad-relative paths."""
    p = Path(ref)
    if not p.is_file():
        return "missing (SolidWorks would search for it or show it suppressed)"
    try:
        rel = p.resolve().relative_to(cad_root.resolve())
    except ValueError:
        return "outside cad/ (copy it in with Pack and Go)"
    key = rel.as_posix().lower()
    if SCRATCH & {part.lower() for part in rel.parts[:-1]}:
        return "in a scratch folder (_wip/_sim/_archive are not committed)"
    if ignored and key in ignored:
        return (
            "matches .gitignore, so it is only in git if force-added; move or rename it"
        )
    if indexed is not None and key not in indexed:
        return "not in git yet (neither committed nor staged); git add it with the promotion"
    if unstaged and key in unstaged:
        return "working copy differs from the staged copy; stage it or restore it"
    if is_lfs_pointer(p):
        return "an LFS pointer, not the file, so its own references can't be read; git lfs pull it"
    return None


def target_problem(
    f: Path, indexed: set[str], unstaged: set[str], cad_root: Path = CAD_ROOT
) -> str | None:
    """None if the file can be scanned, else why not. Checked before SolidWorks starts."""
    key = cad_key(f, cad_root)
    if key is None:
        return "outside cad/ (copy it in with Pack and Go)"
    if SCRATCH & set(Path(key).parts[:-1]):
        return "in a scratch folder; promote it first (conventions/cad.md section 2, rule 2)"
    if key not in indexed:
        return "not staged or committed; git add it first"
    if key in unstaged:
        return "working copy differs from the staged copy; stage it (git add) or restore it, then re-run"
    if is_lfs_pointer(f):
        return "an LFS pointer, not the file; git lfs pull it, then re-run"
    return None


def git_ignored(paths: list[Path], root: Path = REPO_ROOT) -> set[str]:
    rels = []
    for p in paths:
        try:
            rels.append(p.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            pass
    if not rels:
        return set()
    try:
        out = git(
            "check-ignore",
            "--no-index",
            "--stdin",
            "-z",
            root=root,
            input_bytes=("\0".join(rels) + "\0").encode(),
        )
    except subprocess.CalledProcessError as err:
        if (
            err.returncode == 1
        ):  # nothing ignored; 128 is a git failure and must not pass as "nothing"
            return set()
        raise
    return {
        p[len("cad/") :].lower()
        for p in out.decode().split("\0")
        if p.startswith("cad/")
    }


def unstaged_paths(root: Path = REPO_ROOT) -> set[str]:
    """Lower-case cad-relative paths whose working copy differs from the staged copy.

    The scan reads working-tree files, so it only proves what gets committed when those match.
    """
    out = git("diff", "--name-only", "-z", "--", "cad", root=root).decode()
    return {p[len("cad/") :].lower() for p in out.split("\0") if p.startswith("cad/")}


def cad_key(path: Path, cad_root: Path = CAD_ROOT) -> str | None:
    try:
        return path.resolve().relative_to(cad_root.resolve()).as_posix().lower()
    except ValueError:
        return None


def index_snapshot(root: Path = REPO_ROOT) -> tuple[bytes, bytes]:
    """The index entries and the unstaged diff under cad/: if either changes, the scan proves nothing."""
    return (
        git("ls-files", "-s", "-z", "--", "cad", root=root),
        git("diff", "--binary", "--", "cad", root=root),
    )


def index_paths(root: Path = REPO_ROOT) -> set[str]:
    """Lower-case cad-relative paths in the index (committed or staged)."""
    out = git("ls-files", "-z", "--", "cad", root=root).decode()
    return {p[len("cad/") :].lower() for p in out.split("\0") if p.startswith("cad/")}


def dependencies(sw, path: Path) -> list[str] | None:
    """Stored reference paths, or None when SolidWorks returns nothing.

    None is normal for a part with no references, but an assembly or drawing always has some, so
    scan() refuses None for those (a file SolidWorks can't read also gives None).
    """
    # (file, traverse all levels, search for files, add read-only info) -> [name, path, name, path, ...]
    # search=False: report the stored paths, so a reference SolidWorks would only find by searching shows up as missing.
    deps = sw.GetDocumentDependencies2(str(path), True, False, False)
    if deps is None or deps is False:
        return None
    if isinstance(deps, str) or len(deps) % 2:
        raise RuntimeError(
            f"{path}: unexpected dependency list from SolidWorks: {deps!r}"
        )
    return [deps[i + 1] for i in range(0, len(deps), 2)]


def targets(argv: list[str], root: Path = REPO_ROOT) -> list[Path]:
    """--all: every staged or committed native file in cad/ outside the scratch folders."""
    if argv == ["--all"]:
        out = git("ls-files", "-z", "--", "cad", root=root).decode()
        found = []
        for rel in sorted(p for p in out.split("\0") if p):
            parts = {x.lower() for x in Path(rel).parts}
            if Path(rel).suffix.lower() in NATIVE and not (SCRATCH & parts):
                found.append(root / rel)
        return found
    return [Path(a).resolve() for a in argv]


def shown(f: Path, root: Path = REPO_ROOT) -> str:
    try:
        return f.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(f)


def scan(
    sw, files: list[Path], indexed: set[str], unstaged: set[str], root: Path = REPO_ROOT
) -> int:
    """Check every reference of each file; prints one line per bad reference, then ok or BAD per file."""
    bad = 0
    for f in files:
        refs = dependencies(sw, f)
        if refs is None:
            if f.suffix.lower() in {".sldasm", ".slddrw"}:
                bad += 1
                print(
                    f"BAD  {shown(f, root)}: SolidWorks returned no references for an assembly or drawing; "
                    "open it in SolidWorks to see why"
                )
                continue
            refs = []
        ignored = git_ignored([Path(r) for r in refs], root)
        file_bad = 0
        for ref in refs:
            why = classify(ref, root / "cad", ignored, indexed, unstaged)
            if why:
                file_bad += 1
                print(f"BAD  {shown(f, root)} -> {PureWindowsPath(ref)}: {why}")
        verdict = "BAD " if file_bad else "ok  "
        print(f"{verdict} {shown(f, root)}: {len(refs)} reference(s) checked")
        bad += file_bad
    return bad


def main(argv: list[str]) -> int:
    if not argv or argv in (["-h"], ["--help"]):
        print(__doc__)
        return 2
    indexed, unstaged = index_paths(), unstaged_paths()
    files = targets(argv)
    bad = 0
    ready = []
    for f in files:
        why = target_problem(f, indexed, unstaged)
        if why:
            bad += 1
            print(f"BAD  {shown(f)}: {why}")
        else:
            ready.append(f)
    if ready:  # start SolidWorks only when there is something to scan
        sys.path.insert(0, str(REPO_ROOT / "tools" / "solidworks"))
        from sw_instance import launch  # Windows only (pywin32)

        with launch() as inst:
            # The launch takes a while: take the snapshot the scan relies on now, and make sure it held.
            before = index_snapshot()
            indexed, unstaged = index_paths(), unstaged_paths()
            for f in list(ready):
                why = target_problem(f, indexed, unstaged)
                if why:
                    bad += 1
                    print(f"BAD  {shown(f)}: {why}")
                    ready.remove(f)
            bad += scan(inst.sw, ready, indexed, unstaged)
            if index_snapshot() != before:
                bad += 1
                print(
                    "BAD  the index or a working copy under cad/ changed during the scan; re-run"
                )
    print(f"\n{bad} problem(s) in {len(files)} file(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
