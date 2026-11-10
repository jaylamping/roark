"""Tests for the pre-print gate (pytest; run by scripts/check.sh). Rules: conventions/part-lifecycle.md section 3.

The mesh tests need numpy, scipy, trimesh and rtree and are skipped without them (CI has only pytest); the rest is stdlib.
"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate
from gitlfs import content_sha256

SPEC = """+++
link = "test_link"
region = "upper-arm"
status = "agreed"
agreed = "test 2026-11-09"
evidence = "reviews/upper-arm/20261109_test/evidence.json"

[print]
material = "PETG"
settings = { wall_loops = "6", sparse_infill_density = "50%" }

[[load_case]]
id = "G90"
what = "arm horizontal"
bulk_sf = 2.0
layer_sf = 1.25

[[part]]
name = "upper_arm_test_left"
export = "exports/upper-arm/upper_arm_test_left.stl"
up = [0, 0, 1]
+++
# Test link
"""

GOOD_SETTINGS = {
    "filament_type": ["PETG"],
    "wall_loops": "6",
    "sparse_infill_density": "50%",
    "different_settings_to_system": ["sparse_infill_density;wall_loops", "", ""],
}


def write_3mf(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Metadata/project_settings.config", json.dumps(settings))


def evidence(cad: Path, **over) -> dict:
    ev = {
        "sources": {"exports/upper-arm/upper_arm_test_left.stl": content_sha256(cad / "exports/upper-arm/upper_arm_test_left.stl")},
        "fea": [{"case": "G90", "part": "*", "bulk_sf": 3.1, "layer_sf": 7.0, "converged": True}],
        "access": [{"part": "upper_arm_test_left", "insertion_clear": True, "screws_reachable": True, "method": "test"}],
    }
    ev.update(over)
    return ev


def make_link(cad: Path, export_text: str = "solid x\nendsolid x\n") -> None:
    (cad / "upper-arm").mkdir(parents=True)
    (cad / "upper-arm/test_requirements.md").write_text(SPEC)
    exp = cad / "exports/upper-arm/upper_arm_test_left.stl"
    exp.parent.mkdir(parents=True)
    exp.write_text(export_text)
    ev = cad / "reviews/upper-arm/20261109_test/evidence.json"
    ev.parent.mkdir(parents=True)
    ev.write_text(json.dumps(evidence(cad)))


def test_3mf_with_no_flagged_overrides_fails(tmp_path: Path) -> None:
    """Guards: bug - Bambu Studio reset infill to 15% on open because the overrides weren't flagged (2026-11-07)."""
    spec = gate.front_matter(write(tmp_path / "s.md", SPEC))
    part = spec["part"][0]
    write_3mf(tmp_path / "ok.3mf", GOOD_SETTINGS)
    assert gate.check_3mf(tmp_path / "ok.3mf", spec, part).status == gate.PASS
    write_3mf(tmp_path / "bad.3mf", {**GOOD_SETTINGS, "different_settings_to_system": ["", "", ""]})
    assert gate.check_3mf(tmp_path / "bad.3mf", spec, part).status == gate.FAIL
    write_3mf(tmp_path / "infill.3mf", {**GOOD_SETTINGS, "sparse_infill_density": "15%"})
    assert gate.check_3mf(tmp_path / "infill.3mf", spec, part).status == gate.FAIL
    # some keys flagged, one spec key not: Bambu Studio still resets that one
    write_3mf(tmp_path / "partial.3mf", {**GOOD_SETTINGS, "different_settings_to_system": ["wall_loops", "", ""]})
    c = gate.check_3mf(tmp_path / "partial.3mf", spec, part)
    assert (c.status, c.detail[0]) == (gate.FAIL, "sparse_infill_density = '50%' is not flagged in "
                                       "different_settings_to_system: Bambu Studio will reset it on open")
    # unless the spec says that value is the system preset's
    c = gate.check_3mf(tmp_path / "partial.3mf", {**spec, "print": {**spec["print"], "preset": ["sparse_infill_density"]}}, part)
    assert (c.status, c.detail[0]) == (gate.PASS, "sparse_infill_density = '50%', the system preset value (spec `preset`)")


def test_evidence_for_an_older_export_or_below_the_pass_mark_fails(tmp_path: Path) -> None:
    """Guards: bug - stale and singular FEA numbers were reported as passes (2026-11-07)."""
    cad = tmp_path / "cad"
    make_link(cad)
    _, spec, part = gate.find_part(cad, "upper_arm_test_left")
    assert gate.check_evidence(cad, spec, part).status == gate.PASS
    ev = cad / spec["evidence"]
    for bad in (
        {"fea": [{"case": "G90", "part": "*", "bulk_sf": 1.9, "layer_sf": 7.0, "converged": True}]},
        {"fea": [{"case": "G90", "part": "*", "bulk_sf": 3.1, "layer_sf": 7.0}]},
        {"fea": []},
        {"access": []},
    ):
        ev.write_text(json.dumps(evidence(cad, **bad)))
        assert gate.check_evidence(cad, spec, part).status == gate.FAIL, bad
    ev.write_text(json.dumps(evidence(cad)))
    (cad / part["export"]).write_text("solid y\nendsolid y\n")
    assert gate.check_evidence(cad, spec, part).status == gate.FAIL


