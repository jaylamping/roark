#!/usr/bin/env python3
"""Check the CAD tree against the layout rule in cad/manifests/cad-layout.json.

Usage:
    python3 tools/cad/check_cad_layout.py [CAD_ROOT] [--strict] [--quiet]
    python3 tools/cad/check_cad_layout.py --repo [--strict] [--quiet]

CAD_ROOT defaults to the repo's cad/ folder; its own manifests/exports.json is read.
--repo checks what git tracks instead of a folder: CAD files outside cad/, tracked files in
scratch folders, and the tracked part of cad/ (works in a clone without LFS content). The
rules and the export records are read from the index too, so it checks a commit against
that commit's own rules.
Exit code 0 = clean, 1 = layout errors (or warnings with --strict), 2 = bad usage.
Stdlib only (Python 3.9 or newer), so it runs on Windows, macOS and Linux without setup.

Errors (break the rule):
  - unknown top-level folder or loose top-level file; a folder name not in lower case
  - two tracked paths that differ only in case
  - forbidden folder names anywhere outside _archive (codex, task, task-2, _import*, old, ...)
  - native SolidWorks files outside a region folder, vendor/, or the scratch folders
  - a file type that does not belong in its folder (region folders hold SLDPRT/SLDASM/md;
    arm/ holds whole-arm assemblies only; SLDPRT in exports/; STEP in prints/; ...)
  - simulation results (.CWR, .STE) outside _sim/ or _archive/
  - exports/, prints/, reviews/, drawings/ not split by region; reviews/ not split into
    reviews/<region>/<YYYYMMDD>_<topic>/
  - date-stamped folders outside reviews/, _wip/, _sim/, _archive/
  - version-suffixed copies (_v2, _revC, _final, _copy, "Copy of", ...) in region, exports,
    prints and drawings folders: keep one current file, history is in git
  - any file of 100 MB or more outside the scratch folders (real size, LFS pointers included)
  - a review file over 10 MB
  - an export whose bytes no longer match cad/manifests/exports.json, or whose source is gone;
    a missing, unreadable or malformed exports.json
  - --repo: a CAD file tracked outside cad/, or any tracked file under _wip/_sim/_archive/.checkpoints,
    or a lock, download-marker or Windows Explorer file
Warnings (should be fixed, do not fail without --strict):
  - native and vendor model names that do not match cad/manifests/cad-conventions.json
    (lower case, region prefix, no robot name)
  - .checkpoints folders (SolidWorks recreates them beside open parts; gitignored)
  - stale exports (source changed since the export was recorded) and exports with no record
  - review files over 2 MB, packets over 15 MB or 10 images, packets with no pinned commit
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitlfs import (
    MAX_FILE_BYTES,
    REPO_ROOT,
    blob_sizes,
    content_sha256,
    git,
    parse_pointer,
    real_blob_size,
    real_size,
)

LAYOUT_PATH = REPO_ROOT / "cad" / "manifests" / "cad-layout.json"
CONVENTIONS_PATH = REPO_ROOT / "cad" / "manifests" / "cad-conventions.json"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".svg"}
EXPORT_KEYS = ("export", "source", "sourceSha256", "exportSha256")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, rel: PurePosixPath | Path | str, msg: str) -> None:
        r = rel if isinstance(rel, str) else PurePosixPath(*Path(rel).parts).as_posix()
        self.errors.append(f"{r}: {msg}")

    def warn(self, rel: PurePosixPath | Path | str, msg: str) -> None:
        r = rel if isinstance(rel, str) else PurePosixPath(*Path(rel).parts).as_posix()
        self.warnings.append(f"{r}: {msg}")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


class Checker:
    """Checks a list of (path relative to the CAD root, real size). Folders come from the paths."""

    def __init__(
        self,
        root: Path,
        layout: dict,
        conventions: dict,
        exports: dict | None = None,
        source: FileSource | None = None,
    ) -> None:
        self.root = root
        self.source = source or DiskSource(root)
        self.layout = layout
        low = lambda xs: {x.lower() for x in xs}
        self.regions = low(layout["regionFolders"])
        self.region_ext = low(layout["regionExtensions"])
        self.region_ext_override = {
            k.lower(): low(v)
            for k, v in layout.get("regionExtensionOverrides", {}).items()
        }
        self.functions = {k.lower(): v for k, v in layout["functionFolders"].items()}
        self.scratch = low(layout["scratchFolders"])
        self.root_files = low(layout["rootFiles"])
        self.native_ext = low(layout["nativeExtensions"])
        self.sim_ext = low(layout["simExtensions"])
        self.forbidden = [
            re.compile(p, re.IGNORECASE) for p in layout["forbiddenFolderPatterns"]
        ]
        self.version_suffix = re.compile(layout["versionSuffixPattern"], re.IGNORECASE)
        vs_folders = low(layout["versionSuffixFolders"])
        self.version_suffix_tops = (
            self.regions if "regions" in vs_folders else set()
        ) | (vs_folders - {"regions"})
        self.warn_dirs = [
            re.compile(p, re.IGNORECASE) for p in layout.get("warnFolderPatterns", [])
        ]
        self.dated = re.compile(layout["datedFolderPattern"])
        self.dated_ok = low(layout["datedFoldersAllowedUnder"])
        self.review_dir = re.compile(layout["reviewFolderPattern"])
        self.review_limits = layout["reviewLimits"]
        self.ignore = [
            re.compile(p, re.IGNORECASE) for p in layout["ignoreFilePatterns"]
        ]
        # Name patterns match the stem with the extension lower-cased: SolidWorks writes
        # extensions in upper case, but the stem must be lower case (conventions/cad.md section 4).
        self.part_re = re.compile(conventions["partFilenamePattern"])
        self.asm_re = re.compile(conventions["assemblyFilenamePattern"])
        self.vendor_re = re.compile(conventions["vendorFilenamePattern"])
        self.vendor_name_ext = low(conventions["vendorNameExtensions"])
        self.forbidden_tokens = low(conventions["forbiddenNameTokens"])
        self.exports = exports
        self.report = Report()
        self.packets: dict[str, list[tuple[PurePosixPath, int]]] = defaultdict(list)

    # -- entry points --------------------------------------------------------
    def run(self) -> Report:
        """Walk the folder on disk."""
        files = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                files.append(
                    (PurePosixPath(*path.relative_to(self.root).parts), real_size(path))
                )
        return self.check(files)

    def check(self, files: list[tuple[PurePosixPath, int]]) -> Report:
        dirs = set()
        for rel, _ in files:
            for i in range(1, len(rel.parts)):
                dirs.add(PurePosixPath(*rel.parts[:i]))
        for d in sorted(dirs):
            self.check_top_dir(d)
            self.check_dir_name(d)
        for rel, size in sorted(files):
            in_checkpoints = any(p.lower() == ".checkpoints" for p in rel.parts[:-1])
            if not self.ignored(rel.name) and not in_checkpoints:
                self.check_file(rel, size)
        self.check_packets()
        if self.exports is None:
            self.report.error(
                "manifests/exports.json", "missing; the export records can't be checked"
            )
        else:
            self.check_exports({rel.as_posix() for rel, _ in files})
        return self.report

    # -- helpers -------------------------------------------------------------
    def ignored(self, name: str) -> bool:
        return any(p.search(name) for p in self.ignore)

    def check_top_dir(self, rel: PurePosixPath) -> None:
        if len(rel.parts) != 1:
            return
        name = rel.parts[0].lower()
        known = name in self.regions or name in self.functions or name in self.scratch
        if known or any(p.search(name) for p in self.warn_dirs):
            return
        self.report.error(
            rel, "unknown top-level folder (not a region, function or scratch folder)"
        )

    def check_dir_name(self, rel: PurePosixPath) -> None:
        """Folder-name rules (not applied inside _archive)."""
        parts = rel.parts
        if parts[0].lower() == "_archive":
            return
        name = parts[-1]
        if name != name.lower() and parts[0].lower() not in self.scratch:
            self.report.error(
                rel,
                "folder names are lower case (git and Linux see a different folder)",
            )
        if any(pat.search(name) for pat in self.forbidden):
            self.report.error(rel, f"forbidden folder name '{name}'")
        if any(pat.search(name) for pat in self.warn_dirs):
            self.report.warn(
                rel,
                "SolidWorks checkpoints (gitignored); move to _archive/checkpoints/ when they pile up",
            )
        if self.dated.search(name) and parts[0].lower() not in self.dated_ok:
            self.report.error(
                rel, "date-stamped folder outside reviews/, _wip/, _sim/, _archive/"
            )

    def check_native_name(self, rel: PurePosixPath, top: str) -> None:
        ext = rel.suffix.lower()
        name = rel.stem + ext
        tokens = set(rel.stem.lower().split("_"))
        if tokens & self.forbidden_tokens:
            self.report.warn(rel, "no robot name in file names (tenet 7)")
        if top == "vendor":
            if not self.vendor_re.search(name):
                self.report.warn(
                    rel,
                    "vendor file name should be vendor_<maker>_<model>.<ext> (lower case)",
                )
            return
        region = top.replace("-", "_")
        if ext == ".sldprt" and not self.part_re.search(name):
            self.report.warn(
                rel, f"part name should be {region}_<part>.SLDPRT (lower case)"
            )
        elif ext == ".sldasm" and not self.asm_re.search(name):
            self.report.warn(
                rel,
                f"assembly name should be {region}[_<name>]_asm.SLDASM (lower case)",
            )
        elif not name.startswith(region + "_"):
            self.report.warn(
                rel, f"name should start with its region folder: {region}_..."
            )

    # -- files ---------------------------------------------------------------
    def check_file(self, rel: PurePosixPath, size: int) -> None:
        parts = rel.parts
        ext = rel.suffix.lower()
        top = parts[0].lower()
        if top not in self.scratch and size >= MAX_FILE_BYTES:
            self.report.error(
                rel,
                f"{size / 1e6:.1f} MB: at or over the size limit ({MAX_FILE_BYTES / 1e6:g} MB); move to _wip/ or _archive/",
            )
        if len(parts) == 1:
            if rel.name.lower() not in self.root_files:
                self.report.error(
                    rel,
                    "loose file at CAD root (only README.md and robot.SLDASM belong here)",
                )
            return
        if top in self.scratch:
            if ext in self.sim_ext and top == "_wip":
                self.report.error(rel, "simulation results belong in _sim/")
            return
        if ext in self.sim_ext:
            self.report.error(rel, "simulation results belong in _sim/<region>/")
            return
        if top in self.version_suffix_tops and self.version_suffix.search(rel.name):
            self.report.error(
                rel,
                "version-suffixed copy; keep one current file and overwrite it, history is in git",
            )
        if top in self.regions:
            allowed = self.region_ext_override.get(top, self.region_ext)
            if ext not in allowed:
                what = (
                    "whole-arm assemblies only"
                    if top == "arm"
                    else "native parts and assemblies"
                )
                self.report.error(
                    rel, f"'{ext or '(none)'}' files do not belong in {top}/ ({what})"
                )
            elif ext in self.native_ext:
                self.check_native_name(rel, top)
            return
        if top in self.functions:
            self.check_function_file(rel, top, ext, size)

    def check_function_file(
        self, rel: PurePosixPath, top: str, ext: str, size: int
    ) -> None:
        rule = self.functions[top]
        parts = rel.parts
        if ext in self.native_ext and top != "vendor":
            self.report.error(
                rel,
                f"native SolidWorks file in {top}/ (move to a region folder or _wip/)",
            )
            return
        if top == "vendor" and ext in self.vendor_name_ext:
            self.check_native_name(rel, top)
        allowed = rule.get("extensions")
        if allowed is not None and ext not in {e.lower() for e in allowed}:
            self.report.error(rel, f"'{ext or '(none)'}' files do not belong in {top}/")
        if rule.get("regionSubfolders"):
            if len(parts) < 3:
                self.report.error(
                    rel, f"{top}/ must be split by region: {top}/<region>/..."
                )
                return
            if parts[1].lower() not in self.regions:
                self.report.error(rel, f"'{parts[1]}' is not a region folder name")
        if rule.get("datedSubfolders"):
            if len(parts) < 4:
                self.report.error(
                    rel, f"{top}/ files go in {top}/<region>/<YYYYMMDD>_<topic>/"
                )
                return
            if not self.review_dir.search(parts[2]):
                self.report.error(
                    rel,
                    f"'{parts[2]}' should be named <YYYYMMDD>_<topic> (lower case, hyphens)",
                )
            if top == "reviews":
                self.check_review_file(rel, size)

    def check_review_file(self, rel: PurePosixPath, size: int) -> None:
        lim = self.review_limits
        if size > lim["fileMaxBytes"]:
            self.report.error(
                rel,
                f"{size / 1e6:.1f} MB review file; keep bulky data in _archive/reviews/",
            )
        elif size > lim["fileWarnBytes"]:
            self.report.warn(
                rel,
                f"{size / 1e6:.1f} MB review file; keep renders under 2 MB (about 1600 px)",
            )
        self.packets["/".join(rel.parts[:3])].append((rel, size))

    def check_packets(self) -> None:
        lim = self.review_limits
        pinned = re.compile(lim["pinnedCommitPattern"])
        for packet, files in sorted(self.packets.items()):
            total = sum(s for _, s in files)
            images = sum(1 for r, _ in files if r.suffix.lower() in IMAGE_EXT)
            if total > lim["packetWarnBytes"]:
                self.report.warn(
                    packet,
                    f"review packet is {total / 1e6:.1f} MB; keep a packet under 15 MB",
                )
            if images > lim["packetImagesWarn"]:
                self.report.warn(
                    packet, f"{images} images; commit the key renders (10 or fewer)"
                )
            if not any(
                self._has_pin(r, pinned) for r, _ in files if r.suffix.lower() == ".md"
            ):
                self.report.warn(
                    packet,
                    "no 'Pinned commit: <full 40-character SHA>' line in the packet's markdown",
                )

    def _has_pin(self, rel: PurePosixPath, pinned: re.Pattern) -> bool:
        data = self.source.read(rel.as_posix())
        return bool(data and pinned.search(data.decode("utf-8", errors="replace")))

    # -- exports manifest ----------------------------------------------------
    def check_exports(self, present: set[str]) -> None:
        recorded = set()
        entries = (
            self.exports.get("exports") if isinstance(self.exports, dict) else None
        )
        if not isinstance(entries, list):
            self.report.error("manifests/exports.json", "no 'exports' list")
            return
        for i, entry in enumerate(entries):
            missing = [
                k for k in EXPORT_KEYS if not isinstance(entry, dict) or k not in entry
            ]
            if missing:
                self.report.error(
                    "manifests/exports.json",
                    f"entry {i} is missing {', '.join(missing)}",
                )
                continue
            exp, src = entry["export"], entry["source"]
            recorded.add(exp)
            exp_sha, src_sha = self.source.sha256(exp), self.source.sha256(src)
            if exp_sha is None:
                self.report.error(exp, "listed in manifests/exports.json but missing")
                continue
            if exp_sha != entry["exportSha256"]:
                self.report.error(
                    exp,
                    "changed since it was recorded; run tools/cad/record_export.py again",
                )
            if src_sha is None:
                self.report.error(
                    exp,
                    f"source {src} is gone; re-export from the current part or delete the export",
                )
            elif src_sha != entry["sourceSha256"]:
                self.report.warn(
                    exp,
                    f"stale: {src} changed after this export; re-export and record it",
                )
        for rel in sorted(present):
            p = PurePosixPath(rel)
            unrecorded = (
                p.parts[0] == "exports"
                and p.suffix.lower() in {".step", ".stp", ".stl"}
                and rel not in recorded
            )
            if unrecorded:
                self.report.warn(
                    rel,
                    "no source recorded; run tools/cad/record_export.py EXPORT SOURCE",
                )


# -- where file contents come from -------------------------------------------
class DiskSource:
    """Files on disk under the CAD root."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self, rel: str) -> bytes | None:
        """None only when the file doesn't exist; any other read failure raises."""
        path = self.root / rel
        return path.read_bytes() if path.is_file() else None

    def sha256(self, rel: str) -> str | None:
        path = self.root / rel
        return content_sha256(path) if path.is_file() else None


