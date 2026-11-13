"""Probe a spot on our part (2026-11-13: the lumped-plate outline corner): sphere averages at 0.5 / 1 / 2 mm of the full stress tensor
over our body's nodes, with node counts, the averaged principal stresses, vm, across-layer tension (sz) and interlayer shear
(hypot txz, tyz), and SF against 45 / 22.5 / 13. Then the same with the centre moved DEPTH into the post along sign(Z - CZ)*Z
(away from the lug: off the model edge; the lumped boss step corner is not in the real part, a separate plate on a flat post face).
Without a point given: the worst 0.5 mm shear centre of the plate-outline-corner spot (X offset 34.2, Y PLATE_TOP, our face).
    python corner_probe.py NPZ POST_TXT [X Y Z] [PLATE_TOP=294.7] [DEPTHS=0.5,1.0]      (under capped.py)"""
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
t = cKDTree(p[arm])
S = np.zeros((len(p), 3, 3))
S[:, 0, 0], S[:, 1, 1], S[:, 2, 2] = s[:, 1], s[:, 2], s[:, 3]
S[:, 0, 1] = S[:, 1, 0] = s[:, 4]
S[:, 0, 2] = S[:, 2, 0] = s[:, 5]
S[:, 1, 2] = S[:, 2, 1] = s[:, 6]
PT = 294.7
if len(sys.argv) >= 6:
    c0 = np.array([float(v) for v in sys.argv[3:6]])
else:
    xo, dz = np.abs(p[:, 0] - HX), np.abs(p[:, 2] - CZ)
    q = arm[(np.hypot(xo[arm] - 34.2, p[arm, 1] - PT) < 1.5) & (dz[arm] > 4.4) & (dz[arm] < 6.0)]
    sh = np.hypot(s[:, 5], s[:, 6])
    best = max(q, key=lambda i: sh[arm[t.query_ball_point(p[i], 0.5)]].mean())
    c0 = p[best]
sgn = np.sign(c0[2] - CZ)
depths = [float(v) for v in (sys.argv[7] if len(sys.argv) > 7 else '0.5,1.0').split(',')]


def report(c, label):
    print(f'-- {label}: centre {np.round(c, 2).tolist()} (X offset {abs(c[0] - HX):.2f}, Z - CZ {c[2] - CZ:+.2f})')
    for R in (0.5, 1.0, 2.0):
        nb = arm[t.query_ball_point(c, R)]
        if len(nb) == 0:
            print(f'   R {R}: no arm nodes'); continue
        A = S[nb].mean(axis=0)
        ev = np.sort(np.linalg.eigvalsh(A))[::-1]
        vm = np.sqrt(0.5 * ((ev[0] - ev[1]) ** 2 + (ev[1] - ev[2]) ** 2 + (ev[2] - ev[0]) ** 2))
        sh = np.hypot(A[0, 2], A[1, 2])
        sz = A[2, 2]
        print(f'   R {R:3.1f}: n {len(nb):4d}  p1 {ev[0]:+7.1f}  p2 {ev[1]:+7.1f}  p3 {ev[2]:+7.1f}  vm {vm:6.1f} (SF {45 / vm if vm else 99:5.2f})  '
              f'sz {sz:+6.1f} (layer SF {22.5 / sz if sz > 0 else 99:5.2f})  shear {sh:5.1f} (SF {13 / sh if sh else 99:5.2f})')


print(f'result: {sys.argv[1]}')
report(c0, 'spot (the model edge)')
for dp in depths:
    report(c0 + np.array([0, 0, sgn * dp]), f'{dp} mm into the post, away from the lug (off the boss step)')
