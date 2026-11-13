"""Lug plate top edge against the hub's R1.2 Z-root fillet (2026-11-13, D3c4 check 3), by X-plane sections every 0.1 over each
plate (X offset 18.9-34.3, both lugs, both faces). The plate lies on the lug's Z face by design, so the hub is first cut to the
material beyond the lug face (Z > 11.0 + EPS front, Z < 1.0 - EPS back: the D3 lug faces): what remains near the plate is the fillet and the hub's Y 296
underside. The gap is the distance from the plate section to that remainder. Also: our halves to the full hub section.
    python plate_fillet_gap.py HUB_STL PLATES_STL HALVES_DIR      (under capped.py)"""
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
EPS = 0.002
hub, plates = trimesh.load(sys.argv[1]), trimesh.load(sys.argv[2])
H = [trimesh.load(f'{sys.argv[3]}/upper_arm_organic_{n}_left.STL') for n in ('front', 'back')]


def sec(m, x):
    s = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [1, 2]]).buffer(0))      # (Y, Z)
    return g.buffer(0)


win = box(293.0, CZ - 9.0, 297.0, CZ + 9.0)
res = {}
for side, sx in (('-X', -1), ('+X', 1)):
    for xo in np.round(np.arange(18.9, 34.31, 0.1), 2):
        x = HX + sx * xo
        h = sec(hub, x).intersection(win)
        p = sec(plates, x).intersection(win)
        ours = unary_union([sec(m, x) for m in H]).intersection(win)
        for face, zs in (('front', 1), ('back', -1)):
            beyond = box(293.0, 11.0 + EPS, 297.0, CZ + 9.0) if zs > 0 else box(293.0, CZ - 9.0, 297.0, 1.0 - EPS)      # the lug faces are Z 11.0 / 1.0
            hb = h.intersection(beyond)
            pf = p.intersection(box(293.0, CZ, 297.0, CZ + 9.0) if zs > 0 else box(293.0, CZ - 9.0, 297.0, CZ))
            if not pf.is_empty and not hb.is_empty:
                g = pf.distance(hb)
                k = ('plates', side, face)
                if g < res.get(k, (9e9,))[0]:
                    res[k] = (g, xo)
            of = ours.intersection(box(293.0, CZ, 297.0, CZ + 9.0) if zs > 0 else box(293.0, CZ - 9.0, 297.0, CZ))
            if not of.is_empty and not h.is_empty:
                g = of.distance(h)
                k = ('halves', side, face)
                if g < res.get(k, (9e9,))[0]:
                    res[k] = (g, xo)
for k in sorted(res):
    print(f'{k[0]:6s} {k[1]} lug, {k[2]:5s} face: min gap {res[k][0]:.3f} mm at X offset {res[k][1]:.1f}')
