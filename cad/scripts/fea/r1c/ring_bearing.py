"""R1e shim ring bearing from the lumped runs (2026-11-12): the end-face contact pressure of the 0 gap model (shim lumped into the
end face, end face bearing on the hub disc at Y 302) mapped onto the ring's annulus r 36.2-38.4. Arm-side nodes on the face.
Reports, per run: mean sigma y over the annulus, mean over the compressed part, net axial force (mean x area), peak, worst
0.5 / 1 mm sphere averages (face nodes only), the most-loaded 30 deg sector, against PETG compression (45 MPa used as the
model's yield; printed PETG compressive strength is higher, about 55-60, and through the layers it is not a weak direction).
    python ring_bearing.py NPZ POST_TXT [NPZ POST_TXT ...]      (run under capped.py)"""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
R0, R1, YF = 36.2, 38.4, 302.0
AREA = np.pi * (R1 ** 2 - R0 ** 2)
args = sys.argv[1:]
for npz, post in zip(args[::2], args[1::2]):
    d = np.load(npz)
    p, s = d['pos'], d['s']
    runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(post).read().split('\n')[0])
    body = np.full(len(p), '?', object)
    for nm, a, b in runs:
        body[int(a):int(b) + 1] = nm
    r = np.hypot(p[:, 0] - HX, p[:, 2] - CZ)
    th = np.degrees(np.arctan2(p[:, 2] - CZ, p[:, 0] - HX)) % 360
    m = (body == 'arm') & (np.abs(p[:, 1] - YF) < 0.03) & (r >= R0) & (r <= R1)
    q = np.flatnonzero(m)
    sy = s[:, 2]
    comp = sy[q] < 0
    t = cKDTree(p[q])
    worst = []
    for R in (0.5, 1.0):
        best, n_ = 0.0, 0
        for i in q[np.argsort(sy[q])[:300]]:
            nb = q[t.query_ball_point(p[i], R)]
            v = sy[nb].mean()
            if v < best:
                best, n_ = v, len(nb)
        worst.append((best, n_))
    i = q[np.argmin(sy[q])]
    sec = [(a, sy[q][(th[q] >= a) & (th[q] < a + 30)].mean()) for a in range(0, 360, 30)]
    a_min, v_min = min(sec, key=lambda x: x[1])
    print(f'{npz}')
    print(f'  annulus r {R0}-{R1} at Y {YF}: {len(q)} arm face nodes; area {AREA:.0f} mm2')
    print(f'  mean sigma y {sy[q].mean():+.2f} MPa (net axial force about {sy[q].mean() * AREA:+.0f} N); '
          f'compressed part {comp.mean() * 100:.0f} % of nodes, mean there {sy[q][comp].mean():+.2f} MPa')
    print(f'  most-loaded 30 deg sector: th {a_min}-{a_min + 30}, mean {v_min:+.2f} MPa')
    print(f'  peak {sy[i]:+.2f} MPa at r {r[i]:.2f} th {th[i]:.0f}; worst 0.5 mm average {worst[0][0]:+.2f} (n {worst[0][1]}), '
          f'1 mm {worst[1][0]:+.2f} (n {worst[1][1]}); SF vs 45 MPa: peak {45 / abs(sy[i]):.1f}, 0.5 mm {45 / abs(worst[0][0]):.1f}, '
          f'1 mm {45 / abs(worst[1][0]):.1f}, sector mean {45 / abs(v_min):.1f}')