def test_verify_needs_a_current_passing_report_for_every_3mf(tmp_path: Path) -> None:
    """Guards: number - a print file is committed only with a passing gate report for exactly the inputs it judged: spec,
    export, 3MF, picture sheet, evidence, the part's mesh-whitelist entry, and the meshes that hide or mate with it."""
    cad = tmp_path / "cad"
    make_link(cad)
    mf = cad / "prints/upper-arm/upper_arm_test_left.3mf"
    write_3mf(mf, GOOD_SETTINGS)
    sheet = cad / "prints/upper-arm/upper_arm_test_left_sheet.png"
    sheet.write_bytes(b"png")
    for rel in ("exports/upper-arm/hider.stl", "exports/upper-arm/mate.stl"):
        (cad / rel).write_text(f"solid {rel}\nendsolid\n")
    (cad / "manifests").mkdir()
    (cad / gate.WHITELIST).write_text(json.dumps({"upper_arm_test_left": {"bodies": 1}, "other": {"bodies": 2}}))
    roles = [("spec", "upper-arm/test_requirements.md"), ("export", "exports/upper-arm/upper_arm_test_left.stl"),
             ("3mf", "prints/upper-arm/upper_arm_test_left.3mf"), ("sheet", "prints/upper-arm/upper_arm_test_left_sheet.png"),
             ("evidence", "reviews/upper-arm/20261109_test/evidence.json"),
             ("mesh whitelist", "manifests/mesh-whitelist.json#upper_arm_test_left"),
             ("hidden by", "exports/upper-arm/hider.stl"), ("mate", "exports/upper-arm/mate.stl")]
    rep = mf.with_name("upper_arm_test_left_gate.md")

    def report(result: str) -> None:
        rep.write_text(f"# gate\n\nResult: {result}\n\n" +
                       "".join(f"- Input {r}: {p} (sha256 {gate.input_sha(cad, p)})\n" for r, p in roles))

    m3 = "cad/prints/upper-arm/upper_arm_test_left.3mf"
    assert gate.verify(cad) == [f"{m3}: no gate report (upper_arm_test_left_gate.md); run python tools/cad/gate.py "
                                "upper_arm_test_left"]
    report("FAIL")
    assert gate.verify(cad) == [f"{m3}: its gate report did not pass"]
    report("PASS")
    assert gate.verify(cad) == []
    wl = json.loads((cad / gate.WHITELIST).read_text())
    (cad / gate.WHITELIST).write_text(json.dumps({**wl, "other": {"bodies": 3}}))  # another part's entry: no effect
    assert gate.verify(cad) == []
    # CRLF line ends from a Windows checkout don't change a text input's hash
    spec = cad / "upper-arm/test_requirements.md"
    spec.write_bytes(spec.read_bytes().replace(b"\n", b"\r\n"))
    assert gate.verify(cad) == []

    def change_spec() -> None:
        spec.write_text(SPEC.replace("bulk_sf = 2.0", "bulk_sf = 1.5"))

    for role, path, change in [
        ("spec", "upper-arm/test_requirements.md", change_spec),
        ("export", "exports/upper-arm/upper_arm_test_left.stl", lambda: (cad / roles[1][1]).write_text("solid y\nendsolid y\n")),
        ("3mf", "prints/upper-arm/upper_arm_test_left.3mf", lambda: write_3mf(mf, {**GOOD_SETTINGS, "wall_loops": "4"})),
        ("evidence", roles[4][1], lambda: (cad / roles[4][1]).write_text(json.dumps(evidence(cad, fea=[])))),
        ("mesh whitelist", roles[5][1], lambda: (cad / gate.WHITELIST).write_text(json.dumps({**wl, "upper_arm_test_left": {}}))),
        ("hidden by", roles[6][1], lambda: (cad / roles[6][1]).write_text("solid z\nendsolid z\n")),
        ("mate", roles[7][1], lambda: (cad / roles[7][1]).write_text("solid z\nendsolid z\n")),
    ]:
        report("PASS")
        change()
        assert gate.verify(cad) == [f"{m3}: {role} cad/{path} changed after the gate ran; run it again"], role
    report("PASS")
    sheet.unlink()
    assert gate.verify(cad) == [f"{m3}: sheet cad/prints/upper-arm/upper_arm_test_left_sheet.png is missing"]
    # a 3MF in a sub-folder or with an upper-case extension still needs its report
    write_3mf(cad / "prints/upper-arm/sub/other.3MF", GOOD_SETTINGS)
    sheet.write_bytes(b"png")
    assert gate.verify(cad) == ["cad/prints/upper-arm/sub/other.3MF: no gate report (other_gate.md); run python "
                                "tools/cad/gate.py other"]


