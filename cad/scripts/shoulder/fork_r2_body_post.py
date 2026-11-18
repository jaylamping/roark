"""Read-out of the RS02-on-fork bolted cases by body: the fork's own nodes (the body that is not a stand-in or a washer,
from the `body` record in the result file), with nothing left out. Per screw, the lowest safety factors within 6 mm of
its axis (seat ring Y to 3 mm above the ring's top), worst 0.5 / 1 mm ball: layer tension (sigma_y, 22.5 MPa; the fork
prints Y up), shear across the layers (sqrt(txy^2 + tyz^2), 13.0 MPa, assumed), von Mises (45 MPa). For a stop case also
layer stress of either sign. Then the same for the rest of the fork, where only the 4 mm at the fixed boss face is out.

    python fork_r2_body_post.py CASE TAG [CASE TAG ...]
"""
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
from dims import ROLL_OUT, RS02_SCREWS, RX, RY, SEAT_Y, YZ


def post(case, tag):
    z = np.load(str(FS.F / f'{case}_{tag}.npz'), allow_pickle=False)
    if 'body' not in z:
        print(f'{case} {tag}: no body record in the result file')
        return
    names = [str(n) for n in z['body_names']]
    fork = [k for k, n in enumerate(names) if 'DUMMY' not in n.upper()]
    keep = np.isin(z['body'], fork)
    pos, s = z['pos'][keep], z['s'][keep]
    x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - YZ
    tree = cKDTree(pos)
    q = dict(layer=(np.maximum(s[:, 2], 0), 22.5), shear=(np.sqrt(s[:, 4] ** 2 + s[:, 6] ** 2), 13.0), vM=(s[:, 10], 45.0))
    if case.endswith('STOP'):
        q['layer, either sign'] = (np.abs(s[:, 2]), 22.5)

    def low(mk):
        idx = np.flatnonzero(mk)
        cell = []
        for k, (v, al) in q.items():
            top = idx[np.argsort(v[idx])[-300:]]
            b5 = max(v[tree.query_ball_point(pos[i], 0.5)].mean() for i in top)
            b1 = max(v[tree.query_ball_point(pos[i], 1.0)].mean() for i in top)
            cell.append('%s %.2f / %.2f' % (k, al / max(b5, 1e-9), al / max(b1, 1e-9)))
        return ', '.join(cell)

    print(f'== {case} {tag}: fork body {[names[k] for k in fork]}, {len(pos)} nodes of {len(keep)}; nothing left out. SF worst 0.5 / 1 mm ball')
    near = np.zeros(len(pos), bool)
    for a in RS02_SCREWS:
        t = math.radians(a)
        dr = np.hypot(x - 36.5 * math.cos(t), zz - 36.5 * math.sin(t))
        reg = (dr < 6.0) & (y > SEAT_Y[0]) & (y < SEAT_Y[1] + 3.0)
        near |= reg
        print('  screw at %5.0f deg: %s' % (a, low(reg)))
    rr = np.hypot(pos[:, 0] - RX, pos[:, 1] - RY)
    print('  rest of the fork   : %s' % low(~near & ~((pos[:, 2] < ROLL_OUT + 4.0) & (rr < 23.0))))


if __name__ == '__main__':
    a = sys.argv[1:]
    for i in range(0, len(a), 2):
        post(a[i], a[i + 1])
