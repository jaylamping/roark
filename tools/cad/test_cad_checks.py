"""Tests for the CAD size and layout checks (pytest; run by scripts/check.sh). Rules: conventions/cad.md."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_cad_layout as ccl
import check_file_sizes as cfs
import gitlfs

LAYOUT = ccl.load_json(ccl.LAYOUT_PATH)
CONVENTIONS = ccl.load_json(ccl.CONVENTIONS_PATH)
PIN = "Pinned commit: " + "a" * 40 + "\n"


def pointer(size: int, oid: str) -> str:
    return (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {size}\n"
    )


def build(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def check_tree(root: Path, files: dict[str, str]) -> ccl.Report:
    build(root, files)
    return ccl.Checker(root, LAYOUT, CONVENTIONS, exports={"exports": []}).run()


def git(root: Path, *args: str) -> str:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway repo with the real manifests and one LFS pointer committed and pushed (pointers are written by hand; no LFS needed)."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "commit.gpgsign", "false")
    manifests = {
        f"cad/manifests/{p.name}": p.read_text(encoding="utf-8")
        for p in ccl.LAYOUT_PATH.parent.glob("*.json")
    }
    # the real rules, but no export records: the real records name files this throwaway repo doesn't have
    manifests["cad/manifests/exports.json"] = json.dumps({"version": 1, "exports": []})
    build(
        tmp_path,
        {
            "README.md": "x",
            "cad/shoulder/shoulder_a.SLDPRT": pointer(5_000_000, "1" * 64),
            **manifests,
        },
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


def test_staged_and_pushed_sizes_read_the_lfs_pointer(repo: Path) -> None:
    """Guards: number - the file size limit applies to LFS files by their real size (PLAN.md, conventions/cad.md rule 5)."""
    build(repo, {"cad/shoulder/shoulder_big.SLDPRT": pointer(120_000_000, "2" * 64)})
    git(repo, "add", "-A")
    assert cfs.staged(repo) == [(120_000_000, "cad/shoulder/shoulder_big.SLDPRT")]
    git(repo, "commit", "-qm", "big")
    pushed = cfs.pushed(["origin/main..HEAD"], repo)
    assert pushed == [(120_000_000, "cad/shoulder/shoulder_big.SLDPRT")]
    assert cfs.report(pushed, "pushed") == 1


def test_size_limit_boundary() -> None:
    """Guards: number - at the limit fails, one byte under passes (PLAN.md file size limit)."""
    limit = gitlfs.MAX_FILE_BYTES
    assert cfs.report([(limit - 1, "a")], "t") == 0
    assert cfs.report([(limit, "a")], "t") == 1


def test_a_type_change_to_a_large_file_is_checked(repo: Path) -> None:
    """Guards: bug - --staged and --range skipped a symlink replaced by a large file (status T) (PR 14 review, 2026-11-09)."""
    (repo / "cad" / "shoulder" / "link.SLDPRT").symlink_to("shoulder_a.SLDPRT")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "link")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    (repo / "cad" / "shoulder" / "link.SLDPRT").unlink()
    build(repo, {"cad/shoulder/link.SLDPRT": pointer(150_000_000, "3" * 64)})
    git(repo, "add", "-A")
    assert cfs.staged(repo) == [(150_000_000, "cad/shoulder/link.SLDPRT")]
    git(repo, "commit", "-qm", "type change")
    assert cfs.pushed(["origin/main..HEAD"], repo) == [(150_000_000, "cad/shoulder/link.SLDPRT")]


def test_content_added_in_a_merge_commit_is_checked(repo: Path) -> None:
    """Guards: bug - a file added while resolving a merge skipped the pushed-size check (CAD process review, 2026-11-08)."""
    git(repo, "checkout", "-q", "-b", "side")
    build(repo, {"side.txt": "s"})
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "side")
    git(repo, "checkout", "-q", "main")
    build(repo, {"main.txt": "m"})
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "main")
    git(repo, "merge", "-q", "--no-commit", "side")
    build(repo, {"cad/shoulder/shoulder_m.SLDPRT": pointer(130_000_000, "4" * 64)})
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "merge with new content")
    assert (130_000_000, "cad/shoulder/shoulder_m.SLDPRT") in cfs.pushed(
        ["HEAD", "--not", "--remotes=origin"], repo
    )


def test_layout_errors(tmp_path: Path) -> None:
    """Guards: number - the folder rules in cad/manifests/cad-layout.json (file types per folder, sim output, loose files, folder case)."""
    report = check_tree(
        tmp_path,
        {
            "codex/a.SLDPRT": "",
            "exports/shoulder/shoulder_a.SLDPRT": "",
            "exports/loose.stl": "",
            "shoulder/shoulder_a.step": "",
            "arm/arm_link.SLDPRT": "",
            "arm/notes.md": "",
            "prints/shoulder/shoulder_a.stl": "",
            "shoulder/fea.CWR": "",
            "stray.step": "",
            "Torso/torso_plate.SLDPRT": "",
        },
    )
    assert sorted(report.errors) == sorted(
        [
            "codex: unknown top-level folder (not a region, function or scratch folder)",
            "codex: forbidden folder name 'codex'",
            "exports/shoulder/shoulder_a.SLDPRT: native SolidWorks file in exports/ (move to a region folder or _wip/)",
            "exports/loose.stl: exports/ must be split by region: exports/<region>/...",
            "shoulder/shoulder_a.step: '.step' files do not belong in shoulder/ (native parts and assemblies)",
            "arm/arm_link.SLDPRT: '.sldprt' files do not belong in arm/ (whole-arm assemblies only)",
            "arm/notes.md: '.md' files do not belong in arm/ (whole-arm assemblies only)",
            "prints/shoulder/shoulder_a.stl: '.stl' files do not belong in prints/",
            "shoulder/fea.CWR: simulation results belong in _sim/<region>/",
            "stray.step: loose file at CAD root (only README.md and robot.SLDASM belong here)",
            "Torso: folder names are lower case (git and Linux see a different folder)",
        ]
    )


def test_clean_tree_has_no_findings(tmp_path: Path) -> None:
    """Guards: number - the layout and naming rules accept the documented example tree (conventions/cad.md)."""
    report = check_tree(
        tmp_path,
        {
            "README.md": "",
            "robot.SLDASM": "",
            "shoulder/shoulder_pitch_bracket_left.SLDPRT": "",
            "shoulder/.checkpoints/x.tmp": "",
            "upper-arm/upper_arm_link_left.SLDPRT": "",
            "arm/arm_left_asm.SLDASM": "",
            "fixtures/fixtures_test.SLDPRT": "",
            "vendor/robstride/vendor_robstride_rs03.STEP": "",
            "vendor/acme/vendor_acme_bracket.x_b": "",
            "prints/shoulder/shoulder_pitch_bracket_left.3mf": "",
            "reviews/shoulder/20261109_pitch-gate/brief.md": PIN,
            "_wip/layout/scratch_v2.SLDPRT": "",
            "_sim/shoulder/study.CWR": "",
        },
    )
    assert report.errors == []
    assert report.warnings == [
        "shoulder/.checkpoints: SolidWorks checkpoints (gitignored); move to _archive/checkpoints/ when they pile up"
    ]


def test_version_copies_are_errors_and_look_alikes_are_not(tmp_path: Path) -> None:
    """Guards: number - versionSuffixPattern in cad-layout.json: one current file per part, history in git."""
    bad = [
        "upper-arm/upper_arm_link_left_revC.SLDPRT",
        "upper-arm/upper_arm_link_v2_left.SLDPRT",
        "arm/arm_left_revb_asm.SLDASM",
        "arm/arm_left_final_asm.SLDASM",
        "exports/shoulder/shoulder_bracket_final.step",
        "prints/shoulder/shoulder_bracket (2).3mf",
        "shoulder/Copy of shoulder_bracket.SLDPRT",
        "shoulder/Backup (2) of shoulder_bracket.SLDPRT",
    ]
    fine = [
        "fixtures/fixtures_test_stand_rs03.SLDPRT",
        "fixtures/fixtures_test.SLDPRT",
        "upper-arm/upper_arm_reverse_stop.SLDPRT",
    ]
    report = check_tree(tmp_path, dict.fromkeys(bad + fine, ""))
    flagged = sorted(e.split(":")[0] for e in report.errors if "version-suffixed" in e)
    assert flagged == sorted(bad)


def test_names(tmp_path: Path) -> None:
    """Guards: number - cad-conventions.json naming: lower-case stem, region prefix, assembly suffix, vendor shape, no robot name."""
    report = check_tree(
        tmp_path,
        {
            "upper-arm/shoulder_link.SLDPRT": "",
            "torso/marengo_torso_asm.SLDASM": "",
            "torso/torso_marengo_asm.SLDASM": "",
            "shoulder/Shoulder_Bracket.SLDPRT": "",
            "shoulder/shoulder-bracket.SLDPRT": "",
            "arm/arm_left.SLDASM": "",
            "vendor/robstride/rs03.STEP": "",
            "vendor/robstride/vendor_robstride_rs03.SLDPRT": "",
        },
    )
    assert report.errors == []
    assert sorted(report.warnings) == sorted(
        [
            "upper-arm/shoulder_link.SLDPRT: name should start with its region folder: upper_arm_...",
            "torso/marengo_torso_asm.SLDASM: no robot name in file names (tenet 7)",
            "torso/marengo_torso_asm.SLDASM: name should start with its region folder: torso_...",
            "torso/torso_marengo_asm.SLDASM: no robot name in file names (tenet 7)",
            "shoulder/Shoulder_Bracket.SLDPRT: part name should be shoulder_<part>.SLDPRT (lower case)",
            "shoulder/shoulder-bracket.SLDPRT: part name should be shoulder_<part>.SLDPRT (lower case)",
            "arm/arm_left.SLDASM: assembly name should be arm[_<name>]_asm.SLDASM (lower case)",
            "vendor/robstride/rs03.STEP: vendor file name should be vendor_<maker>_<model>.<ext> (lower case)",
        ]
    )


def test_review_packet_limits(tmp_path: Path) -> None:
    """Guards: number - review limits in cad-layout.json (2 MB warn, 10 MB error, 15 MB and 10 images per packet, pinned commit)."""
    pkt = "reviews/shoulder/20261109_gate"
    pinned = "reviews/shoulder/20261110_pinned"
    files = {
        f"{pkt}/brief.md": "no pin",
        f"{pkt}/big.png": "",
        f"{pkt}/huge.csv": "",
        "reviews/shoulder/loose.md": PIN,
        f"{pinned}/brief.md": "Pinned commit: " + "a" * 41 + "\n",
        **{f"{pinned}/r{i}.png": "" for i in range(11)},
    }
    build(tmp_path, files)
    sized = [(f"{pkt}/big.png", 3_000_000), (f"{pkt}/huge.csv", 11_000_000)]
    sized += [(f"{pinned}/r{i}.png", 1_500_000) for i in range(11)]
    for rel, size in sized:
        with (tmp_path / rel).open("wb") as fh:
            fh.truncate(size)
    report = ccl.Checker(tmp_path, LAYOUT, CONVENTIONS, exports={"exports": []}).run()
    assert sorted(report.errors) == [
        "reviews/shoulder/20261109_gate/huge.csv: 11.0 MB review file; keep bulky data in _archive/reviews/",
        "reviews/shoulder/loose.md: reviews/ files go in reviews/<region>/<YYYYMMDD>_<topic>/",
    ]
    assert sorted(report.warnings) == [
        "reviews/shoulder/20261109_gate/big.png: 3.0 MB review file; keep renders under 2 MB (about 1600 px)",
        "reviews/shoulder/20261109_gate: no 'Pinned commit: <full 40-character SHA>' line in the packet's markdown",
        "reviews/shoulder/20261110_pinned: 11 images; commit the key renders (10 or fewer)",
        "reviews/shoulder/20261110_pinned: no 'Pinned commit: <full 40-character SHA>' line in the packet's markdown",
        "reviews/shoulder/20261110_pinned: review packet is 16.5 MB; keep a packet under 15 MB",
    ]


def test_repo_mode_rejects_cad_outside_cad_plain_blobs_and_tracked_scratch(
    repo: Path,
) -> None:
    """Guards: number - CAD lives only in cad/, through LFS; scratch, lock and Explorer files are never tracked; no case twins (conventions/cad.md)."""
    build(
        repo,
        {
            "docs/part.step": "",
            "cad/shoulder/shoulder_raw.SLDPRT": "not a pointer",
            "cad/shoulder/shoulder_fake.SLDPRT": pointer(1, "not-a-sha").replace("size 1", "size -1"),
            "cad/_wip/x/notes.md": "",
            "cad/.cad-writer.lock": "{}",
            "cad/shoulder/Thumbs.db": "",
            "cad/shoulder/Shoulder_A.SLDPRT": pointer(1, "6" * 64),
        },
    )
    git(repo, "add", "-A", "-f")
    report = ccl.check_repo(repo)
    assert sorted(report.errors) == sorted(
        [
            "docs/part.step: CAD file outside cad/ (CAD files live only in cad/; docs link there)",
            "cad/shoulder/shoulder_raw.SLDPRT: CAD file committed as a plain git blob, not through Git LFS (git lfs install, then re-add it)",
            "cad/shoulder/shoulder_fake.SLDPRT: CAD file committed as a plain git blob, not through Git LFS (git lfs install, then re-add it)",
            "cad/_wip/x/notes.md: tracked file in a scratch folder (_wip/_sim/_archive/.checkpoints are local only); git rm --cached it",
            "cad/.cad-writer.lock: lock, download-marker or Explorer file must not be tracked; git rm --cached it",
            "cad/shoulder/Thumbs.db: lock, download-marker or Explorer file must not be tracked; git rm --cached it",
            "cad/shoulder/shoulder_a.SLDPRT: differs from cad/shoulder/Shoulder_A.SLDPRT only in case; keep one",
        ]
    )


def test_repo_mode_reads_its_rules_from_the_index(repo: Path) -> None:
    """Guards: bug - --repo checked staged files against unstaged rules (PR 15 review, 2026-11-09)."""
    build(repo, {"cad/scratchpad/x.md": ""})
    git(repo, "add", "-A")
    layout = json.loads((repo / "cad/manifests/cad-layout.json").read_text())
    layout["scratchFolders"].append("scratchpad")
    (repo / "cad/manifests/cad-layout.json").write_text(json.dumps(layout))
    assert ccl.check_repo(repo).errors == [
        "cad/scratchpad: unknown top-level folder (not a region, function or scratch folder)"
    ]


EXPORT, SOURCE = "exports/shoulder/shoulder_a.step", "shoulder/shoulder_a.SLDPRT"


def record(**changes: str) -> dict:
    entry = {
        "export": EXPORT,
        "source": SOURCE,
        "config": "",
        "settings": "",
        "sourceSha256": "1" * 64,
        "exportSha256": "5" * 64,
        "recorded": "",
    }
    entry.update(changes)
    return entry


def stage_exports(repo: Path, manifest: str | None, files: dict[str, str]) -> list[str]:
    build(repo, {f"cad/{k}": v for k, v in files.items()})
    if manifest is None:
        git(repo, "rm", "-q", "--cached", "cad/manifests/exports.json")
    else:
        build(repo, {"cad/manifests/exports.json": manifest})
    git(repo, "add", "-A") if manifest is not None else None
    report = ccl.check_repo(repo)
    return sorted(report.errors) + ["WARN " + w for w in sorted(report.warnings)]


@pytest.mark.parametrize(
    ("entries", "files", "expected"),
    [
        ([record()], {EXPORT: pointer(1000, "5" * 64)}, []),
        (
            [record(sourceSha256="9" * 64)],
            {EXPORT: pointer(1000, "5" * 64)},
            [f"WARN cad/{EXPORT}: stale: {SOURCE} changed after this export; re-export and record it"],
        ),
        (
            [record(exportSha256="7" * 64)],
            {EXPORT: pointer(1000, "5" * 64)},
            [f"cad/{EXPORT}: changed since it was recorded; run tools/cad/record_export.py again"],
        ),
        ([record()], {}, [f"cad/{EXPORT}: listed in manifests/exports.json but missing"]),
        (
            [record(source="shoulder/gone.SLDPRT")],
            {EXPORT: pointer(1000, "5" * 64)},
            [f"cad/{EXPORT}: source shoulder/gone.SLDPRT is gone; re-export from the current part or delete the export"],
        ),
        (
            [],
            {EXPORT: pointer(1000, "5" * 64)},
            [f"WARN cad/{EXPORT}: no source recorded; run tools/cad/record_export.py EXPORT SOURCE"],
        ),
        ([{"export": EXPORT}], {}, ["cad/manifests/exports.json: entry 0 is missing source, sourceSha256, exportSha256"]),
    ],
)
def test_export_records(repo: Path, entries: list, files: dict, expected: list) -> None:
    """Guards: number - every export outcome in conventions/cad.md section 5: match, stale, changed, missing, source gone, unrecorded, bad entry."""
    assert stage_exports(repo, json.dumps({"exports": entries}), files) == expected


def test_a_missing_or_broken_export_manifest_fails(repo: Path) -> None:
    """Guards: bug - a missing or empty exports.json switched the export check off silently (PR 15 review, 2026-11-09)."""
    assert stage_exports(repo, "", {}) == [
        "cad/manifests/exports.json: not valid JSON: Expecting value: line 1 column 1 (char 0)"
    ]
    assert stage_exports(repo, None, {}) == [
        "cad/manifests/exports.json: missing; the export records can't be checked"
    ]


def test_exports_are_checked_against_the_staged_bytes(repo: Path) -> None:
    """Guards: bug - --repo once hashed the working tree, so a commit could hold an export that didn't match its record (CAD process review, 2026-11-08)."""
    build(
        repo,
        {
            f"cad/{EXPORT}": pointer(1000, "5" * 64),
            "cad/manifests/exports.json": json.dumps({"exports": [record()]}),
        },
    )
    git(repo, "add", "-A")
    (repo / "cad" / EXPORT).write_text("edited in the tree, not staged")
    assert ccl.check_repo(repo).errors == []
    git(repo, "add", "-A")
    assert ccl.check_repo(repo).errors == [
        f"cad/{EXPORT}: CAD file committed as a plain git blob, not through Git LFS (git lfs install, then re-add it)",
        f"cad/{EXPORT}: changed since it was recorded; run tools/cad/record_export.py again",
    ]


def test_lfs_pointer_parsing() -> None:
    """Guards: protocol - the Git LFS pointer format, https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md."""
    assert gitlfs.parse_pointer(pointer(42, "c" * 64).encode()) == ("c" * 64, 42)
    assert gitlfs.parse_pointer(b"not a pointer") is None
    assert gitlfs.parse_pointer(pointer(42, "not-a-sha").encode()) is None
    assert gitlfs.parse_pointer(pointer(42, "c" * 64).replace("42", "-1").encode()) is None
