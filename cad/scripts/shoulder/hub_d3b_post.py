"""Rev D3b, HUBL_YAW3P (couple on the shim-plate area): layer, across-layer shear and von Mises safety factors at the spots the
arm thread asked for, both lugs, both directions, at 304 N and (x 304/370) at 370 N. Each: peak / 0.5 / 1 / 2 mm average about
the peak node of that measure.
  plate edge: the lug's outer face beside the shim plate's top edge (X offset 34.0-34.7, Y 294.3-295.5)
  R0.8 root:  the outward root where the outer face meets the spigot underside (X offset 34.3-35.4, Y 295.1-296.2)
  R1.2 run-out: the Z roots' outer ends (X offset 32.5-34.7, Y 294.7-296.2, |Z - 6| 4.9-6.3)
  bolt-hole rim: the lug Z faces within r 1.7-2.6 of the bolt axis (X offset 23, Y 292; the arm's plate hole is dia 4.4)
Layer: sigma_y (tensile part) against 22.5 MPa. Shear: sqrt(txy^2 + tyz^2) across the layers, against 22.5 / sqrt(3) = 13.0 MPa
(an assumed interlayer shear allowable: the layer strength through the von Mises shear relation). Bulk: von Mises against 45 MPa.
python hub_d3b_post.py NPZ"""
import sys

import numpy as np

import fea_shoulder as FS

RX = FS.RX
L, B = FS.YIELD * FS.LAYER, FS.YIELD
T = L / np.sqrt(3.0)
K370 = 304.0 / 370.0


def sf_stats(pos, val, allow, m):
    """SF at the peak of val in mask m and over the nodes within 0.5 / 1 / 2 mm of it (val >= 0 there)."""
    i = np.flatnonzero(m)[np.argmax(val[m])]
    d = np.linalg.norm(pos - pos[i], axis=1)
    out = [allow / max(val[i], 1e-9)]
    for rad in (0.5, 1.0, 2.0):
        out.append(allow / max(val[d <= rad].mean(), 1e-9))
    return out, pos[i]


z = np.load(str(FS.F / f'{sys.argv[1]}.npz'))
pos, s = z['pos'], z['s']
x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - 6.0
ax = np.abs(x)
tau = np.hypot(s[:, 4], s[:, 6])
vm = s[:, 10]
spots = {
    'plate edge (outer face, X 34.4, Y 294.9)': (ax > 34.0) & (ax < 34.7) & (y > 294.3) & (y < 295.5) & (np.abs(zz) < 5.05),
    'R0.8 outward root': (ax > 34.3) & (ax < 35.4) & (y > 295.1) & (y < 296.2) & (np.abs(zz) < 5.05),
    'R1.2 run-out (Z root outer end)': (ax > 32.5) & (ax < 34.7) & (y > 294.7) & (y < 296.2) & (np.abs(zz) > 4.9) & (np.abs(zz) < 6.3),
    'bolt-hole rim (Z faces, r 1.7-2.6 of the hole axis)': (np.hypot(ax - 23.0, y - 292.0) > 1.65) & (np.hypot(ax - 23.0, y - 292.0) < 2.6) & (np.abs(np.abs(zz) - 5.0) < 0.15),
    'plate-hole edge dia 6.0 (Z faces, r 2.6-3.4)': (np.hypot(ax - 23.0, y - 292.0) > 2.6) & (np.hypot(ax - 23.0, y - 292.0) < 3.4) & (np.abs(np.abs(zz) - 5.0) < 0.15),
}
print(f'== {sys.argv[1]}: {len(pos)} nodes. SF peak / 0.5 / 1 / 2 mm at 304 N; [370 N] = x {K370:.3f}')
for lug, lx in (('-X lug', x < 0), ('+X lug', x > 0)):
    for k, m0 in spots.items():
        m = m0 & lx
        if not m.any():
            print(f'  {lug} {k}: no nodes')
            continue
        worst = {}
        for sgn in (1.0, -1.0):
            sy = np.maximum(sgn * s[:, 2], 0.0)
            for nm, val, allow in (('layer', sy, L), ('shear', tau, T), ('vM', vm, B)):
                st, p = sf_stats(pos, val, allow, m)
                if nm not in worst or st[1] < worst[nm][0][1]:
                    worst[nm] = (st, p, sgn)
        for nm in ('layer', 'shear', 'vM'):
            st, p, sgn = worst[nm]
            f = ' / '.join(f'{v:5.2f}' for v in st)
            f370 = ' / '.join(f'{v * K370:5.2f}' for v in st)
            allow = {'layer': L, 'shear': T, 'vM': B}[nm]
            mpa = ' / '.join(f'{allow / v:5.1f}' for v in st)
            print(f'  {lug} {k:38s} {nm:5s} {f}   [370 N: {f370}]   MPa at 304 N: {mpa}   at {p.round(2).tolist()}' + (f' dir {"+" if sgn > 0 else "-"}' if nm == 'layer' else ''))
