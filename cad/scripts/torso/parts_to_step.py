"""Build a STEP of the rev A torso frame from its parts list (parts.json).

Usage: python3 cad/scripts/torso/parts_to_step.py cad/reference/torso_frame_parts.json cad/reference/torso_frame.step

Torso frame coordinates, mm: X lateral (+X robot left), Y up, Z forward.
Each entry becomes one named solid. Groups 'future' and the pelvis ghost are left out.
"""
import json, sys
from build123d import (Box, Cylinder, Pos, Rot, Compound, Polyline, make_face,
                       extrude, Location, export_step, Axis, Plane, Vector)

SKIP_GROUPS = {"future"}
SKIP_IDS = {"pelvis_ghost"}


def box(lo, hi):
    size = [h - l for l, h in zip(lo, hi)]
    c = [(l + h) / 2 for l, h in zip(lo, hi)]
    return Pos(*c) * Box(*size)


def cyl(c, r, h, axis):
    rot = {"x": Rot(0, 90, 0), "y": Rot(90, 0, 0), "z": Rot(0, 0, 0)}[axis]
    return Pos(*c) * rot * Cylinder(r, h)


def poly(p):
    # outline in the XY plane, plate from z0 to z0 + t (corner radii ignored)
    pts = [Vector(x, y, p["z0"]) for x, y in p["pts"]]
    face = make_face(Polyline(*pts, close=True))
    solid = extrude(face, amount=p["t"], dir=(0, 0, 1))
    for hx, hy, hr in p.get("holes", []):
        solid = solid - Pos(hx, hy, p["z0"] + p["t"] / 2) * Cylinder(hr, p["t"] * 3)
    return solid


def build(p):
    t = p["type"]
    if t == "box":
        return box(p["lo"], p["hi"])
    if t == "cyl":
        return cyl(p["c"], p["r"], p["h"], p["axis"])
    if t == "multibox":
        s = None
        for lo, hi in p["boxes"]:
            b = box(lo, hi)
            s = b if s is None else s + b
        return s
    if t == "poly":
        return poly(p)
    raise ValueError(t)


def main(src, out):
    parts = json.load(open(src))["parts"]
    children, skipped = [], []
    for p in parts:
        if p["group"] in SKIP_GROUPS or p["id"] in SKIP_IDS:
            skipped.append(p["id"]); continue
        s = build(p)
        s.label = f'{p["group"]}__{p["id"]}'
        children.append(s)
    groups = {}
    for s in children:
        groups.setdefault(s.label.split("__")[0], []).append(s)
    top = Compound(label="torso_frame",
                   children=[Compound(label=g, children=v) for g, v in sorted(groups.items())])
    export_step(top, out)
    print(len(children), "solids;", "skipped", skipped)
    print({g: len(v) for g, v in groups.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
