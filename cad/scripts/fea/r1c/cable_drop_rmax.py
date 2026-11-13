"""For each theta (ours: 0 = +X, positive toward +Z), the largest bundle-centre radius at which a round bundle of Dia DB dropped
straight down (along -Y) clears every Y section of the R1g halves (bolt / screw / insert holes filled), and which plane limits it.
    python cable_drop_rmax.py EXPORTS_DIR OUT_TXT [DB]      (under capped.py)"""
import os
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
E, out = Path(sys.argv[1]), sys.argv[2]
DB = float(sys.argv[3]) if len(sys.argv) > 3 else 16.0
YS = [298, 296, 294, 292, 290, 288, 286, 284, 280, 276, 272, 270, 268, 265, 262, 260, 255, 250, 245, 240]
halves = [trimesh.load(E / f'upper_arm_organic_{n}_left.STL') for n in ('front', 'back')]


def section(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return unary_union([Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > 60.0])
                        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]) if not p.is_empty])


secs = {y: unary_union([section(m, y) for m in halves]) for y in YS}
L = [f'Straight drop of a Dia {DB} bundle along -Y, theta ours (0 = +X lug, + toward +Z front; seam at 0 / 180).',
     'r_max = the largest centre radius clearing every plane Y 298-240 (step 0.25); the limiting plane; and r_max over the hub end only (Y 298-284).',
     f'{"theta":>5} {"r_max all":>9} {"limit Y":>7} {"r_max hub end":>13}']
for t in range(0, 360, 5):
    c, s_ = np.cos(np.radians(t)), np.sin(np.radians(t))
    best, lim, best_h = None, None, None
    for r in np.arange(0, 30.01, 0.25):
        P = Point(HX + r * c, CZ + r * s_)
        bad = [y for y in YS if P.distance(secs[y]) < DB / 2 or secs[y].contains(P)]
        if not bad and best is None or (not bad and best is not None):
            best = r
        elif bad and best is not None and lim is None:
            lim = bad[0]
        if not [y for y in bad if y >= 284]:
            best_h = r
        if bad and [y for y in bad if y >= 284]:
            break
    L.append(f'{t:5d} {("%.2f" % best) if best is not None else "none":>9} {str(lim):>7} {("%.2f" % best_h) if best_h is not None else "none":>13}')
Path(out).write_text('\n'.join(L) + '\n', encoding='utf-8')
print('\n'.join(L))
