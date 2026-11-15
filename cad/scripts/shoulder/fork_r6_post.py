"""Read-out of the 6808-seat cases with a stand-in outer race (fea_shoulder.py R6_*; OPEN_ASSUMPTIONS item 49). The fork's
nodes only: the race is the ring r 23.0 to R6_RO about the roll axis between the bearing's two faces, where the fork has
no material, so its nodes are told apart by position (everything inside r R6_RO + 0.03 in that Z range is left out).

    python fork_r6_post.py TAG [TAG ...]        (TAG as run_r2.sh names the results: sf5, real)

Safety factors, worst 0.5 / 1 / 2 mm ball: von Mises (45 MPa), layer tension (sigma_y, 22.5 MPa; the fork prints Y up),
shear across the layers (sqrt(txy^2 + tyz^2), 13.0 MPa, assumed). Nothing else is left out. Regions:
  bearing seat      fork nodes within 4 mm of the housing's bore (r up to 30.1), Z from the lip to 1.5 in front of the bearing
  lip               the outer-race lip behind the bearing (r 24.0 to 26.1, Z behind the bearing's rear face)
  rest of the fork  everything else but the boss face's band (within 4 mm of the fixed face) and the RS02 seat ring
"""
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
from dims import BRG_LIP_Z, BRG_SEAT_R, BRG_Z, ROLL_OUT, RX, RY, SEAT_Y, YZ

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
    rr = np.hypot(pos[:, 0] - RX, pos[:, 1] - RY)
    race = (rr < FS.R6_RO + 0.03) & (pos[:, 2] < BRG_Z[0] + 0.03) & (pos[:, 2] > BRG_Z[1] - 0.03)
    pos, s, rr = pos[~race], s[~race], rr[~race]
    zz = pos[:, 2]
    tree = cKDTree(pos)
    q = dict(vM=s[:, 10], layer=np.maximum(s[:, 2], 0.0), shear=np.sqrt(s[:, 4] ** 2 + s[:, 6] ** 2))
    if case.endswith('STOP'):
        q['layer, either sign'] = np.abs(s[:, 2])
    seat = (rr < BRG_SEAT_R + 4.0) & (zz > BRG_LIP_Z - 3.0) & (zz < BRG_Z[0] + 1.5)
    lip = seat & (rr < BRG_SEAT_R + 0.05) & (zz < BRG_Z[1] + 0.05)
    ry = np.hypot(pos[:, 0] - RX, pos[:, 2] - YZ)
    ring = (pos[:, 1] > SEAT_Y[0]) & (pos[:, 1] < SEAT_Y[1] + 3.0) & (ry > 33.0) & (ry < 46.5)
    rest = ~seat & ~ring & ~((zz < ROLL_OUT + 4.0) & (rr < 23.0))
    print(f'== {case} {tag}: {len(pos)} fork nodes ({int(race.sum())} race nodes left out). SF worst 0.5 / 1 / 2 mm ball, and where (X and Y from the roll axis, Z)')
    al = dict(ALLOW)
    al['layer, either sign'] = al['layer']
    for nm, mk in (('bearing seat', seat), ('  lip behind the bearing', lip), ('rest of the fork', rest)):
        row = []
        for k, v in q.items():
            w = worst(pos, tree, v, mk)
            if w is None:
                continue
            row.append('%s %.2f / %.2f / %.2f at (%+.0f, %+.0f, %.0f)' % (k, al[k] / max(w[0][0], 1e-9), al[k] / max(w[0][1], 1e-9), al[k] / max(w[0][2], 1e-9), w[1][0] - RX, w[1][1] - RY, w[1][2]))
        print(f'  {nm:26s} ' + ' | '.join(row))


if __name__ == '__main__':
    for tag in sys.argv[1:] or ['sf5']:
        for case in ('R6_STOP', 'R6_MX', 'R6_MXn', 'R6_MZ'):
            post(case, tag)
