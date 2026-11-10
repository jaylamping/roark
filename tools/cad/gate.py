"""Pre-print gate: one command per printed part, one pass/fail report. conventions/part-lifecycle.md section 3.

    python tools/cad/gate.py <part>        # e.g. upper_arm_shell_front_left
    python tools/cad/gate.py --all         # every part listed in a requirements spec
    python tools/cad/gate.py --verify      # every 3MF in cad/prints/ has a current passing report (stdlib only; CI)

The part is looked up in the `[[part]]` tables of the requirements specs (cad/<region>/*_requirements.md). The report goes to
cad/prints/<region>/<part>_gate.md, with the hash of every input it judged (spec, export, 3MF, picture sheet, evidence, the
part's mesh-whitelist entry, the `hidden_by` and `mates` meshes), and the exit code is 1 on FAIL. A report is written on
FAIL too, so the failure is visible in review.

Checks, in order: spec agreed; files present; mesh (mesh_check.py); support on visible faces and interference with mating
parts (part_checks.py); 3MF settings and their override flags; evidence (load cases with converged FEA, insertion path and
driver access) recorded against the current export; print-log lessons that apply (warnings).
The mesh checks need numpy, scipy, trimesh and rtree; the rest is stdlib (Python 3.11+ for tomllib).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import time
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitlfs import REPO_ROOT, content_sha256, parse_pointer

CAD_ROOT = REPO_ROOT / "cad"
WHITELIST = "manifests/mesh-whitelist.json"
FRONT = "+++"
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
INTERFERENCE_TOL = 0.05  # mm: tessellation noise on faces that only touch
TEXT_INPUTS = (".md", ".json")


@dataclass
class Check:
    name: str
    status: str
    detail: list[str] = field(default_factory=list)


def front_matter(path: Path) -> dict:
    """The TOML block between the first two `+++` lines of a markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != FRONT:
        raise ValueError(f"{path}: no +++ front matter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == FRONT), None)
    if end is None:
        raise ValueError(f"{path}: front matter not closed with +++")
    return tomllib.loads("\n".join(lines[1:end]))


def specs(cad: Path) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(cad.glob("*/*_requirements.md")):
        if not p.parent.name.startswith("_"):
            out.append((p, front_matter(p)))
    return out


def find_part(cad: Path, name: str) -> tuple[Path, dict, dict]:
    hits = [(p, s, part) for p, s in specs(cad) for part in s.get("part", []) if part.get("name") == name]
    if not hits:
        raise SystemExit(f"{name}: not listed in any cad/<region>/*_requirements.md [[part]] table")
    if len(hits) > 1:
        raise SystemExit(f"{name}: listed in more than one spec: {', '.join(str(h[0]) for h in hits)}")
    return hits[0]


def paths(spec: dict, part: dict) -> dict[str, str]:
    """cad/-relative paths the gate reads and writes for a part. Print files are named after the part (cad.md rule 6)."""
    prints = f"prints/{spec['region']}/{part['name']}"
    return {
        "export": part["export"],
        "3mf": prints + ".3mf",
        "sheet": prints + "_sheet.png",
        "report": prints + "_gate.md",
    }


def has_content(p: Path) -> bool:
    """False for a missing file or an LFS pointer whose content isn't downloaded."""
    return p.is_file() and not (p.stat().st_size <= 1024 and parse_pointer(p.read_bytes()))


# ---- checks -------------------------------------------------------------------------------------------------------------


def check_spec(spec_path: Path, spec: dict) -> Check:
    if spec.get("status") == "agreed" and spec.get("agreed"):
        return Check("requirements agreed", PASS, [f"{spec_path.name}: {spec['agreed']}"])
    return Check("requirements agreed", FAIL, [f"{spec_path.name} is `{spec.get('status')}`; it needs status = \"agreed\" "
                                               "and who agreed it, before anything is printed"])


def check_files(cad: Path, p: dict[str, str]) -> Check:
    missing = [f"cad/{p[k]}" for k in ("export", "3mf", "sheet") if not (cad / p[k]).is_file()]
    no_lfs = [f"cad/{p[k]}" for k in ("export", "3mf") if (cad / p[k]).is_file() and not has_content(cad / p[k])]
    lines = [f"missing: {m}" for m in missing] + [f"LFS content not downloaded: {m} (git lfs pull --include \"{m}\")"
                                                   for m in no_lfs]
    return Check("export, 3MF and picture sheet present", FAIL if lines else PASS, lines)


def settings_of(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("Metadata/project_settings.config"))


def first(v):
    return v[0] if isinstance(v, list) and v else v


def check_3mf(path: Path, spec: dict, part: dict) -> Check:
    """Values the spec asks for, the material, and that each of those settings is flagged in different_settings_to_system:
    Bambu Studio reloads system defaults for any key not flagged there (infill came back as 15%, 2026-11-07). A setting
    whose value is the system preset's isn't flagged by Bambu Studio; the spec names those keys in `preset`."""
    pr = spec.get("print", {})
    want = {**pr.get("settings", {}), **part.get("settings", {})}
    preset = set(pr.get("preset", [])) | set(part.get("preset", []))
    material = part.get("material", pr.get("material"))
    try:
        ps = settings_of(path)
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError) as e:
        return Check("3MF settings", FAIL, [f"can't read project settings: {e}"])
    flagged = {k for entry in ps.get("different_settings_to_system", []) for k in str(entry).split(";") if k}
    bad, ok = [], []
    if not flagged:
        bad.append("different_settings_to_system is empty: Bambu Studio will reset every setting to the system preset")
    if material and str(first(ps.get("filament_type", ""))).upper() != material.upper():
        bad.append(f"filament_type {first(ps.get('filament_type'))!r}, spec says {material!r}")
    for k, v in sorted(want.items()):
        got = first(ps.get(k))
        if got is None or str(got) != str(v):
            bad.append(f"{k} = {got!r}, spec says {v!r}")
        elif k in preset:
            ok.append(f"{k} = {v!r}, the system preset value (spec `preset`)")
        elif k not in flagged:
            bad.append(f"{k} = {v!r} is not flagged in different_settings_to_system: Bambu Studio will reset it on open")
    return Check("3MF settings", FAIL if bad else PASS,
                 bad + ok + [f"{len(want)} settings match, {len(flagged)} keys flagged"])


