"""Rev D3b, HUBL_YAW3P38 (the arm's fixed shim plate: dia 3.8 hole, top edge Y 294.7): the WHOLE lug, not a window. Layer,
across-layer shear and von Mises safety factors, both lugs, both load directions (linear, so the other direction is -sigma),
at 304 N and (x 304/370) at 370 N. Each: peak, then 0.5 / 1 / 2 mm averages about the worst of the 300 highest nodes (lowest 0.5 mm SF).
  inner R1.2 root: the Z roots' inner ends, where the fillet runs out on rev D's r 23 bore (X offset 21.5-24.5)
  outer R1.2 root: the Z roots' outer ends (X offset 32.5-34.7)
  plate edge: the lug's outer face beside the plate's top edge (X offset 34.0-34.7, Y 294.3-295.6)
  R0.8 outward root (X offset 34.3-35.4, Y 295.1-296.2)
  bolt-hole rim: the lug Z faces within r 1.7-2.6 of the bolt axis (X offset 23, Y 292; plate hole r 1.9)
  whole lug: every node with X offset 17-37, Y 286-298.5, |Z - 6| <= 6.5 (lug, roots and the spigot just above)
  whole hub: every node; the minimum and where it is
Layer: sigma_y (tensile part) against 22.5 MPa. Shear: sqrt(txy^2 + tyz^2) against 13.0 MPa (assumed). Bulk: von Mises 45 MPa.
python hub_d3b_post38.py NPZ"""
import sys

import numpy as np

import fea_shoulder as FS

RX = FS.RX
L, B = FS.YIELD * FS.LAYER, FS.YIELD
T = L / np.sqrt(3.0)
K370 = 304.0 / 370.0


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
print(f'== {sys.argv[1]}: {len(pos)} nodes. SF peak / 0.5 / 1 / 2 mm at 304 N; [370 N] = x {K370:.3f}; MPa at 304 N peak / 0.5 mm')


def line(lab, m):
    worst = {}
    for sgn in (1.0, -1.0):
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
        print(f'  {lab:40s} {nm:5s} centred {f(cen)} [370 N {f([c * K370 for c in cen])}]  worst-ball {f(wst[1:])} [370 N {f([c * K370 for c in wst[1:]])}]  '
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
