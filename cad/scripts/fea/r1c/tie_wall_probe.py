"""R1h tie bridge (review 3, item 9): stress in our -X neck wall where the bridge will stand (Y 255-261, Z CZ-4 to CZ, the inner
wall face at X about 146.2), from r1g6 results that do not contain the bridge. Every arm node of the wall there (X 139-147.5,
Y 254-262, Z CZ-6 to CZ+1) is a 0.5 / 1 / 2 mm sphere centre (average of nodal values over the arm's nodes, as the region report);
the worst vm, layer (sz, tension) and interlayer shear (hypot txz, tyz), with SF against 45 / 22.5 / 13.
    python tie_wall_probe.py NPZ POST_TXT [LABEL]"""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
d = np.load(sys.argv[1])
p, s = d['pos'], d['s']
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[2]).read().split('\n')[0])
body = np.full(len(p), '?', object)
for nm, a, b in runs:
    body[int(a):int(b) + 1] = nm
arm = np.flatnonzero(body == 'arm')
T = np.zeros((len(p), 3, 3))
T[:, 0, 0], T[:, 1, 1], T[:, 2, 2] = s[:, 1], s[:, 2], s[:, 3]
T[:, 0, 1] = T[:, 1, 0] = s[:, 4]
T[:, 0, 2] = T[:, 2, 0] = s[:, 5]
T[:, 1, 2] = T[:, 2, 1] = s[:, 6]
dev = T - np.trace(T, axis1=1, axis2=2)[:, None, None] / 3 * np.eye(3)
val = {'vm': np.sqrt(1.5 * (dev ** 2).sum(axis=(1, 2))), 'layer': s[:, 3], 'shear': np.hypot(s[:, 5], s[:, 6])}
allow = {'vm': 45.0, 'layer': 22.5, 'shear': 13.0}
m = (p[arm, 0] > 139) & (p[arm, 0] < 147.5) & (p[arm, 1] > 254) & (p[arm, 1] < 262) & (p[arm, 2] > CZ - 6) & (p[arm, 2] < CZ + 1)
cand = arm[m]
t = cKDTree(p[arm])
lab = sys.argv[3] if len(sys.argv) > 3 else sys.argv[1]
print(f'{lab}: -X neck wall at the tie bridge (X 139-147.5, Y 254-262, Z - CZ -6 to +1): {len(cand)} arm nodes; wall inner face X '
      f'{p[cand, 0].max():.2f}')
for k in ('vm', 'layer', 'shear'):
    out = []
    for R in (0.5, 1.0, 2.0):
        best = None
        for i in cand:
            nb = arm[t.query_ball_point(p[i], R)]
            v = val[k][nb].mean()
            if best is None or v > best[0]:
                best = (v, i, len(nb))
        v, i, n = best
        sf = allow[k] / v if v > 0 else 99.0
        out.append((R, sf, v, i, n))
    sf = ' / '.join(f'{o[1]:.2f}' for o in out)
    i = out[0][3]
    print(f'   {k:5s} SF .5/1/2 {sf}  (0.5 mm: {out[0][2]:+.2f} MPa, n {out[0][4]}, at {np.round(p[i], 2).tolist()})')
