"""Read-out of the RS02-on-fork bolted cases (fea_shoulder.py R2_*; OPEN_ASSUMPTIONS item 49). Body-safe: the aluminium
stand-in for the RS02 lies inside the cuff's bore below the seat plane (r under 39.5 of the yaw axis, Y up to 351.86),
where the fork has no material, so its nodes are told apart by position; the nodes on the seat plane itself are left
out too (both bodies have nodes there), so the fork's seat face is read from just above it.

    python fork_r2_post.py TAG [TAG ...]        (TAG as run_r2.sh names the results: p250, p1000)

Safety factors, worst 0.5 / 1 / 2 mm ball: von Mises (45 MPa), layer tension (sigma_y, 22.5 MPa; the fork prints Y up),
shear across the layers (sqrt(txy^2 + tyz^2), 13.0 MPa, assumed). Regions:
  seat ring        the RS02's seat ring, Y 351.9 to 362.5, r 33 to 46.5 of the yaw axis
    at the screws  the part of it within 4.5 mm of a screw axis
    tie rings out  the same without the nodes within 1.2 mm of a head-seat edge (where the model's screw is tied rigidly)
    between screws the rest of the ring
  rest of the fork everything else, with the usual bands round the boss face, the 6808 seat and the tooth left out
"""
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
from dims import RS02_SCREWS, ROLL_OUT, RX, RY, SEAT_Y, YZ

Y0 = SEAT_Y[0]
import os
SEATH = float(os.environ.get('R2_SEAT_YH', '358.4'))      # Y of the screw seats: 359.9 with RS02_SEAT_FIX
ALLOW = (('vM', FS.YIELD), ('layer', FS.YIELD * FS.LAYER), ('shear', FS.YIELD * FS.LAYER / math.sqrt(3.0)))


def worst(pos, tree, v, mk, n=300):
    idx = np.flatnonzero(mk)
    if not len(idx):
        return None
    top = idx[np.argsort(v[idx])[-n:]]
    b = {r: np.array([v[tree.query_ball_point(pos[i], r)].mean() for i in top]) for r in (0.5, 1.0, 2.0)}
    w = top[int(np.argmax(b[0.5]))]
    return [b[r].max() for r in (0.5, 1.0, 2.0)], pos[w]


def post(case, tag):
    try:
        z = np.load(str(FS.F / f'{case}_{tag}.npz'))
    except FileNotFoundError:
        return
    pos, s = z['pos'], z['s']
    x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - YZ
    ry = np.hypot(x, zz)
    fork = ~((ry < 39.5) & (y < Y0 + 0.02)) & ~(np.abs(y - Y0) < 0.02)
    pos, s, x, y, zz, ry = pos[fork], s[fork], x[fork], y[fork], zz[fork], ry[fork]
    tree = cKDTree(pos)
    q = dict(vM=s[:, 10], layer=np.abs(s[:, 2]) if case.endswith('STOP') else np.maximum(s[:, 2], 0.0), shear=np.sqrt(s[:, 4] ** 2 + s[:, 6] ** 2))
    ring = (y > Y0) & (y < SEAT_Y[1] + 0.6) & (ry > 33.0) & (ry < 46.5)
    near = np.zeros(len(pos), bool)
    tie = np.zeros(len(pos), bool)
    for a in RS02_SCREWS:
        t = math.radians(a)
        dr = np.hypot(x - 36.5 * math.cos(t), zz - 36.5 * math.sin(t))
        near |= dr < 4.5
        tie |= (np.abs(dr - 1.8) < 1.2) & (np.abs(y - SEATH) < 1.2)
    rr = np.hypot(x, y - RY)
    rest = ~ring & ~((pos[:, 2] < ROLL_OUT + 4.0) & (rr < 23.0)) & ~((rr < 30.5) & (pos[:, 2] < -36.0)) & ~((pos[:, 2] < -28.0) & (rr > 24.0) & (rr < 46.0) & (y < RY - 18.0))
    print(f'== {case} {tag}: {len(pos)} fork nodes ({int((~fork).sum())} stand-in and seat-plane nodes left out). SF worst 0.5 / 1 / 2 mm ball')
    for nm, mk in (('seat ring, all', ring), ('  at the screws', ring & near), ('  at the screws, tie rings out', ring & near & ~tie), ('  between screws', ring & ~near), ('rest of the fork', rest)):
        row = []
        for k, al in ALLOW:
            w = worst(pos, tree, q[k], mk)
            if w is None:
                continue
            row.append('%s %.2f / %.2f / %.2f at (%+.0f, %.0f, %+.0f)' % (k, al / max(w[0][0], 1e-9), al / max(w[0][1], 1e-9), al / max(w[0][2], 1e-9), w[1][0] - RX, w[1][1], w[1][2] - YZ))
        print(f'  {nm:30s} ' + ' | '.join(row))


if __name__ == '__main__':
    for tag in sys.argv[1:] or ['p250']:
        for case in ('R2_MX', 'R2_MXn', 'R2_MZ', 'R2_STOP'):
            post(case, tag)
