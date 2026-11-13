"""Four lug plates with their lips, placed on the D3b lug faces, as one STL for close_path_r1c.py (HUB_STL) (review A5 / r1g4,
2026-11-13). Outline as lug_shim_print.outline: main face X offset 18.96-34.2 x Y 288.2-TOP, lower strip X offset 18.96-32.5 x
Y 287.2-288.2, bolt hole radius HOLE_R at (offset 23.0, Y 292.0); lip X offset 19.5-32.5 x Y 287.2-288.0, 1.2 tall toward the lug.
    python plates_close_stl.py OUT_STL [T=0.45] [HOLE_R=1.9] [TOP=294.7]      (under capped.py)"""
import sys

import trimesh
from shapely.geometry import Point, box
from shapely.ops import unary_union

HX = 170.49
out = sys.argv[1]
t = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
hr = float(sys.argv[3]) if len(sys.argv) > 3 else 1.9
top = float(sys.argv[4]) if len(sys.argv) > 4 else 294.7
LUG_Z = (1.0, 11.0)      # the lug's Z faces (CZ -+ 5.0)


def xs(side, a, b):
    return (HX - b, HX - a) if side < 0 else (HX + a, HX + b)


parts = []
for side, bx in ((-1, 147.5), (1, 193.5)):
    m0, m1 = xs(side, 18.96, 34.2)
    s0, s1 = xs(side, 18.96, 32.5)
    l0, l1 = xs(side, 19.5, 32.5)
    poly = unary_union([box(m0, 288.2, m1, top), box(s0, 287.2, s1, 288.2)]).difference(Point(bx, 292.0).buffer(hr, 64))
    lip = box(l0, 287.2, l1, 288.0)
    # front plate on the lug's +Z face, lip down toward the lug; back plate on the -Z face, lip up toward the lug
    for z0, lz0 in ((LUG_Z[1], LUG_Z[1] - 1.2), (LUG_Z[0] - t, LUG_Z[0])):
        m = trimesh.creation.extrude_polygon(poly, t)
        m.apply_translation((0, 0, z0))
        parts.append(m)
        L = trimesh.creation.extrude_polygon(lip, 1.2)
        L.apply_translation((0, 0, lz0))
        parts.append(L)
P = trimesh.util.concatenate(parts)
P.export(out)
print(f'plates t {t} hole r {hr} top {top}: {len(parts)} bodies -> {out}')