PASS_MARKS = ("bulk_sf", "layer_sf")


def load_case_sha256(lc: dict) -> str:
    """The hash an evidence file records for each load case it ran: everything that defines the load (`id`, `what` and any
    other key), not the pass marks or the `parts` it applies to, so raising a mark doesn't need a new study. Study scripts
    import this to write `load_cases` in their evidence file."""
    body = {k: v for k, v in lc.items() if k not in (*PASS_MARKS, "parts")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_evidence(cad: Path, spec: dict, part: dict) -> Check:
    """Load cases and the assembly checks, recorded against the export and the load cases as they are now: an FEA of an
    older export or another load is stale (old or singular numbers were once reported as passes, 2026-11-07)."""
    name = "evidence (load cases, access)"
    rel = part.get("evidence", spec.get("evidence"))
    if not rel:
        return Check(name, FAIL, ["no evidence file named in the spec"])
    ev_path = cad / rel
    if not ev_path.is_file():
        return Check(name, FAIL, [f"missing: cad/{rel}"])
    try:
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        bad, ok = evidence_findings(cad, spec, part, rel, ev)
    except (ValueError, TypeError, AttributeError, KeyError) as e:  # malformed JSON or rows of the wrong shape
        return Check(name, FAIL, [f"cad/{rel} can't be read as evidence: {type(e).__name__}: {e}"])
    return Check(name, FAIL if bad else PASS, bad + ok)


def evidence_findings(cad: Path, spec: dict, part: dict, rel: str, ev: dict) -> tuple[list[str], list[str]]:
    name, bad, ok = part["name"], [], []
    sources = ev.get("sources", {})
    if part["export"] not in sources:
        bad.append(f"cad/{rel} does not list {part['export']} in its sources")
    for src, sha in sorted(sources.items()):
        f = cad / src
        if not f.is_file():
            bad.append(f"source cad/{src} no longer exists")
        elif content_sha256(f) != sha:
            bad.append(f"stale: cad/{src} changed since this evidence was recorded")
    link_exports = sorted({p["export"] for p in spec.get("part", [])} - set(sources))
    recorded = ev.get("load_cases", {})
    if not spec.get("load_case"):
        bad.append("the spec lists no load cases")
    for lc in spec.get("load_case", []):
        if lc.get("parts") and name not in lc["parts"]:
            continue
        marks = [k for k in PASS_MARKS if k in lc]
        if not marks:
            bad.append(f"{lc['id']}: the spec gives no pass mark (bulk_sf or layer_sf)")
        for key in marks:
            if not finite(lc[key]) or lc[key] <= 0:
                bad.append(f"{lc['id']}: the spec's {key} = {lc[key]!r} is not a positive finite number")
        rows = [r for r in ev.get("fea", []) if r.get("case") == lc["id"] and r.get("part") in (name, "*")]
        if not rows:
            bad.append(f"{lc['id']}: no FEA result")
            continue
        if recorded.get(lc["id"]) != load_case_sha256(lc):
            bad.append(f"{lc['id']}: the evidence was not recorded for this load case as the spec now states it "
                       "(load_cases hash missing or different); run the study again")
        if any(r.get("part") == "*" for r in rows) and link_exports:
            bad.append(f"{lc['id']}: whole-link result, but its sources leave out {', '.join(link_exports)}")
        if not all(r.get("converged") is True for r in rows):
            bad.append(f"{lc['id']}: mesh convergence not shown (converged must be true)")
        for key in marks:
            got = [r.get(key) for r in rows]
            if not all(finite(g) for g in got):
                bad.append(f"{lc['id']}: {key} {got} is not a finite number in every result")
            elif finite(lc[key]):
                low = min(got)
                (ok if low >= lc[key] else bad).append(f"{lc['id']}: {key} {low:g} (pass {lc[key]:g})")
    acc = [r for r in ev.get("access", []) if r.get("part") == name]
    if not acc:
        bad.append("no insertion-path and driver-access record")
    for r in acc:
        for key in ("insertion_clear", "screws_reachable"):
            if r.get(key) is not True:
                bad.append(f"access: {key} is {r.get(key)!r} ({r.get('notes', '')})")
        if r.get("insertion_clear") is True and r.get("screws_reachable") is True:
            ok.append(f"access: insertion clear, screws reachable ({r.get('method', 'method not given')})")
    return bad, ok


def load_whitelist(cad: Path, name: str) -> dict:
    f = cad / WHITELIST
    return json.loads(f.read_text(encoding="utf-8")).get(name, {}) if f.is_file() else {}


def inputs(cad: Path, spec_path: Path, spec: dict, part: dict, p: dict[str, str]) -> list[tuple[str, str]]:
    """(role, cad/-relative path) of everything a PASS depends on. The mesh whitelist is shared by every part, so only this
    part's entry is pinned, as `manifests/mesh-whitelist.json#<part>`."""
    ev = part.get("evidence", spec.get("evidence"))
    return [("spec", spec_path.relative_to(cad).as_posix()), ("export", p["export"]), ("3mf", p["3mf"]),
            ("sheet", p["sheet"]), *([("evidence", ev)] if ev else []), ("mesh whitelist", f"{WHITELIST}#{part['name']}"),
            *[("hidden by", r) for r in part.get("hidden_by", [])], *[("mate", r) for r in part.get("mates", [])]]


def input_sha(cad: Path, rel: str) -> str:
    """The content hash the report records for an input: the LFS oid for an LFS file, so CI can check it from pointers.
    Text inputs (the spec, the evidence) are hashed with LF line ends, so a Windows checkout with core.autocrlf records
    the same hash CI computes."""
    f = cad / rel.split("#", 1)[0]
    if "#" in rel:
        entry = json.loads(f.read_text(encoding="utf-8")).get(rel.split("#", 1)[1], {}) if f.is_file() else {}
        return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    if not f.is_file():
        return "missing"
    if f.suffix.lower() in TEXT_INPUTS:
        return hashlib.sha256(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return content_sha256(f)


def mesh_checks(cad: Path, spec: dict, part: dict, p: dict[str, str]) -> list[Check]:
    try:
        import trimesh

        import mesh_check
        import part_checks
    except ImportError as e:
        return [Check("mesh, support and interference", FAIL, [f"not run: {e} (pip install numpy scipy trimesh rtree)"])]
    if not has_content(cad / p["export"]):
        return [Check("mesh, support and interference", FAIL, ["not run: no export content"])]
    load = lambda rel: trimesh.load(str(cad / rel), force="mesh")  # noqa: E731
    m = load(p["export"])
    mesh_name = "mesh (bodies, sharp vertices, knife edges, thin walls, surface deviation)"
    try:
        wl = load_whitelist(cad, part["name"])
        ok, rep = mesh_check.check(m, part["name"], bodies=wl.get("bodies", 1), corners=wl.get("corners", ()),
                                   folds=wl.get("folds", ()), thin=wl.get("thin", ()), revolve=wl.get("revolve"))
        out = [Check(mesh_name, PASS if ok else FAIL, rep.strip().splitlines()[2:-1])]
    except (ValueError, TypeError, AttributeError, KeyError) as e:  # malformed whitelist JSON or entry
        out = [Check(mesh_name, FAIL, [f"not run: cad/{WHITELIST} or its entry for {part['name']} is malformed: "
                                        f"{type(e).__name__}: {e}"])]

    out.append(support_check(cad, spec, part, m, load))

    rows, worst = [], 0.0
    for rel in part.get("mates", []):
        if not has_content(cad / rel):
            rows.append(f"missing mating mesh cad/{rel}")
            worst = float("inf")
            continue
        depth, where = part_checks.interference(m, load(rel))
        worst = max(worst, depth)
        rows.append(f"{rel}: deepest overlap {depth:.2f} mm" + (f" at {where}" if where else ""))
    if part.get("mates"):
        out.append(Check("interference with mating parts", PASS if worst <= INTERFERENCE_TOL else FAIL,
                         rows + [f"tolerance {INTERFERENCE_TOL} mm"]))
    else:
        out.append(Check("interference with mating parts", WARN, ["no `mates` listed for this part"]))
    return out


def support_check(cad: Path, spec: dict, part: dict, m, load) -> Check:
    """Support on visible outer faces. A missing `hidden_by` mesh fails: without it, faces it hides count as visible. An
    allowance above zero needs its reason (part-lifecycle.md section 1). Called only once the mesh libraries imported."""
    import trimesh

    import part_checks

    missing = [r for r in part.get("hidden_by", []) if not has_content(cad / r)]
    hide = [load(r) for r in part.get("hidden_by", []) if r not in missing]
    ref = trimesh.util.concatenate([m, *hide]) if hide else None
    areas, _, _ = part_checks.support(m, part["up"], ref=ref)
    allowed = float(part.get("visible_support_mm2", spec.get("print", {}).get("visible_support_mm2", 0)))
    reason = part.get("visible_support_reason")
    line = (f"support on visible outer faces {areas['outer_mm2']} mm2 (allowed {allowed:g}), "
            f"hidden {areas['hidden_mm2']} mm2, up {part['up']}")
    lines = [line] + ([f"where: {areas['outer_where']}"] if "outer_where" in areas else [])
    bad = [f"hidden_by mesh missing or not downloaded: cad/{r}" for r in missing]
    if allowed and not reason:
        bad.append(f"an allowance of {allowed:g} mm2 needs visible_support_reason in the spec")
    elif allowed:
        lines.append(f"allowance: {reason}")
    support_off = str({**spec.get("print", {}).get("settings", {}), **part.get("settings", {})}.get("enable_support")) == "0"
    if support_off:
        lines.append(f"support is off for this part: these {areas['support_mm2']} mm2 print as unsupported overhangs")
    if bad:
        status = FAIL
    else:
        status = WARN if support_off else (PASS if areas["outer_mm2"] <= allowed else FAIL)
    return Check("support on visible faces", status, bad + lines)


def lessons(cad: Path) -> tuple[list[tuple[str, dict]], list[str]]:
    """Every `[[lesson]]` in the print logs, and one error per print log that can't be read: its lessons are unknown, so
    no part may be told that none apply."""
    out, errors = [], []
    for f in sorted(cad.glob("prints/**/*_prints.md")):
        src = f.relative_to(cad).as_posix()
        try:
            out += [(src, les) for les in front_matter(f).get("lesson", [])]
        except ValueError as e:  # tomllib.TOMLDecodeError is a ValueError
            errors.append(f"cad/{src} can't be read, so its lessons are unknown: {e}")
    return out, errors


def check_lessons(cad: Path, spec: dict, part: dict) -> Check:
    """Lessons from earlier prints whose `applies_to` words match this part, its region or its mating parts."""
    material = part.get("material", spec.get("print", {}).get("material", ""))
    hay = " ".join([part["name"], spec["region"], material, *part.get("mates", []), *spec.get("interfaces", [])]).lower()
    found, errors = lessons(cad)
    if errors:
        return Check("lessons from earlier prints", FAIL, errors)
    hits = [f"{les.get('text', '')} (cad/{src}{', allowance ' + str(les['allowance_mm']) + ' mm' if 'allowance_mm' in les else ''})"
            for src, les in found if any(w.lower() in hay for w in les.get("applies_to", []))]
    return Check("lessons from earlier prints", WARN if hits else PASS, hits or ["none apply"])


# ---- report -------------------------------------------------------------------------------------------------------------


def run(cad: Path, name: str) -> tuple[bool, Path]:
    spec_path, spec, part = find_part(cad, name)
    p = paths(spec, part)
    checks = [check_spec(spec_path, spec), check_files(cad, p)]
    checks += mesh_checks(cad, spec, part, p)
    checks.append(check_3mf(cad / p["3mf"], spec, part) if has_content(cad / p["3mf"])
                  else Check("3MF settings", FAIL, ["not run: no 3MF content"]))
    checks.append(check_evidence(cad, spec, part))
    checks.append(check_lessons(cad, spec, part))
    ok = all(c.status != FAIL for c in checks)

    def sha(rel: str) -> str:
        try:
            return input_sha(cad, rel)
        except ValueError:  # a malformed whitelist; the mesh check has already failed on it
            return "unreadable"

    lines = [
        f"# Pre-print gate: {name}",
        "",
        f"Result: {PASS if ok else FAIL}",
        "",
        f"- Gate run: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, `python tools/cad/gate.py {name}`",
        *[f"- Input {role}: {rel} (sha256 {sha(rel)})" for role, rel in inputs(cad, spec_path, spec, part, p)],
        "",
        "| Check | Result |",
        "|---|---|",
        *[f"| {c.name} | {c.status} |" for c in checks],
        "",
    ]
    for c in checks:
        lines += [f"## {c.name}: {c.status}", "", *[f"- {d.strip()}" for d in c.detail], ""]
    report = cad / p["report"]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return ok, report


INPUT = re.compile(r"^- Input ([a-z0-9 ]+): (\S+) \(sha256 (\S+)\)$")


def verify(cad: Path) -> list[str]:
    """Every 3MF under cad/prints/ (any depth, any case of `.3mf`) has a gate report beside it that passed for exactly the
    inputs it records, and every print log parses. Stdlib only and reads LFS pointers, so CI can run it without the CAD
    content."""
    errors = lessons(cad)[1]
    prints = cad / "prints"
    for mf in sorted(f for f in prints.rglob("*") if f.is_file() and f.suffix.lower() == ".3mf"):
        rel = mf.relative_to(cad).as_posix()
        rep = mf.with_name(mf.stem + "_gate.md")
        if not rep.is_file():
            errors.append(f"cad/{rel}: no gate report ({rep.name}); run python tools/cad/gate.py {mf.stem}")
            continue
        text = rep.read_text(encoding="utf-8")
        if "\nResult: PASS\n" not in text:
            errors.append(f"cad/{rel}: its gate report did not pass")
            continue
        recorded = [m.groups() for m in map(INPUT.match, text.splitlines()) if m]
        roles = {role: path for role, path, _ in recorded}
        for role in ("spec", "export", "3mf"):
            if role not in roles:
                errors.append(f"cad/{rel}: gate report records no {role}; run the gate again")
        if roles.get("3mf", rel) != rel:
            errors.append(f"cad/{rel}: gate report is for another 3MF ({roles['3mf']})")
        for role, path, sha in recorded:
            try:
                now = input_sha(cad, path)
            except ValueError as e:
                now = f"unreadable ({e})"
            if now == "missing":
                errors.append(f"cad/{rel}: {role} cad/{path} is missing")
            elif now != sha:
                errors.append(f"cad/{rel}: {role} cad/{path} changed after the gate ran; run it again")
    return errors


def main(argv: list[str], cad: Path = CAD_ROOT) -> int:
    if argv == ["--verify"]:
        errors = verify(cad)
        for e in errors:
            print(f"error: {e}")
        print(f"gate verify: {len(errors)} errors")
        return 1 if errors else 0
    if argv == ["--all"]:
        names = [part["name"] for _, s in specs(cad) for part in s.get("part", [])]
    elif len(argv) == 1 and not argv[0].startswith("-"):
        names = argv
    else:
        print(__doc__)
        return 2
    failed = 0
    for n in names:
        ok, report = run(cad, n)
        failed += not ok
        print(f"{PASS if ok else FAIL}  {n}  ->  {report.relative_to(cad.parent).as_posix()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
