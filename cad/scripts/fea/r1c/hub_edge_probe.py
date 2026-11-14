"""STOP_0 hub -X lug low spot (review 3, item 6 addition; 2026-11-14): is it the lumped plate boss's step edge bearing on the lug's
outer edge? Post-processing only.
 1. The contact pressure (-sz) on the hub's front Z face (Z 11.0) of the -X lug near the spot, by X offset band across the boss
    outline (X offset 34.2) and the lug's outer edge (34.4), over Y 292.4-294.4: mean and peak, and the force per band.
 2. Tensor averages over hub nodes at the spot and stepped away from the boss edge: into the lug (-Z) 0.5 / 1.0 mm, and inward
    (smaller X offset) 0.5 / 1.0 mm: principal stresses, vm, sz, shear, with SF against 45 / 22.5 / 13.
    python hub_edge_probe.py NPZ POST_TXT [X Y Z]"""
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
c0 = np.array([float(v) for v in sys.argv[3:6]]) if len(sys.argv) >= 6 else np.array([136.1, 293.4, 11.0])
hub = np.flatnonzero(body == 'hub')
arm = np.flatnonzero(body == 'arm')
S = np.zeros((len(p), 3, 3))
S[:, 0, 0], S[:, 1, 1], S[:, 2, 2] = s[:, 1], s[:, 2], s[:, 3]
S[:, 0, 1] = S[:, 1, 0] = s[:, 4]
S[:, 0, 2] = S[:, 2, 0] = s[:, 5]
S[:, 1, 2] = S[:, 2, 1] = s[:, 6]
side = np.sign(c0[0] - HX)
xo = side * (p[:, 0] - HX)
print(f'result: {sys.argv[1]}; spot {c0.tolist()} (X offset {side * (c0[0] - HX):.2f}, Z - CZ {c0[2] - CZ:+.2f})')
print('1. contact pressure on the hub front Z face (Z 11.0 +- 0.03), Y 292.4-294.4, by X offset band (hub nodes; arm nodes on Z 11.0 alongside):')
f = (np.abs(p[:, 2] - 11.0) < 0.03) & (p[:, 1] > 292.4) & (p[:, 1] < 294.4)
for lo, hi in ((32.2, 33.2), (33.2, 33.7), (33.7, 34.0), (34.0, 34.2), (34.2, 34.3), (34.3, 34.45)):
    for nm, idx in (('hub', hub), ('arm', arm)):
        m = idx[f[idx] & (xo[idx] >= lo) & (xo[idx] < hi)]
        if len(m) == 0:
            print(f'   X offset {lo:5.2f}-{hi:5.2f} {nm}: no face nodes'); continue
        pr = -s[m, 3] if nm == 'hub' else s[m, 3] * 0 - s[m, 3]
        print(f'   X offset {lo:5.2f}-{hi:5.2f} {nm}: n {len(m):3d}  pressure (-sz) mean {pr.mean():+6.2f} peak {pr.max():+6.2f} MPa')
t = cKDTree(p[hub])


def rep(c, label):
    print(f'-- {label}: {np.round(c, 2).tolist()}')
    for R in (0.5, 1.0, 2.0):
        nb = hub[t.query_ball_point(c, R)]
        if len(nb) == 0:
            print(f'   R {R}: no hub nodes'); continue
        A = S[nb].mean(axis=0)
        ev = np.sort(np.linalg.eigvalsh(A))[::-1]
        vm = np.sqrt(0.5 * ((ev[0] - ev[1]) ** 2 + (ev[1] - ev[2]) ** 2 + (ev[2] - ev[0]) ** 2))
        sh = np.hypot(A[0, 2], A[1, 2])
        vmn = np.sqrt(0.5 * ((s[nb, 1] - s[nb, 2]) ** 2 + (s[nb, 2] - s[nb, 3]) ** 2 + (s[nb, 3] - s[nb, 1]) ** 2) + 3 * (s[nb, 4] ** 2 + s[nb, 5] ** 2 + s[nb, 6] ** 2)).mean()
        print(f'   R {R}: n {len(nb):4d}  p1 {ev[0]:+7.1f} p2 {ev[1]:+7.1f} p3 {ev[2]:+7.1f}  vm (tensor) {vm:6.1f} SF {45 / vm:5.2f}  '
              f'vm (nodal avg) {vmn:6.1f} SF {45 / vmn:5.2f}  sz {A[2, 2]:+6.1f}  shear {sh:5.1f} SF {13 / sh if sh else 99:5.2f}')


rep(c0, 'at the spot')
for dd in (0.5, 1.0):
    rep(c0 + np.array([0, 0, -dd]), f'{dd} mm into the lug (-Z), away from the face the boss bears on')
for dd in (0.5, 1.0):
    rep(c0 + np.array([-side * dd, 0, 0]), f'{dd} mm inward (X offset {side * (c0[0] - HX) - dd:.2f}), inside the boss outline')
