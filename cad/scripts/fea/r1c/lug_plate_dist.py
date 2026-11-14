"""How the plate force spreads over each hub lug Z face (review 3, item 11; 2026-11-14). The hub's nodal traction on its two Z faces
(as lug_loads.py: t = sigma.n, linear over the face, 0.1 mm grid), compressive normal force only, split by where it lands relative
to the plate (lumped in the model: X offset 18.96-34.2 x Y 288.2-294.6, hole r 1.7 round the bolt):
  within 1 mm of the plate's outer outline / within 1 mm of the plate hole edge / the rest of the plate / outside the plate.
Also the centre of pressure and the force-weighted spread. For the shoulder thread, which applies the plate force more evenly.
    python lug_plate_dist.py NPZ POST_TXT [LABEL] [HUB_HOLE_R=1.9]"""
import re
import sys

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from shapely.geometry import Point, box
from shapely import contains_xy

HX, CZ = 170.49, 5.985875
G = 0.1
BOLTS = {-1: 147.5, 1: 193.5}
d = np.load(sys.argv[1])
p, s = d['pos'], d['s']
lab = sys.argv[3] if len(sys.argv) > 3 else sys.argv[1]
HOLR = float(sys.argv[4]) if len(sys.argv) > 4 else 1.9
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[2]).read().split('\n')[0])
body = np.full(len(p), '?', object)
for nm, a, b in runs:
    body[int(a):int(b) + 1] = nm
hub = body == 'hub'
print(f'{lab}: compressive normal force on each hub lug Z face, by zone (N and % of the face total)')
for side in (-1, 1):
    xo = side * (p[:, 0] - HX)
    bxo = abs(BOLTS[side] - HX)
    lugzone = hub & (xo > 18.5) & (xo < 34.6) & (p[:, 1] > 287.9) & (p[:, 1] < 295.0)
    face = box(18.76, 288.0, 34.4, 294.8).difference(Point(bxo, 292.0).buffer(HOLR, 64))
    plate = box(18.96, 288.2, 34.2, 294.6).difference(Point(bxo, 292.0).buffer(1.7, 64))
    outline_band = plate.difference(box(18.96, 288.2, 34.2, 294.6).buffer(-1.0))
    hole_band = plate.intersection(Point(bxo, 292.0).buffer(2.7, 64))
    for zf, nm, nz in ((11.0, 'front', 1.0), (1.0, 'back', -1.0)):
        m = np.flatnonzero(lugzone & (np.abs(p[:, 2] - zf) < 0.03))
        uv = np.c_[side * (p[m, 0] - HX), p[m, 1]]
        f = LinearNDInterpolator(uv, -s[m, 3] * nz)      # compressive normal pressure (positive) = -sz * nz
        bb = face.bounds
        gu, gv = np.meshgrid(np.arange(bb[0] + G / 2, bb[2], G), np.arange(bb[1] + G / 2, bb[3], G))
        gu, gv = gu.ravel(), gv.ravel()
        k = contains_xy(face, gu, gv)
        gu, gv = gu[k], gv[k]
        pr = f(gu, gv)
        ok = ~np.isnan(pr)
        gu, gv, pr = gu[ok], gv[ok], np.clip(pr[ok], 0, None)
        F = pr * G * G
        tot = F.sum()
        if tot < 2.0:
            print(f'  {"-X" if side < 0 else "+X"} {nm:5s}: {tot:6.1f} N compressive (not loaded)')
            continue
        inpl = contains_xy(plate, gu, gv)
        ob = contains_xy(outline_band, gu, gv)
        hb = contains_xy(hole_band, gu, gv) & ~ob
        rest = inpl & ~ob & ~hb
        cu, cv = (F * gu).sum() / tot, (F * gv).sum() / tot
        su, sv = np.sqrt((F * (gu - cu) ** 2).sum() / tot), np.sqrt((F * (gv - cv) ** 2).sum() / tot)
        z = lambda mk: f'{F[mk].sum():6.1f} N ({F[mk].sum() / tot * 100:4.1f} %)'
        print(f'  {"-X" if side < 0 else "+X"} {nm:5s}: {tot:6.1f} N; within 1 mm of the plate outline {z(ob)}; within 1 mm of the plate '
              f'hole {z(hb)}; rest of the plate {z(rest)}; outside the plate {z(~inpl)}; centre X offset {cu:.2f} Y {cv:.2f}, '
              f'spread (1 sd) {su:.2f} x {sv:.2f} mm; peak {pr.max():.1f} MPa')
