"""Elbow cable rig for option A3 (2026-11-15, ELBOW_CABLE_STUDY.md): the power-pair clock-spring under the inboard cap, at full
size, with only the faces that matter. Two prints:
  tray:    the inboard cheek's pocket (r 22-34.8, 5.6 deep: today's 4.3 + the 1.3 of option A3), its drop exit 12 wide through the
           pocket wall at 180 deg (the cap rim opened over the drop), a tie point for the drop end, the centre hole for the stub,
           a clamp tab to hold the tray on a table edge, two notches in the base edge marking the lever's 0 and 124 deg, and three
           holes for the lid's pegs;
  parts:   the stub (a tube, bore 32, OD 40, its top flush with the pocket floor, hanging from a 1.2 flange), with a notch and two
           cable-tie holes to anchor the strip's inner end at the bore, two tie holes near its bottom for the 26 AWG twist option;
           the lid (the cap's underside: a flat disc over the pocket, 3 pegs, a Dia 28 centre hole, 3 narrow viewing slots, two tie
           holes by the centre for the twist option's forearm-side anchor); the lever (keyed onto the stub's bottom, 120 mm,
           pointer tip).
Cheap settings: 0.20 layers, 3 walls, 15 % infill, no support, no brim. Output: C:\\joe\\prints\\elbow-cable-rig\\ (not in git).
    python elbow_cable_rig.py [OUT_DIR]      (from cad/scripts/arm)"""
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.affinity import rotate
from shapely.ops import unary_union

import organic_print as P

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else 'C:/joe/prints/elbow-cable-rig')
OUT.mkdir(parents=True, exist_ok=True)
RI, RO, DEPTH = 22.0, 34.8, 5.6          # pocket (option A3)
BASE = 3.0                                # tray base; the pocket floor is its top
WALL_R = 40.0                             # pocket wall r 34.8-40
HOLE_R = 20.4                             # stub hole (stub OD 40)
CB_R, CB_D = 22.0, 1.2                    # counterbore for the stub's flange (flange top flush with the floor)
STUB_RI, STUB_RO, STUB_L = 16.0, 20.0, 28.0
FL_R = 21.6
DROP_W = 12.0
PEG_R, PEG_D = 37.4, 4.0
SWING = (118.0, 242.0)                    # the lever's 0 and 124 deg marks, centred on the drop side, away from the clamp tab
TIE = 3.0


def disc(r, n=180):
    return Point(0, 0).buffer(r, n)


def ext(poly, z0, h):
    m = trimesh.creation.extrude_polygon(poly, h)
    m.apply_translation((0, 0, z0))
    return m


def union(ms):
    m = trimesh.boolean.union(ms, engine='manifold') if len(ms) > 1 else ms[0]
    return m


def diff(a, bs):
    return trimesh.boolean.difference([a] + bs, engine='manifold')


def tray():
    base2d = unary_union([disc(46.0), box(30, -20, 95, 20)])
    # base edge notches at the lever marks
    for a in SWING:
        base2d = base2d.difference(rotate(box(43.5, -1.0, 47, 1.0), a, origin=(0, 0)))
    base2d = base2d.difference(disc(HOLE_R))
    base = ext(base2d, 0, BASE)
    tab = ext(box(48, -20, 95, 20), 0, 6.0)                       # stiffer clamp tab
    wall2d = disc(WALL_R).difference(disc(RO)).difference(box(-WALL_R - 1, -DROP_W / 2, -RO + 0.5, DROP_W / 2))
    wall = ext(wall2d, BASE, DEPTH)
    t = union([base, tab, wall])
    cuts = [ext(disc(CB_R).difference(disc(HOLE_R - 0.01)), BASE - CB_D, CB_D + 0.01)]
    for a in (0.0, 120.0, 240.0):
        x, y = PEG_R * math.cos(math.radians(a)), PEG_R * math.sin(math.radians(a))
        cuts.append(ext(Point(x, y).buffer(PEG_D / 2 + 0.1, 32), BASE + DEPTH - 4.0, 4.1))
    for y in (-8.5, 8.5):                                           # tie point for the drop end, outside the wall on the drop side
        cuts.append(ext(Point(-43.0, y).buffer(TIE / 2, 24), -0.1, BASE + 0.2))
    return diff(t, cuts)


