"""Named-spot report for the R1g plate-hole studies (2026-11-13): worst sphere averages at 0.5 / 1 / 2 mm with the node count in
each sphere (to tell a corner from a section), vm / layer / shear, for:
  hub lug face at the plate-hole edge, hub lug roots (Y 294-297.5), our post at the boss hole edge, the hub groove bottom,
  the plate outline corner (our face at X offset 34.2, Y 294.6).
    python spot_report.py NPZ POST_TXT HOLE_R [PLATE_TOP]      (run under capped.py)"""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
BOLTS = (147.5, 193.5)
d = np.load(sys.argv[1])
p, s = d['pos'], d['s']
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[2]).read().split('\n')[0])
body = np.full(len(p), '?', object)
for nm, a, b in runs:
    body[int(a):int(b) + 1] = nm
hr = float(sys.argv[3])
PT = float(sys.argv[4]) if len(sys.argv) > 4 else 294.6      # plate top Y (r1g4: 294.7)
r_axis = np.hypot(p[:, 0] - HX, p[:, 2] - CZ)
xo = np.abs(p[:, 0] - HX)
rb = np.min([np.hypot(p[:, 0] - bx, p[:, 1] - 292.0) for bx in BOLTS], axis=0)
dz = np.abs(p[:, 2] - CZ)
vm = s[:, 10]
LAYER = {'arm': s[:, 3], 'hub': s[:, 2]}
SHEAR = {'arm': np.hypot(s[:, 5], s[:, 6]), 'hub': np.hypot(s[:, 4], s[:, 6])}
SPOTS = [
    ('hub lug face at the plate-hole edge', 'hub', (dz > 4.4) & (dz < 5.6) & (rb > hr - 0.6) & (rb < hr + 0.6)),
    ('hub lug roots (Y 294-297.5)', 'hub', (p[:, 1] > 294.0) & (p[:, 1] < 297.5) & (xo > 18.0) & (xo < 36.0) & (dz < 7.0)),
    ('our post at the boss hole edge', 'arm', (dz > 4.4) & (dz < 6.6) & (rb > hr - 0.3) & (rb < hr + 0.6)),
    ('hub groove bottom (Y 299.1-302, r 31-35.85)', 'hub', (p[:, 1] > 299.1) & (p[:, 1] < 302.0) & (r_axis > 31.0) & (r_axis < 35.85)),
    ('plate outline corner (our face, X offset 34.2, Y 294.6)', 'arm', (np.hypot(xo - 34.2, p[:, 1] - PT) < 1.5) & (dz > 4.4) & (dz < 6.0)),
    # 2026-11-13 (shoulder thread's governing hub spot under yaw): the INNER end of the R1.2 Z roots, where the fillet runs out onto the
    # r 23 bore wall, X offset 21.5-24.5, Y 294.8-296, per lug
    ('hub R1.2 root inner end, -X lug (X off 21.5-24.5, Y 294.8-296)', 'hub', (p[:, 0] < HX) & (xo > 21.5) & (xo < 24.5) & (p[:, 1] > 294.8) & (p[:, 1] < 296.0) & (dz > 3.5) & (dz < 7.0)),
    ('hub R1.2 root inner end, +X lug (X off 21.5-24.5, Y 294.8-296)', 'hub', (p[:, 0] > HX) & (xo > 21.5) & (xo < 24.5) & (p[:, 1] > 294.8) & (p[:, 1] < 296.0) & (dz > 3.5) & (dz < 7.0)),
]
for label, b, geo in SPOTS:
    m = (body == b) & geo
    q = np.flatnonzero(m)
    print(f'-- {label}: {len(q)} nodes')
    if len(q) == 0:
        continue
    bq = np.flatnonzero(body == b)      # review M1 (2026-11-13): average over every node of the body in the sphere, as hub_r1c does
    t = cKDTree(p[bq])
    for nm, v, A in (('vm', vm, 45.0), ('layer', LAYER[b], 22.5), ('shear', SHEAR[b], 13.0)):
        out = []
        for R in (0.5, 1.0, 2.0):
            best, bn, bat = 0.0, 0, None
            for i in q:      # every node of the spot a candidate centre (review M3)
                nb = bq[t.query_ball_point(p[i], R)]
                mv = v[nb].mean()
                if mv > best:
                    best, bn, bat = mv, len(nb), p[i]
            out.append((A / best if best > 0 else 99.0, bn, bat))
        print(f'   {nm:6s} SF .5/1/2 {out[0][0]:.2f}/{out[1][0]:.2f}/{out[2][0]:.2f}  n {out[0][1]}/{out[1][1]}/{out[2][1]}  at {np.round(out[0][2], 1).tolist()}')
