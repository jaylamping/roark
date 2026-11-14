"""Hub-top read-out for the bolted-contact cases (HUBB_*): per region, layer tension (sigma_y against 22.5 MPa), shear
across the layers (sqrt(txy^2 + tyz^2) against 13.0 MPa, assumed) and von Mises (45 MPa), as safety factors at the peak
node and for the worst 0.5 and 1 mm balls among the region's 300 highest nodes. Hub nodes only (the dummy disc above
Y 319.86 is left out).

    python hub_top_post.py NPZ [NPZ ...]        (names in cad/_sim/shoulder, without the extension)

Regions: the whole hub; the hub top (Y 311.5 and up); round the cable window at 68 deg (within 7 mm of the slot's line,
Y 302 and up); the boss tubes at 38 and 98 deg (within 4.6 mm of each tube's axis); the two close-fit locating holes
(-142 and 38 deg, within 2.7 mm of the axis); the wall under the groove (Y 298.6-300.8); the two lugs.
"""
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS

RX, YZ = FS.RX, FS.YZ
L, B = FS.YIELD * FS.LAYER, FS.YIELD
T = L / math.sqrt(3.0)


def regions(pos):
    x, y, z = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - YZ
    r = np.hypot(x, z)

    def tube(a, rad):
        t = math.radians(a)
        return (np.hypot(x - 12.0 * math.cos(t), z - 12.0 * math.sin(t)) <= rad) & (y >= 298.0)

    t68 = math.radians(68.0)
    across = np.abs(-x * math.sin(t68) + z * math.cos(t68))            # distance from the window's radial plane
    along = x * math.cos(t68) + z * math.sin(t68)
    return {
        'whole hub': np.ones(len(pos), bool),
        'hub top (Y 311.5 up)': y >= 311.5,
        'round the window at 68 deg': (across <= 7.0) & (along >= 13.0) & (y >= 302.0),
        'boss tube at 38 deg': tube(38.0, 4.6),
        'boss tube at 98 deg': tube(98.0, 4.6),
        'locating hole at 38 deg': tube(38.0, 2.7),
        'locating hole at -142 deg': tube(-142.0, 2.7),
        'wall under the groove': (y >= 298.6) & (y <= 300.8) & (r >= 30.0),
        '-X lug': (x < -17.0) & (y < 297.0),
        '+X lug': (x > 17.0) & (y < 297.0),
    }


def post(name):
    z = np.load(str(FS.F / f'{name}.npz'))
    pos, s = z['pos'], z['s']
    keep = pos[:, 1] <= 319.87
    pos, s = pos[keep], s[keep]
    tree = cKDTree(pos)
    q = dict(layer=(np.maximum(s[:, 2], 0.0), L), shear=(np.sqrt(s[:, 4] ** 2 + s[:, 6] ** 2), T), vM=(s[:, 10], B))
    print(f'== {name}: {len(pos)} hub nodes. SF peak / 0.5 mm / 1 mm (worst ball), and where the 0.5 mm ball is (X offset, Y, Z offset)')
    for nm, mk in regions(pos).items():
        if not mk.any():
            continue
        out = []
        for k, (v, al) in q.items():
            idx = np.flatnonzero(mk)
            top = idx[np.argsort(v[idx])[-300:]]
            b05 = np.array([v[tree.query_ball_point(pos[i], 0.5)].mean() for i in top])
            b10 = np.array([v[tree.query_ball_point(pos[i], 1.0)].mean() for i in top])
            w = top[int(np.argmax(b05))]
            out.append(f'{k} {al / max(v[top].max(), 1e-9):5.2f} / {al / max(b05.max(), 1e-9):5.2f} / {al / max(b10.max(), 1e-9):5.2f} at ({pos[w][0] - RX:+.1f}, {pos[w][1]:.1f}, {pos[w][2] - YZ:+.1f})')
        print(f'  {nm:28s} ' + ' | '.join(out))


if __name__ == '__main__':
    for n in sys.argv[1:]:
        post(n)