def stub():
    tube = ext(disc(STUB_RO).difference(disc(STUB_RI)), 0, STUB_L)
    fl = ext(disc(FL_R).difference(disc(STUB_RI)), 0, 1.2)        # printed flange-down; in use it is the top
    key = ext(box(STUB_RO - 0.1, -1.5, STUB_RO + 1.4, 1.5), STUB_L - 8.0, 8.0)
    s = union([tube, fl, key])
    cuts = [ext(box(STUB_RI - 1, -3.5, FL_R + 1, 3.5), -0.1, 4.1)]  # notch at the top end: the strip leaves the bore here
    for z in (6.0, 12.0):                                           # cable-tie holes below the notch (inner-end anchor)
        c = trimesh.creation.cylinder(radius=TIE / 2, height=12, sections=24)
        c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        c.apply_translation((STUB_RO - 1.5, 0, z))
        cuts.append(c)
    for z in (STUB_L - 14.0, STUB_L - 10.5):                        # twist option: the upper-arm-side anchor near the bottom
        c = trimesh.creation.cylinder(radius=TIE / 2, height=12, sections=24)
        c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        c.apply_translation((0, STUB_RO - 1.5, z))
        cuts.append(c)
    return diff(s, cuts)


def lid():
    l2d = disc(WALL_R).difference(disc(14.0))
    for a in (60.0, 180.0, 300.0):
        l2d = l2d.difference(rotate(box(24, -1.5, 33, 1.5), a, origin=(0, 0)))
    for y in (-4.0, 4.0):
        l2d = l2d.difference(Point(17.5, y).buffer(TIE / 2, 24))
    plate = ext(l2d, 0, 2.4)
    pegs = []
    for a in (0.0, 120.0, 240.0):
        x, y = PEG_R * math.cos(math.radians(a)), PEG_R * math.sin(math.radians(a))
        pegs.append(ext(Point(x, y).buffer(PEG_D / 2 - 0.05, 32), 2.4, 3.6))
    return union([plate] + pegs)


def lever():
    ring = disc(26.0).difference(disc(STUB_RO + 0.15)).difference(box(STUB_RO - 0.2, -1.65, STUB_RO + 1.7, 1.65))
    arm = Polygon([(24, -6), (120, -3), (124, 0), (120, 3), (24, 6)])
    return ext(unary_union([ring, arm]), 0, 5.0)


def slice_one(name, part, out):
    d = out / name
    d.mkdir(exist_ok=True)
    (d / 'profile').mkdir(exist_ok=True)
    part.apply_translation((0, 0, -part.bounds[0, 2]))
    part.export(d / f'{name}.stl')
    extra = {'layer_height': '0.2', 'initial_layer_print_height': '0.2', 'wall_loops': '3', 'sparse_infill_density': '15%',
             'enable_support': '0', 'brim_type': 'no_brim'}
    src, size = P.project(name, part, [], extra, d)
    final = f'{name}.3mf'
    args = [P.EXE, '--datadir', str(d / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(d), str(src)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    (d / 'log.txt').write_text(r.stdout[-6000:] + r.stderr[-3000:], errors='replace')
    res = dict(name=name, exit=r.returncode, size_mm=[round(float(v), 1) for v in size], watertight=bool(part.is_watertight),
               volume_mm3=round(float(part.volume), 1))
    f = d / final
    if f.exists():
        z = zipfile.ZipFile(f)
        s = z.read('Metadata/slice_info.config').decode(errors='replace')
        res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
        res['warnings'] = re.findall(r'<warning[^>]*>', s)
        g = [n for n in z.namelist() if n.endswith('.gcode')]
        if g:
            (d / f'{name}.gcode').write_bytes(z.read(g[0]))
    (d / 'result.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res)[:600], flush=True)
    return res


if __name__ == '__main__':
    t = tray()
    s = stub()
    l = lid()
    lv = lever()
    # plate 2: the stub (flange down), the lid (pegs up) and the lever, side by side
    s2 = s.copy(); s2.apply_translation((-50, 0, 0))
    l2 = l.copy(); l2.apply_translation((10, 0, 0))
    lv2 = lv.copy(); lv2.apply_translation((-60, 48, 0))
    parts = trimesh.util.concatenate([s2, l2, lv2])
    for nm, m in (('tray', t), ('stub', s), ('lid', l), ('lever', lv)):
        m.export(OUT / f'elbow_cable_rig_{nm}.stl')
    r1 = slice_one('elbow_cable_rig_tray', t, OUT)
    r2 = slice_one('elbow_cable_rig_parts', parts, OUT)
    (OUT / 'results.json').write_text(json.dumps([r1, r2], indent=1))