def test_a_print_log_that_does_not_parse_fails_instead_of_hiding_its_lessons(tmp_path: Path) -> None:
    """Guards: bug - a print log with a TOML typo was skipped, and the gate reported that no lessons apply (found
    2026-11-10)."""
    cad = tmp_path / "cad"
    make_link(cad)
    _, spec, part = gate.find_part(cad, "upper_arm_test_left")
    log = cad / "prints/upper-arm/upper_arm_prints.md"
    log.parent.mkdir(parents=True)
    log.write_text('+++\n[[lesson]]\nid = "tab"\napplies_to = ["upper-arm"]\ntext = "check the tab"\n+++\n')
    c = gate.check_lessons(cad, spec, part)
    assert (c.status, c.detail) == (gate.WARN, ["check the tab (cad/prints/upper-arm/upper_arm_prints.md)"])
    log.write_text('+++\n[[lesson]]\nid = "tab\n+++\n')
    c = gate.check_lessons(cad, spec, part)
    assert c.status == gate.FAIL
    assert c.detail[0].startswith("cad/prints/upper-arm/upper_arm_prints.md can't be read, so its lessons are unknown: ")
    assert gate.verify(cad) == c.detail


def write(p: Path, text: str) -> Path:
    p.write_text(text)
    return p


def test_support_on_a_visible_face_is_found(tmp_path: Path) -> None:
    """Guards: bug - the one-piece upper arm printed with supported, rough outer skin (2026-11-08)."""
    trimesh = pytest.importorskip("trimesh")
    import part_checks

    # a T: a 10 mm stem with two 10 mm arms on top; printed stem-down, the arms' undersides are visible overhangs
    box = lambda size, at: trimesh.creation.box(size, trimesh.transformations.translation_matrix(at))  # noqa: E731
    t = trimesh.util.concatenate([box((10, 10, 25), (0, 0, 12.5)), box((10, 10, 5), (-10, 0, 22.5)), box((10, 10, 5), (10, 0, 22.5))])
    areas, _, _ = part_checks.support(t, [0, 0, 1])
    assert areas["outer_mm2"] >= 190  # 2 x 10 x 10 mm under the cap arms
    areas, _, _ = part_checks.support(t, [0, 0, -1])  # cap down: nothing hangs
    assert areas["outer_mm2"] == 0


def test_interference_depth_with_a_mating_part(tmp_path: Path) -> None:
    """Guards: bug - an RS02 housing tab overlapped the printed upper arm by about 1 mm and nothing flagged it (2026-11-08)."""
    trimesh = pytest.importorskip("trimesh")
    import part_checks

    a = trimesh.creation.box((20, 20, 20))
    touching = trimesh.creation.box((20, 20, 20), trimesh.transformations.translation_matrix((20, 0, 0)))
    overlap = trimesh.creation.box((20, 20, 20), trimesh.transformations.translation_matrix((19, 0, 0)))
    assert part_checks.interference(a, touching, samples=4000)[0] <= gate.INTERFERENCE_TOL
    assert part_checks.interference(a, overlap, samples=4000)[0] == pytest.approx(1.0, abs=0.1)


def test_gate_passes_a_clean_part_end_to_end(tmp_path: Path) -> None:
    """Guards: number - the gate's pass/fail is the AND of every check, and its report is what --verify accepts."""
    trimesh = pytest.importorskip("trimesh")
    pytest.importorskip("scipy")
    cad = tmp_path / "cad"
    box = trimesh.creation.box((40, 30, 20), trimesh.transformations.translation_matrix((0, 0, 10)))
    make_link(cad, export_text="")
    box.export(cad / "exports/upper-arm/upper_arm_test_left.stl")
    ev = cad / "reviews/upper-arm/20261109_test/evidence.json"
    ev.write_text(json.dumps(evidence(cad)))
    write_3mf(cad / "prints/upper-arm/upper_arm_test_left.3mf", GOOD_SETTINGS)
    (cad / "prints/upper-arm/upper_arm_test_left_sheet.png").write_bytes(b"png")
    ok, report = gate.run(cad, "upper_arm_test_left")
    assert ok, report.read_text()
    assert gate.verify(cad) == []
    (cad / "upper-arm/test_requirements.md").write_text(SPEC.replace('status = "agreed"', 'status = "draft"'))
    ok, _ = gate.run(cad, "upper_arm_test_left")
    assert not ok
