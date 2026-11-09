"""Tests for the CAD size and layout checks (pytest; run by scripts/check.sh). Rules: conventions/cad.md."""

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
    return ccl.Checker(root, LAYOUT, CONVENTIONS).run()


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
    """A throwaway repo with one LFS pointer committed and pushed (pointers are written by hand; no LFS needed)."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "commit.gpgsign", "false")
    build(
        tmp_path,
        {
            "README.md": "x",
            "cad/shoulder/shoulder_a.SLDPRT": pointer(5_000_000, "1" * 64),
        },
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


def test_staged_and_pushed_sizes_read_the_lfs_pointer(repo: Path) -> None:
    """Guards: number - the 100 MB file limit applies to LFS files by their real size (conventions/cad.md)."""
    build(repo, {"cad/shoulder/shoulder_big.SLDPRT": pointer(120_000_000, "2" * 64)})
    git(repo, "add", "-A")
    assert cfs.staged(repo) == [(120_000_000, "cad/shoulder/shoulder_big.SLDPRT")]
    git(repo, "commit", "-qm", "big")
    pushed = cfs.pushed(["origin/main..HEAD"], repo)
    assert pushed == [(120_000_000, "cad/shoulder/shoulder_big.SLDPRT")]
    assert cfs.report(pushed, "pushed") == 1


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
    """Guards: number - the folder rules in cad/manifests/cad-layout.json (file types per folder, sim output, loose files)."""
    report = check_tree(
        tmp_path,
        {
            "codex/a.SLDPRT": "",
            "exports/shoulder/shoulder_a.SLDPRT": "",
            "exports/loose.stl": "",
            "shoulder/shoulder_a.step": "",
            "arm/arm_link.SLDPRT": "",
            "prints/shoulder/shoulder_a.stl": "",
            "shoulder/fea.CWR": "",
            "stray.step": "",
        },
    )
    joined = "\n".join(report.errors)
    for needle in [
        "codex: forbidden",
        "exports/shoulder/shoulder_a.SLDPRT: native SolidWorks file in exports/",
        "loose.stl: exports/ must be split by region",
        "'.step' files do not belong in shoulder/",
        "'.sldprt' files do not belong in arm/ (whole-arm",
        "'.stl' files do not belong in prints/",
        "fea.CWR: simulation results",
        "stray.step: loose file",
    ]:
        assert needle in joined


def test_clean_tree_has_no_findings(tmp_path: Path) -> None:
    """Guards: number - the layout and naming rules accept the documented example tree (conventions/cad.md)."""
    report = check_tree(
        tmp_path,
        {
            "README.md": "",
            "robot.SLDASM": "",
            "shoulder/shoulder_pitch_bracket_left.SLDPRT": "",
            "upper-arm/upper_arm_link_left.SLDPRT": "",
            "arm/arm_left_asm.SLDASM": "",
            "vendor/robstride/vendor_robstride_rs03.STEP": "",
            "exports/shoulder/shoulder_pitch_bracket_left.step": "",
            "prints/shoulder/shoulder_pitch_bracket_left.3mf": "",
            "reviews/shoulder/20261109_pitch-gate/brief.md": PIN,
            "_wip/layout/scratch_v2.SLDPRT": "",
            "_sim/shoulder/study.CWR": "",
        },
    )
    assert report.errors == []
    assert report.warnings == []


def test_version_copies_are_errors_and_look_alikes_are_not(tmp_path: Path) -> None:
    """Guards: number - versionSuffixPattern in cad-layout.json: one current file per part, history in git."""
    bad = [
        "upper-arm/upper_arm_link_left_revC.SLDPRT",
        "upper-arm/upper_arm_link_v2_left.SLDPRT",
        "exports/shoulder/shoulder_bracket_final.step",
        "prints/shoulder/shoulder_bracket (2).3mf",
        "shoulder/Copy of shoulder_bracket.SLDPRT",
    ]
    fine = [
        "fixtures/fixtures_test_stand_rs03.SLDPRT",
        "upper-arm/upper_arm_reverse_stop.SLDPRT",
    ]
    report = check_tree(tmp_path, dict.fromkeys(bad + fine, ""))
    flagged = sorted(e.split(":")[0] for e in report.errors if "version-suffixed" in e)
    assert flagged == sorted(bad)


def test_names_start_with_their_region(tmp_path: Path) -> None:
    """Guards: number - cad-conventions.json naming: region prefix, no robot name."""
    report = check_tree(
        tmp_path,
        {"upper-arm/shoulder_link.SLDPRT": "", "torso/marengo_torso_asm.SLDASM": ""},
    )
    assert report.errors == []
    assert len(report.warnings) == 2
    assert all("upper_arm_" in w or "torso_" in w for w in report.warnings)


def test_review_packet_limits(tmp_path: Path) -> None:
    """Guards: number - review limits in cad-layout.json (2 MB warn, 10 MB error, pinned commit)."""
    pkt = "reviews/shoulder/20261109_gate"
    build(
        tmp_path,
        {
            f"{pkt}/brief.md": "no pin",
            f"{pkt}/big.png": "",
            f"{pkt}/huge.csv": "",
            "reviews/shoulder/loose.md": PIN,
        },
    )
    for rel, size in [(f"{pkt}/big.png", 3_000_000), (f"{pkt}/huge.csv", 11_000_000)]:
        with (tmp_path / rel).open("wb") as fh:
            fh.truncate(size)
    report = ccl.Checker(tmp_path, LAYOUT, CONVENTIONS).run()
    errors, warns = "\n".join(report.errors), "\n".join(report.warnings)
    assert "huge.csv: 11.0 MB review file" in errors
    assert (
        "loose.md: reviews/ files go in reviews/<region>/<YYYYMMDD>_<topic>/" in errors
    )
    assert "big.png: 3.0 MB" in warns
    assert "Pinned commit" in warns


def test_repo_mode_rejects_cad_outside_cad_plain_blobs_and_tracked_scratch(
    repo: Path,
) -> None:
    """Guards: number - CAD lives only in cad/, through LFS; scratch and lock files are never tracked (conventions/cad.md)."""
    build(
        repo,
        {
            "docs/part.step": "",
            "cad/shoulder/shoulder_raw.SLDPRT": "not a pointer",
            "cad/_wip/x/notes.md": "",
            "cad/.cad-writer.lock": "{}",
        },
    )
    git(repo, "add", "-A", "-f")
    joined = "\n".join(ccl.check_repo(LAYOUT, CONVENTIONS, repo).errors)
    assert "docs/part.step: CAD file outside cad/" in joined
    assert "shoulder_raw.SLDPRT: CAD file committed as a plain git blob" in joined
    assert "cad/_wip/x/notes.md: tracked file in a scratch folder" in joined
    assert (
        "cad/.cad-writer.lock: lock or download-marker file must not be tracked"
        in joined
    )


def test_exports_are_checked_against_the_staged_bytes(repo: Path) -> None:
    """Guards: bug - --repo once hashed the working tree, so a commit could hold an export that didn't match its record (CAD process review, 2026-11-08)."""
    exp, src = "exports/shoulder/shoulder_a.step", "shoulder/shoulder_a.SLDPRT"
    entry = {
        "export": exp,
        "source": src,
        "config": "",
        "settings": "",
        "sourceSha256": "1" * 64,
        "exportSha256": "5" * 64,
        "recorded": "",
    }
    build(
        repo,
        {
            f"cad/{exp}": pointer(1000, "5" * 64),
            "cad/manifests/exports.json": json.dumps({"exports": [entry]}),
        },
    )
    git(repo, "add", "-A")
    (repo / "cad" / exp).write_text("edited in the tree, not staged")
    assert not any(
        "changed since it was recorded" in e
        for e in ccl.check_repo(LAYOUT, CONVENTIONS, repo).errors
    )
    git(repo, "add", "-A")
    assert any(
        "changed since it was recorded" in e
        for e in ccl.check_repo(LAYOUT, CONVENTIONS, repo).errors
    )


def test_lfs_pointer_parsing() -> None:
    """Guards: protocol - the Git LFS pointer format, https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md."""
    assert gitlfs.parse_pointer(pointer(42, "c" * 64).encode()) == ("c" * 64, 42)
    assert gitlfs.parse_pointer(b"not a pointer") is None
