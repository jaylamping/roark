"""Read-out of the six-screw joint cases (fea_shoulder.py J_* on forkj_real: the fork front and the fork rear as two
bodies, six preloaded M4, contact on the pad) with NOTHING left out, body by body, from the body record in the result
file. For each of the six screws: the lowest safety factors within 6 mm of its axis in the joint zone (Y 338 to 366,
within 14 mm of the joint plane), on the fork rear's side (counterbore and head seat) and on the fork front's side
(insert boss). Then the joint zone away from the screws, and the rest of each part (only the 4 mm at the fixed boss
face is out). Worst 0.5 / 1 mm ball: layer tension (sigma_y, 22.5 MPa; both parts print Y up), shear across the layers
(sqrt(txy^2 + tyz^2), 13.0 MPa, assumed), von Mises (45 MPa); for the stop case also layer stress of either sign.

    python joint_body_post.py CASE TAG [CASE TAG ...]        (TAG as run_joint.sh names the results, e.g. p400)
"""
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
from dims import JOINT_PTS, JZ0, ROLL_OUT, RX, RY


def post(case, tag):
    z = np.load(str(FS.F / f'{case}_{tag}.npz'))
    if 'body' not in z:
        print(f'{case} {tag}: no body record in the result file')
        return
    names = [str(n) for n in z['body_names']]
    pos_all, s_all, body = z['pos'], z['s'], z['body']
    front = max(range(len(names)), key=lambda k: pos_all[body == k][:, 2].max() if (body == k).any() else -1e9)      # the fork front reaches furthest forward
    print(f'== {case} {tag}: bodies {names}; fork front = {names[front]}; {len(pos_all)} nodes, nothing left out. SF worst 0.5 / 1 mm ball')
    for k, nm in enumerate(names):
        mk = body == k
        if not mk.any():
            continue
        pos, s = pos_all[mk], s_all[mk]
        tree = cKDTree(pos)
        q = dict(layer=(np.maximum(s[:, 2], 0), 22.5), shear=(np.sqrt(s[:, 4] ** 2 + s[:, 6] ** 2), 13.0), vM=(s[:, 10], 45.0))
        if 'STOP' in case:
            q['layer, either sign'] = (np.abs(s[:, 2]), 22.5)

        def low(m):
            idx = np.flatnonzero(m)
            if not len(idx):
                return '-'
            cell = []
            for kk, (v, al) in q.items():
                top = idx[np.argsort(v[idx])[-300:]]
                b5 = max(v[tree.query_ball_point(pos[i], 0.5)].mean() for i in top)
                b1 = max(v[tree.query_ball_point(pos[i], 1.0)].mean() for i in top)
                cell.append('%s %.2f / %.2f' % (kk, al / max(b5, 1e-9), al / max(b1, 1e-9)))
            return ', '.join(cell)

        zone = (pos[:, 1] > 338.0) & (pos[:, 1] < 366.0) & (np.abs(pos[:, 2] - JZ0) < 14.0) & (np.abs(pos[:, 0] - RX) < 36.0)
        near = np.zeros(len(pos), bool)
        side = 'fork front (insert bosses)' if k == front else 'fork rear (counterbores, head seats)'
        print(f'  {side}:')
        for dx, jy in JOINT_PTS:
            m = zone & (np.hypot(pos[:, 0] - (RX + dx), pos[:, 1] - jy) < 6.0)
            near |= m
            print('    screw at X %+5.1f Y %5.1f: %s' % (dx, jy, low(m)))
        print('    joint zone away from the screws: %s' % low(zone & ~near))
        rr = np.hypot(pos[:, 0] - RX, pos[:, 1] - RY)
        print('    rest of the part: %s' % low(~zone & ~((pos[:, 2] < ROLL_OUT + 4.0) & (pos[:, 2] > ROLL_OUT - 0.5) & (rr < 23.0))))


if __name__ == '__main__':
    a = sys.argv[1:]
    for i in range(0, len(a), 2):
        post(a[i], a[i + 1])
