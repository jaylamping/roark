"""Hub lug read-out for any lug case (the read-out of hub_d3b_post38.py with the load label, the scaled columns and the load
direction as arguments): the WHOLE lug and the whole hub, not a window. Layer, across-layer shear and von Mises safety factors,
both lugs. Each: peak, then 0.5 / 1 / 2 mm averages about the worst of the 300 highest nodes (lowest 0.5 mm SF).
    python hub_lug_post.py NPZ "base label" both|as ["label=factor" ...]
  both: the load is reversible (plain yaw), so the worse of +sigma and -sigma is read; as: only the direction applied.
  "label=factor": an extra column, SF x factor (a load k times the base has factor 1/k).
Layer: sigma_y (tensile part) against 22.5 MPa. Shear: sqrt(txy^2 + tyz^2) against 13.0 MPa (assumed). Bulk: von Mises 45 MPa.
"""
import sys

import numpy as np

import fea_shoulder as FS

RX = FS.RX
L, B = FS.YIELD * FS.LAYER, FS.YIELD
T = L / np.sqrt(3.0)
BASE, DIRS = sys.argv[2], sys.argv[3]
SCALES = [(a.split('=')[0], float(a.split('=')[1])) for a in sys.argv[4:]]
SIGNS = (1.0, -1.0) if DIRS == 'both' else (1.0,)


TREE = None


def sf_stats(pos, val, allow, m, ncand=300):
    """Two readings. 'centred' (as every earlier case): SF at the peak of val in mask m and over the nodes within 0.5 / 1 /
    2 mm of that peak node. 'worst': of the ncand highest nodes, the one whose 0.5 mm average is highest, and the 0.5 / 1 /
    2 mm averages about it (the worst 0.5 mm ball near the peak; never better than centred at 0.5 mm)."""
    idx = np.flatnonzero(m)
    top = idx[np.argsort(val[idx])[-ncand:]]
    ip = top[-1]
    avg05 = np.array([val[TREE.query_ball_point(pos[i], 0.5)].mean() for i in top])
    iw = top[np.argmax(avg05)]
    pk = allow / max(val[ip], 1e-9)
    cen = [pk] + [allow / max(val[TREE.query_ball_point(pos[ip], r)].mean(), 1e-9) for r in (0.5, 1.0, 2.0)]
    wst = [pk] + [allow / max(val[TREE.query_ball_point(pos[iw], r)].mean(), 1e-9) for r in (0.5, 1.0, 2.0)]
    return cen, wst, pos[ip], pos[iw]


z = np.load(str(FS.F / f'{sys.argv[1]}.npz'))
pos, s = z['pos'], z['s']
from scipy.spatial import cKDTree
TREE = cKDTree(pos)
x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - 6.0
ax = np.abs(x)
rb = np.hypot(ax - 23.0, y - 292.0)
tau = np.hypot(s[:, 4], s[:, 6])
vm = s[:, 10]
zroot = (y > 294.7) & (y < 296.2) & (np.abs(zz) > 4.9) & (np.abs(zz) < 6.3)
spots = {
    'inner R1.2 root (X 21.5-24.5)': (ax > 21.5) & (ax < 24.5) & zroot,
    'outer R1.2 root (X 32.5-34.7)': (ax > 32.5) & (ax < 34.7) & zroot,
    'plate edge (outer face, Y 294.7)': (ax > 34.0) & (ax < 34.7) & (y > 294.3) & (y < 295.6) & (np.abs(zz) < 5.05),
    'R0.8 outward root': (ax > 34.3) & (ax < 35.4) & (y > 295.1) & (y < 296.2) & (np.abs(zz) < 5.05),
    'bolt-hole rim (Z faces, r 1.7-2.6)': (rb > 1.65) & (rb < 2.6) & (np.abs(np.abs(zz) - 5.0) < 0.15),
    'WHOLE LUG': (ax > 17.0) & (ax < 37.0) & (y > 286.0) & (y < 298.5) & (np.abs(zz) <= 6.5),
}
print(f'== {sys.argv[1]}: {len(pos)} nodes. SF peak / 0.5 / 1 / 2 mm at {BASE}; ' + '; '.join(f'[{a}] = x {k:.3f}' for a, k in SCALES) + f'; MPa at {BASE} peak / 0.5 mm; direction: {DIRS}')


def line(lab, m):
    worst = {}
    for sgn in SIGNS:
        sy = np.maximum(sgn * s[:, 2], 0.0)
        for nm, val, allow in (('layer', sy, L), ('shear', tau, T), ('vM', vm, B)):
            r_ = sf_stats(pos, val, allow, m)
            if nm not in worst or r_[0][1] < worst[nm][0][0][1]:
                worst[nm] = (r_, sgn)
    for nm in ('layer', 'shear', 'vM'):
        (cen, wst, pp, pw), sgn = worst[nm]
        allow = {'layer': L, 'shear': T, 'vM': B}[nm]
        f = lambda v: ' / '.join(f'{q:5.2f}' for q in v)
        q = pp - [RX, 0, 6.0]
        sc = ''.join(f' [{a} {f([c * k for c in wst[1:]])}]' for a, k in SCALES)
        print(f'  {lab:40s} {nm:5s} centred {f(cen)}  worst-ball {f(wst[1:])}{sc}  '
              f'MPa pk {allow / cen[0]:4.1f} c0.5 {allow / cen[1]:4.1f} w0.5 {allow / wst[1]:4.1f}  peak at X {q[0]:+.2f} Y {q[1]:.2f} Z-6 {q[2]:+.2f}'
              + (f' dir {"+" if sgn > 0 else "-"}' if nm == 'layer' else ''))


for lug, lx in (('-X lug', x < 0), ('+X lug', x > 0)):
    for k, m0 in spots.items():
        m = m0 & lx
        if m.any():
            line(f'{lug} {k}', m)
        else:
            print(f'  {lug} {k}: no nodes')
line('WHOLE HUB (global)', np.ones(len(pos), bool))