class IndexSource:
    """The staged (index) copy of files under cad/, i.e. exactly what a commit holds."""

    def __init__(self, blobs: dict[str, str], root: Path = REPO_ROOT) -> None:
        self.blobs = dict(blobs)  # cad-relative path, exact case -> blob id
        self.root = root

    def read(self, rel: str) -> bytes | None:
        blob = self.blobs.get(rel)
        return git("cat-file", "blob", blob, root=self.root) if blob else None

    def sha256(self, rel: str) -> str | None:
        data = self.read(rel)
        if data is None:
            return None
        ptr = parse_pointer(data) if len(data) <= 1024 else None
        return ptr[0] if ptr else hashlib.sha256(data).hexdigest()


FileSource = Union[DiskSource, IndexSource]  # noqa: UP007 (evaluated at runtime; X | Y needs 3.10)


# -- repo mode ---------------------------------------------------------------
def tracked_files(root: Path = REPO_ROOT) -> list[tuple[str, str]]:
    """(blob id, path) for everything in the index."""
    out = []
    for line in git("ls-files", "-s", "-z", root=root).decode().split("\0"):
        if line:
            meta, rel = line.split("\t", 1)
            out.append((meta.split()[1], rel))
    return out


def check_repo(root: Path = REPO_ROOT) -> Report:
    """Check the index against the rules in the index (a commit is checked by its own rules)."""
    entries = tracked_files(root)
    rules = IndexSource({rel: blob for blob, rel in entries}, root)
    layout = read_manifest(rules, "cad/manifests/cad-layout.json")
    conventions = read_manifest(rules, "cad/manifests/cad-conventions.json")
    if layout is None or conventions is None:
        raise ValueError(
            "cad/manifests/cad-layout.json or cad-conventions.json is not in the index"
        )
    sizes = blob_sizes([b for b, _ in entries], root=root)
    cad_files = []
    report = Report()
    cad_ext = {e.lower() for e in layout["cadExtensions"]}
    scratch = {s.lower() for s in layout["scratchFolders"]} | {".checkpoints"}
    never_tracked = re.compile(
        r"(^~\$|Zone\.Identifier$|^\.cad-writer\.lock$|^desktop\.ini$|^Thumbs\.db$)",
        re.IGNORECASE,
    )
    cad_blobs = {}
    seen_case: dict[str, str] = {}
    for blob, rel in entries:
        other = seen_case.setdefault(rel.lower(), rel)
        if other != rel:
            report.error(rel, f"differs from {other} only in case; keep one")
        p = PurePosixPath(rel)
        if never_tracked.search(p.name):
            report.error(
                rel,
                "lock, download-marker or Explorer file must not be tracked; git rm --cached it",
            )
            continue
        if scratch & {part.lower() for part in p.parts[:-1]}:
            report.error(
                rel,
                "tracked file in a scratch folder (_wip/_sim/_archive/.checkpoints are local only); git rm --cached it",
            )
            continue
        if p.parts[0] == "cad":
            cad_blobs[PurePosixPath(*p.parts[1:]).as_posix()] = blob
            entry = sizes.get(blob)
            if p.suffix.lower() in cad_ext and entry is not None and entry[1] is None:
                report.error(
                    rel,
                    "CAD file committed as a plain git blob, not through Git LFS (git lfs install, then re-add it)",
                )
            cad_files.append(
                (PurePosixPath(*p.parts[1:]), real_blob_size(sizes.get(blob)))
            )
        elif p.suffix.lower() in cad_ext:
            report.error(
                rel,
                "CAD file outside cad/ (CAD files live only in cad/; docs link there)",
            )
    source = IndexSource(cad_blobs, root)
    try:
        exports = read_manifest(source, "manifests/exports.json")
    except ValueError as err:
        report.error("cad/manifests/exports.json", str(err))
        exports = {"exports": []}
    checker = Checker(
        root / "cad",
        layout,
        conventions,
        exports=exports,
        source=source,
    )
    sub = checker.check(cad_files)
    report.errors += [f"cad/{e}" for e in sub.errors]
    report.warnings += [f"cad/{w}" for w in sub.warnings]
    return report


