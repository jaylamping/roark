"""Read-out at the six screw holes on the hub's seat side (bolted hub-top cases): hub nodes within 3.4 mm of a screw axis
and within 3 mm below the seat face, WITHOUT the nodes on the seat plane (the aluminium dummy's bottom face shares that
plane and the result file does not say which body a node belongs to). Worst 0.5 / 1 / 2 mm ball for layer tension,
shear across the layers and von Mises, the worst hole, and how deep the zone under a safety factor of 1 reaches.

    HUB_TOP_RAISE=3.0 python hub_hole_post.py NPZ [NPZ ...]
"""
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS

RX, YZ, TOP = FS.RX, FS.YZ, FS.RS02_OUT
ALLOW = dict(layer=FS.YIELD * FS.LAYER, shear=FS.YIELD * FS.LAYER / math.sqrt(3.0), vM=FS.YIELD)


def post(name):
    z = np.load(str(FS.F / f'{name}.npz'))
    pos, s = z['pos'], z['s']
    keep = pos[:, 1] < TOP - 0.02
    pos, s = pos[keep], s[keep]
    x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - YZ
    tree = cKDTree(pos)
    q = dict(layer=np.maximum(s[:, 2], 0.0), shear=np.sqrt(s[:, 4] ** 2 + s[:, 6] ** 2), vM=s[:, 10])
    print(f'== {name}: SF at the screw holes below the seat face, worst 0.5 / 1 / 2 mm ball; compression across the layers at the worst shear spot')
    worst = {}
    for a in (-142.0, -82.0, -22.0, 38.0, 98.0, 158.0):
        t = math.radians(a)
        dr = np.hypot(x - 12.0 * math.cos(t), zz - 12.0 * math.sin(t))
        idx = np.flatnonzero((dr < 3.4) & (y > TOP - 3.0))
        row = []
        for k, v in q.items():
            top = idx[np.argsort(v[idx])[-150:]]
            b = {r: np.array([v[tree.query_ball_point(pos[i], r)].mean() for i in top]) for r in (0.5, 1.0, 2.0)}
            w = top[int(np.argmax(b[0.5]))]
            sf = tuple(ALLOW[k] / max(b[r].max(), 1e-9) for r in (0.5, 1.0, 2.0))
            row.append((k, sf, dr[w], TOP - y[w], s[w, 2]))
            if k not in worst or sf[0] < worst[k][0][0]:
                worst[k] = (sf, a, dr[w], TOP - y[w], s[w, 2])
        print('  hole %4.0f: ' % a + ' | '.join('%s %.2f / %.2f / %.2f' % ((k,) + sf) for k, sf, *_ in row))
    for k, (sf, a, d_, dep, sy) in worst.items():
        print('  WORST %-5s %.2f / %.2f / %.2f at the %.0f deg hole, %.2f mm from its axis, %.2f mm below the face; stress across the layers there %+.0f MPa (negative = squeezed)' % (k, sf[0], sf[1], sf[2], a, d_, dep, sy))
    # depth of the zone whose 0.5 mm ball is under SF 1 in shear
    v = q['shear']
    allz = np.flatnonzero(y > TOP - 6.0)
    hot = [i for i in allz[np.argsort(v[allz])[-400:]] if v[tree.query_ball_point(pos[i], 0.5)].mean() > ALLOW['shear']]
    if hot:
        print('  zone under 1 in shear (0.5 mm ball): %d nodes, down to %.2f mm below the face' % (len(hot), max(TOP - y[i] for i in hot)))
    else:
        print('  no node whose 0.5 mm ball is under 1 in shear')


if __name__ == '__main__':
    for n in sys.argv[1:]:
        post(n)
