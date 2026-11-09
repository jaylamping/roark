"""Tests for export records and the SolidWorks reference check (pytest; run by scripts/check.sh).

Rules: conventions/cad.md sections 2 and 5.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_cad_layout as ccl
import check_sw_refs
import record_export

LAYOUT = ccl.load_json(ccl.LAYOUT_PATH)
CONVENTIONS = ccl.load_json(ccl.CONVENTIONS_PATH)
POINTER = (
    "version https://git-lfs.github.com/spec/v1\noid sha256:"
    + "1" * 64
    + "\nsize 5000000\n"
)


def build(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def git(root: Path, *args: str) -> None:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, env=env
    )


def test_export_record_round_trip(tmp_path: Path) -> None:
    """Guards: protocol - the cad/manifests/exports.json record written by record_export.py and read by check_cad_layout.py (conventions/cad.md section 5)."""
    cad = tmp_path / "cad"
    src, exp = "shoulder/shoulder_b.SLDPRT", "exports/shoulder/shoulder_b.step"
    build(
        cad,
        {
            src: "v1",
            exp: "e1",
            "exports/shoulder/shoulder_c.stl": "",
            "manifests/exports.json": '{"exports": []}',
        },
    )
    manifest = cad / "manifests" / "exports.json"

    def record() -> dict:
        return record_export.record(
            exp, f"cad/{src}", "Default", "AP214", cad_root=cad, manifest=manifest
        )

    def run() -> ccl.Report:
        data = json.loads(manifest.read_text())
        return ccl.Checker(cad, LAYOUT, CONVENTIONS, exports=data).run()

    unrecorded = "exports/shoulder/shoulder_c.stl: no source recorded; run tools/cad/record_export.py EXPORT SOURCE"
    entry = record()
    assert {k: v for k, v in entry.items() if k != "recorded"} == {
        "export": exp,
        "source": src,
        "config": "Default",
        "settings": "AP214",
        "sourceSha256": record_export.content_sha256(cad / src),
        "exportSha256": record_export.content_sha256(cad / exp),
    }
    report = run()
    assert (report.errors, report.warnings) == ([], [unrecorded])

    (cad / src).write_text("v2")
    (cad / exp).write_text("e2")
    report = run()
    assert report.errors == [
        f"{exp}: changed since it was recorded; run tools/cad/record_export.py again"
    ]
    assert report.warnings == [
        f"{exp}: stale: {src} changed after this export; re-export and record it",
        unrecorded,
    ]

    record()  # the fix the messages ask for: one entry per export, and the check is clean again
    assert [e["export"] for e in json.loads(manifest.read_text())["exports"]] == [exp]
    report = run()
    assert (report.errors, report.warnings) == ([], [unrecorded])

    (cad / src).unlink()
    assert run().errors == [
        f"{exp}: source {src} is gone; re-export from the current part or delete the export"
    ]


@pytest.mark.parametrize(
    ("export", "source", "message"),
    [
        (
            "exports/shoulder/x.step",
            "_wip/t/x.SLDPRT",
            "_wip/t/x.SLDPRT: the source must be a promoted file, not a scratch file or an export",
        ),
        (
            "exports/shoulder/x.step",
            "exports/shoulder/x.step",
            "exports/shoulder/x.step: the source must be a promoted file, not a scratch file or an export",
        ),
        (
            "exports/x.step",
            "shoulder/x.SLDPRT",
            "exports/x.step: exports live under cad/exports/<region>/",
        ),
        (
            "shoulder/x.SLDPRT",
            "shoulder/x.SLDPRT",
            "shoulder/x.SLDPRT: exports live under cad/exports/<region>/",
        ),
        (
            "exports/shoulder/x.png",
            "shoulder/x.SLDPRT",
            "exports/shoulder/x.png: only STEP and STL exports are recorded",
        ),
        ("../outside.step", "shoulder/x.SLDPRT", "../outside.step: outside cad/"),
    ],
)
def test_record_export_refuses_what_git_cant_hold(
    tmp_path: Path, export: str, source: str, message: str
) -> None:
    """Guards: bug - a scratch or self source was recorded, then failed CI with "source is gone" for everyone (PR 17 review, 2026-11-09)."""
    cad = tmp_path / "cad"
    build(cad, {"manifests/exports.json": '{"exports": []}'})
    with pytest.raises(SystemExit) as err:
        record_export.record(
            export, source, cad_root=cad, manifest=cad / "manifests" / "exports.json"
        )
    assert str(err.value) == message


def test_reference_check_rejects_refs_git_would_not_hold(tmp_path: Path) -> None:
    """Guards: bug - a committed assembly pointing at an untracked or scratch part opens broken for everyone else (CAD process review, 2026-11-08)."""
    cad = tmp_path / "cad"
    build(
        tmp_path,
        {
            "cad/shoulder/a.SLDPRT": "",
            "cad/shoulder/p.SLDPRT": POINTER,
            "cad/_wip/x/b.SLDPRT": "",
            "outside/c.SLDPRT": "",
        },
    )
    indexed = {"shoulder/a.sldprt", "shoulder/p.sldprt"}

    def why(
        ref: Path,
        ignored: frozenset[str] = frozenset(),
        indexed: frozenset[str] = frozenset(indexed),
        unstaged: frozenset[str] = frozenset(),
    ) -> str | None:
        return check_sw_refs.classify(str(ref), cad, ignored, indexed, unstaged)

    a = cad / "shoulder/a.SLDPRT"
    assert why(a) is None
    assert (
        why(cad / "_wip/x/b.SLDPRT")
        == "in a scratch folder (_wip/_sim/_archive are not committed)"
    )
    assert (
        why(tmp_path / "outside/c.SLDPRT")
        == "outside cad/ (copy it in with Pack and Go)"
    )
    assert (
        why(cad / "gone.SLDPRT")
        == "missing (SolidWorks would search for it or show it suppressed)"
    )
    assert (
        why(a, ignored=frozenset({"shoulder/a.sldprt"}))
        == "matches .gitignore, so it is only in git if force-added; move or rename it"
    )
    assert (
        why(a, indexed=frozenset())
        == "not in git yet (neither committed nor staged); git add it with the promotion"
    )
    assert (
        why(a, unstaged=frozenset({"shoulder/a.sldprt"}))
        == "working copy differs from the staged copy; stage it or restore it"
    )
    assert (
        why(cad / "shoulder/p.SLDPRT")
        == "an LFS pointer, not the file, so its own references can't be read; git lfs pull it"
    )


class FakeSolidWorks:
    def __init__(self, deps: dict[Path, tuple[str, ...] | None]) -> None:
        self.deps = deps

    def GetDocumentDependencies2(
        self, path: str, traverse: bool, search: bool, read_only: bool
    ) -> tuple[str, ...] | None:  # the SolidWorks API name
        assert (traverse, search, read_only) == (True, False, False)
        return self.deps[Path(path)]


def test_scan_checks_the_bytes_the_commit_will_hold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Guards: bug - the index and working-copy rules had no test, and an unreadable file passed with 0 references (PR 17 review, 2026-11-09)."""
    root = tmp_path
    git(root, "init", "-q", "-b", "main")
    build(
        root,
        {
            ".gitignore": "cad/shoulder/z.SLDPRT\n",
            "cad/shoulder/a.SLDPRT": "a",
            "cad/shoulder/b.SLDPRT": "b",
            "cad/shoulder/p.SLDPRT": POINTER,
            "cad/shoulder/z.SLDPRT": "z",
            "cad/arm/arm_left_asm.SLDASM": "asm",
            "cad/arm/arm_right_asm.SLDASM": "asm",
            "cad/_wip/x/w.SLDPRT": "w",
        },
    )
    git(
        root,
        "add",
        ".gitignore",
        "cad/shoulder/a.SLDPRT",
        "cad/shoulder/b.SLDPRT",
        "cad/shoulder/p.SLDPRT",
        "cad/arm",
    )
    git(root, "add", "-f", "cad/shoulder/z.SLDPRT")
    (root / "cad/shoulder/b.SLDPRT").write_text("b2")  # saved after staging
    cad = root / "cad"

    indexed, unstaged = (
        check_sw_refs.index_paths(root),
        check_sw_refs.unstaged_paths(root),
    )
    assert indexed == {
        "arm/arm_left_asm.sldasm",
        "arm/arm_right_asm.sldasm",
        "shoulder/a.sldprt",
        "shoulder/b.sldprt",
        "shoulder/p.sldprt",
        "shoulder/z.sldprt",
    }
    assert unstaged == {"shoulder/b.sldprt"}
    files = check_sw_refs.targets(["--all"], root)
    assert [f.relative_to(root).as_posix() for f in files] == [
        "cad/arm/arm_left_asm.SLDASM",
        "cad/arm/arm_right_asm.SLDASM",
        "cad/shoulder/a.SLDPRT",
        "cad/shoulder/b.SLDPRT",
        "cad/shoulder/p.SLDPRT",
        "cad/shoulder/z.SLDPRT",
    ]
    problems = {
        f.name: check_sw_refs.target_problem(f, indexed, unstaged, cad) for f in files
    }
    assert problems == {
        "arm_left_asm.SLDASM": None,
        "arm_right_asm.SLDASM": None,
        "a.SLDPRT": None,
        "b.SLDPRT": "working copy differs from the staged copy; stage it (git add) or restore it, then re-run",
        "p.SLDPRT": "an LFS pointer, not the file; git lfs pull it, then re-run",
        "z.SLDPRT": None,
    }
    assert check_sw_refs.target_problem(
        cad / "_wip/x/w.SLDPRT", indexed, unstaged, cad
    ) == (
        "in a scratch folder; promote it first (conventions/cad.md section 2, rule 2)"
    )

    left, right, a = (
        cad / "arm/arm_left_asm.SLDASM",
        cad / "arm/arm_right_asm.SLDASM",
        cad / "shoulder/a.SLDPRT",
    )
    refs = [
        a,
        cad / "shoulder/b.SLDPRT",
        cad / "shoulder/p.SLDPRT",
        cad / "shoulder/z.SLDPRT",
        cad / "_wip/x/w.SLDPRT",
    ]
    sw = FakeSolidWorks(
        {left: tuple(x for r in refs for x in (r.name, str(r))), right: None, a: None}
    )
    bad = check_sw_refs.scan(sw, [left, right, a], indexed, unstaged, root)
    assert capsys.readouterr().out.splitlines() == [
        "BAD  cad/arm/arm_left_asm.SLDASM -> "
        + str(PureWindowsPath(cad / "shoulder/b.SLDPRT"))
        + ": working copy differs from the staged copy; stage it or restore it",
        "BAD  cad/arm/arm_left_asm.SLDASM -> "
        + str(PureWindowsPath(cad / "shoulder/p.SLDPRT"))
        + ": an LFS pointer, not the file, so its own references can't be read; git lfs pull it",
        "BAD  cad/arm/arm_left_asm.SLDASM -> "
        + str(PureWindowsPath(cad / "shoulder/z.SLDPRT"))
        + ": matches .gitignore, so it is only in git if force-added; move or rename it",
        "BAD  cad/arm/arm_left_asm.SLDASM -> "
        + str(PureWindowsPath(cad / "_wip/x/w.SLDPRT"))
        + ": in a scratch folder (_wip/_sim/_archive are not committed)",
        "BAD  cad/arm/arm_left_asm.SLDASM: 5 reference(s) checked",
        "BAD  cad/arm/arm_right_asm.SLDASM: SolidWorks returned no references for an assembly or drawing; open it in SolidWorks to see why",
        "ok   cad/shoulder/a.SLDPRT: 0 reference(s) checked",
    ]
    assert bad == 5


def test_a_git_failure_is_not_read_as_nothing_ignored(tmp_path: Path) -> None:
    """Guards: bug - git check-ignore failing (exit 128) read as "nothing ignored", so ignored references passed (PR 17 review, 2026-11-09)."""
    with pytest.raises(subprocess.CalledProcessError):
        check_sw_refs.git_ignored(
            [tmp_path / "cad/a.SLDPRT"], root=tmp_path
        )  # not a git repo