def read_manifest(source: FileSource, rel: str) -> dict | None:
    """A JSON manifest, None if absent; ValueError if it can't be read as a JSON object."""
    data = source.read(rel)
    if data is None:
        return None
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"not valid JSON: {err}") from err
    if not isinstance(value, dict):
        raise ValueError("not a JSON object")  # noqa: TRY004 (callers report every manifest problem as one kind)
    return value


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    unknown = flags - {"--strict", "--quiet", "--repo"}
    if unknown or len(args) > 1 or ("--repo" in flags and args):
        print(__doc__)
        return 2
    if "--repo" in flags:
        try:
            report, where = check_repo(), "tracked files"
        except ValueError as err:
            print(f"ERROR {err}")
            return 1
        except KeyError as err:
            print(f"ERROR cad/manifests: the staged rules have no {err} key")
            return 1
    else:
        layout, conventions = load_json(LAYOUT_PATH), load_json(CONVENTIONS_PATH)
        root = Path(args[0]) if args else REPO_ROOT / "cad"
        if not root.is_dir():
            print(f"CAD root not found: {root}")
            return 2
        report = Report()
        try:
            exports = read_manifest(DiskSource(root), "manifests/exports.json")
        except ValueError as err:
            report.error("manifests/exports.json", str(err))
            exports = {"exports": []}
        checker = Checker(root, layout, conventions, exports=exports)
        checker.report = report
        report = checker.run()
        where = str(root)
    quiet = "--quiet" in flags
    for line in report.errors:
        print(f"ERROR {line}")
    if not quiet:
        for line in report.warnings:
            print(f"WARN  {line}")
    print(
        f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s) in {where}"
    )
    failed = bool(report.errors) or ("--strict" in flags and bool(report.warnings))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
