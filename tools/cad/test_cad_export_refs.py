"""Tests for export records and the SolidWorks reference check (pytest; run by scripts/check.sh).

Rules: conventions/cad.md sections 2 and 5.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_cad_layout as ccl
import check_sw_refs
import record_export

LAYOUT = ccl.load_json(ccl.LAYOUT_PATH)
CONVENTIONS = ccl.load_json(ccl.CONVENTIONS_PATH)


def build(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def test_recorded_export_goes_stale_when_its_source_changes(tmp_path: Path) -> None:
    """Guards: number - export records in cad/manifests/exports.json: stale source warns, changed export fails."""
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
    record_export.record(
        exp, f"cad/{src}", "Default", "AP214", cad_root=cad, manifest=manifest
    )
    data = json.loads(manifest.read_text())
    assert data["exports"][0]["source"] == src

    def run() -> ccl.Report:
        return ccl.Checker(cad, LAYOUT, CONVENTIONS, exports=data).run()

    report = run()
    assert report.errors == []
    assert [w.split(":")[0] for w in report.warnings] == [
        "exports/shoulder/shoulder_c.stl"
    ]  # no record yet
    (cad / src).write_text("v2")
    (cad / exp).write_text("e2")
    report = run()
    assert any("stale" in w for w in report.warnings)
    assert any("changed since it was recorded" in e for e in report.errors)
    (cad / src).unlink()
    assert any("is gone" in e for e in run().errors)


def test_reference_check_rejects_refs_git_would_not_hold(tmp_path: Path) -> None:
    """Guards: bug - a committed assembly pointing at an untracked or scratch part opens broken for everyone else (CAD process review, 2026-11-08)."""
    cad = tmp_path / "cad"
    build(
        tmp_path,
        {
            "cad/shoulder/a.SLDPRT": "",
            "cad/_wip/x/b.SLDPRT": "",
            "outside/c.SLDPRT": "",
        },
    )
    indexed = {"shoulder/a.sldprt"}
    assert (
        check_sw_refs.classify(str(cad / "shoulder/a.SLDPRT"), cad, set(), indexed)
        is None
    )
    assert "scratch" in check_sw_refs.classify(
        str(cad / "_wip/x/b.SLDPRT"), cad, set(), indexed
    )
    assert "outside cad/" in check_sw_refs.classify(
        str(tmp_path / "outside/c.SLDPRT"), cad, set(), indexed
    )
    assert "missing" in check_sw_refs.classify(
        str(cad / "gone.SLDPRT"), cad, set(), indexed
    )
    assert "gitignored" in check_sw_refs.classify(
        str(cad / "shoulder/a.SLDPRT"), cad, {"shoulder/a.sldprt"}, indexed
    )
    assert "not in git yet" in check_sw_refs.classify(
        str(cad / "shoulder/a.SLDPRT"), cad, set(), set()
    )
