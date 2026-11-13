"""R1f/D3 lug-plate bearing and yaw torque share (2026-11-12). The plates are lumped: our post / web / pocket faces sit line-to-line
with the lug Z faces (Z = CZ +- 5.0). On those faces (arm side), sigma z is the plate bearing pressure. Binned on a 0.5 mm grid
over each face (X offset 18-37, Y 287.5-298), cell force = mean sigma z x 0.25 mm2, torque about the hub axis = sum(x_offset x Fz).
Reports per face: force, torque, bearing mean over the loaded part, worst 1 mm average, peak; then the total torque carried by the
plate faces against the applied 17 N.m (the rest goes through the bolts, pads and anything else).
    python plate_bearing.py NPZ POST_TXT [applied N.m]      (run under capped.py)"""
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
T_app = float(sys.argv[3]) if len(sys.argv) > 3 else 17.0
sz = s[:, 3]
tot = 0.0
for side, sx in (('-X lug', -1), ('+X lug', 1)):
    for zs, zn in ((1, 'front Z face'), (-1, 'back Z face')):
        xo = sx * (p[:, 0] - HX)
        m = (body == 'arm') & (np.abs(p[:, 2] - (CZ + zs * 5.0)) < 0.03) & (xo > 18.0) & (xo < 37.0) & (p[:, 1] > 287.5) & (p[:, 1] < 298.0)
        q = np.flatnonzero(m)
        if len(q) == 0:
            print(side, zn, 'no nodes'); continue
        ix, iy = np.floor(xo[q] / 0.5).astype(int), np.floor(p[q, 1] / 0.5).astype(int)
        cells = {}
        for k, (a, b) in enumerate(zip(ix, iy)):
            cells.setdefault((a, b), []).append(q[k])
        Fz, T, comp = 0.0, 0.0, []
        for (a, b), lst in cells.items():
            v = sz[lst].mean()
            if v < 0:      # compression only: the face can't pull
                f = -v * 0.25 * zs * -1      # force on the lug from our face: pushes the lug toward -zs ... sign carried by zs
                Fz += -v * 0.25
                T += (-v * 0.25) * ((a + 0.5) * 0.5) / 1000.0
                comp.append(-v)
        t_ = cKDTree(p[q])
        worst = 0.0
        for i in q[np.argsort(sz[q])[:200]]:
            nb = q[t_.query_ball_point(p[i], 1.0)]
            worst = min(worst, sz[nb].mean())
        i = q[np.argmin(sz[q])]
        tot += T
        print(f'{side} {zn}: {len(q)} face nodes, {len(cells)} cells ({len(cells) * 0.25:.0f} mm2 face); compressive force {Fz:.0f} N, '
              f'torque {T:.2f} N.m; bearing mean over the loaded cells {np.mean(comp) if comp else 0:.1f} MPa, worst 1 mm average {-worst:.1f}, '
              f'peak {-sz[i]:.1f} MPa at x_off {xo[i]:.1f} Y {p[i, 1]:.1f}')
print(f'torque through the plate faces (both lugs, the loaded faces): {tot:.2f} N.m of {T_app} applied ({tot / T_app * 100:.0f} %); '
      f'the rest through the bolts, pads and elsewhere')
