"""Yaw lever for the hub-end coupon (BENCH_TESTS 2b, 2026-11-13): a flat printed PETG plate that keys onto the coupon's cut end
(Y 284) by the coupon's own outer outline, so it needs no feature on the coupon. A hook hole 200 mm from the yaw axis takes the
luggage scale. Set-up: the hub clamped with its axis vertical, the coupon on top (cut end up), the lever dropped over the cut end
(gravity holds it; a rubber band over the top if wanted); pull the scale horizontally, square to the lever, at the hook hole.
  - pocket: the coupon outline at Y 284.5 (both halves, closed), offset +0.20, 5.0 deep; the floor under it is open inside the
    coupon's wall (offset -3) so the lever sits on the wall's cut face, not on anything inside;
  - plate 8.0 thick (5 pocket + 3 floor), the outline offset +6 round the pocket, and an arm along +X to 212 mm from the yaw axis,
    20 wide, with a Dia 6.5 hook hole at 200.0 mm (the arm tip rounded);
  - the arm tapers 50 -> 20 wide in the plate's plane (the pull is in that plane); 100 % infill. Its own bending under 85 N is
    printed on the result for the hook and for the dial point at r 60 (read the play there).
Printed flat (pocket up), no support. Sliced with the arm halves' seed project like the lug plates.
    python yaw_lever_print.py COUPON_DIR OUT_DIR      (from cad/scripts/arm; under capped.py)"""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

import organic_print as P

HX, CZ = 170.49, 5.985875
cdir, out = Path(sys.argv[1]), Path(sys.argv[2])
if out.exists():
    shutil.rmtree(out)
(out / 'profile').mkdir(parents=True)
loops = []
for half in ('front', 'back'):
    m = trimesh.load(cdir / f'upper_arm_organic_{half}_left.STL')
    s = m.section(plane_origin=[0, 284.5, 0], plane_normal=[0, 1, 0])
    for e in s.discrete:
        if len(e) >= 4:
            loops.append(Polygon(e[:, [0, 2]] - [HX, CZ]).buffer(0))
g = Polygon()
for lp in loops:
    g = g.symmetric_difference(lp)
outer = unary_union([Polygon(p.exterior) for p in (g.geoms if isinstance(g, MultiPolygon) else [g])])
outer = max(outer.geoms, key=lambda q: q.area) if isinstance(outer, MultiPolygon) else outer
pocket = outer.buffer(0.20, join_style=2)
floor_hole = outer.buffer(-3.0)
ARM_L, HOOK = 212.0, 200.0
x0 = float(pocket.bounds[2])
W0, W1 = 50.0, 20.0      # tapered arm, in the plate's plane (the scale pulls in that plane, so this width is the bending depth)
arm = unary_union([Polygon([(0.0, -W0 / 2), (x0, -W0 / 2), (ARM_L - 10.0, -W1 / 2), (ARM_L - 10.0, W1 / 2), (x0, W0 / 2), (0.0, W0 / 2)]),
                   Point(ARM_L - 10.0, 0.0).buffer(10.0, 64)])
DIAL_R = 60.0      # read the play here (on the arm's side face): stiff, about 3 % of the hook-point bending
plate = unary_union([pocket.buffer(6.0), arm]).difference(Point(HOOK, 0.0).buffer(3.25, 64))
base = trimesh.creation.extrude_polygon(plate.difference(floor_hole), 3.0)
ring = trimesh.creation.extrude_polygon(plate.difference(pocket), 5.0)
ring.apply_translation((0, 0, 3.0))
part = trimesh.util.concatenate([base, ring])
part.apply_translation((0, 0, -part.bounds[0, 2]))
part.export(out / 'yaw_lever.stl')
bed = part.copy()
bed.apply_transform(trimesh.transformations.rotation_matrix(np.radians(45.0), [0, 0, 1]))      # diagonal on the 256 bed
# the arm's own in-plane bending under 85 N at the hook (cantilever from the pocket edge, PETG E about 2000 MPa, thickness 8,
# width tapering W0 -> W1), at the hook and at the dial point, by numerical integration of M / EI
L_free = HOOK - x0
xs = np.linspace(0.0, L_free, 2001)
wx = W0 + (W1 - W0) * xs / (ARM_L - 10.0 - x0)
EI = 2000.0 * 8.0 * wx ** 3 / 12.0
kap = 85.0 * (L_free - xs) / EI
slope = np.concatenate([[0], np.cumsum((kap[1:] + kap[:-1]) / 2 * np.diff(xs))])
defl_all = np.concatenate([[0], np.cumsum((slope[1:] + slope[:-1]) / 2 * np.diff(xs))])
defl = float(defl_all[-1])
defl_dial = float(np.interp(DIAL_R - x0, xs, defl_all))
extra = {'layer_height': '0.2', 'initial_layer_print_height': '0.2', 'sparse_infill_density': '100%', 'enable_support': '0', 'brim_type': 'no_brim'}
src, size = P.project('yaw_lever', bed, [], extra, out)
final = 'yaw_lever.3mf'
args = [P.EXE, '--datadir', str(out / 'profile'), '--debug', '1', '--slice', '0', '--export-3mf', final, '--outputdir', str(out), str(src)]
r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
res = dict(exit=r.returncode, size_mm=[round(float(v), 1) for v in size], pocket_bounds_from_axis=[round(float(v), 1) for v in pocket.bounds],
           hook_r=HOOK, own_bending_at_hook_mm_85N=round(defl, 3), dial_r=DIAL_R, own_bending_at_dial_mm_85N=round(defl_dial, 4), free_length_mm=round(L_free, 1))
f = out / final
if f.exists():
    z = zipfile.ZipFile(f)
    s = z.read('Metadata/slice_info.config').decode(errors='replace')
    res['info'] = dict(re.findall(r'key="(prediction|weight)" value="([^"]*)"', s))
    gg = [n for n in z.namelist() if n.endswith('.gcode')]
    if gg:
        (out / 'yaw_lever.gcode').write_bytes(z.read(gg[0]))
(out / 'result.json').write_text(json.dumps(res, indent=1))
print(json.dumps(res))
