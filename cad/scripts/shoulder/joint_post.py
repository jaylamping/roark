"""Read-out of the six-screw joint check (fea_shoulder.py J_* cases on forkj_real: the fork front and fork rear as two
bodies, six preloaded bolt connectors, contact on the pad). OPEN_ASSUMPTIONS item 41.

    python joint_post.py TAG [TAG ...]        (TAG as run_joint.sh names the results: p400, p200)

Safety factors on von Mises (45 MPa) and layer tension (sigma_y against 22.5 MPa; both parts print Y up), peak node /
worst 0.5 mm ball, in the joint zone (Y 338-366, within 14 mm of the joint plane Z = JZ0):
  all             every node of the zone
  away from bolts the same without the nodes within 2.0 mm of a screw's head-seat edge or of its insert bore's wall
                  (where the bolt connector ties in: a rigid tie on a ring of nodes, which makes its own peak)
  fork front side Z >= JZ0 (pad, insert bosses);  fork rear side Z < JZ0 (pad, counterbores)
and for the rest of the fork the regions of ff_proper_post.py, to compare with the merged model.
"""
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
import ff_proper_post as P
from dims import JOINT_FLOOR, JOINT_PTS, RX

JZ0 = FS.JZ0
L, B = P.L, P.B


def near_bolts(pos, d=2.0):
    m = np.zeros(len(pos), bool)
    for dx, jy in JOINT_PTS:
        zf = JZ0 - (5.5 if abs(dx) < 20 else JOINT_FLOOR)
        r = np.hypot(pos[:, 0] - (RX + dx), pos[:, 1] - jy)
        m |= (np.abs(pos[:, 2] - zf) < d) & (np.abs(r - 2.25) < d + 1.6)            # head seat: the hole edge and the button head's ring
        m |= (pos[:, 2] > JZ0 - 0.2) & (pos[:, 2] < JZ0 + 12.7) & (r < 2.8 + d)     # insert bore wall
    return m


def main(tags):
    for case in ('J_PRE0', 'J_MX', 'J_MXn', 'J_MZ', 'J_STOP17'):
        print('==', case)
        for tag in tags:
            try:
                z = np.load(str(FS.F / f'{case}_{tag}.npz'))
            except FileNotFoundError:
                continue
            pos, s = z['pos'], z['s']
            tree = cKDTree(pos)
            vm = s[:, 10]
            ly = np.abs(s[:, 2]) if case == 'J_STOP17' else np.maximum(s[:, 2], 0.0)
            zone = (pos[:, 1] > 338.0) & (pos[:, 1] < 366.0) & (np.abs(pos[:, 2] - JZ0) < 14.0) & (np.abs(pos[:, 0] - RX) < 40.0)
            nb = near_bolts(pos)
            print(f'  {tag}: {len(pos)} nodes; joint zone {int(zone.sum())}, of them near a bolt tie {int((zone & nb).sum())}')
            for nm, mk in (('joint zone, all', zone), ('  away from bolts', zone & ~nb), ('  fork front side', zone & ~nb & (pos[:, 2] >= JZ0)), ('  fork rear side', zone & ~nb & (pos[:, 2] < JZ0))):
                a, b = P.worst(pos, tree, vm, mk), P.worst(pos, tree, ly, mk)
                print(f'     {nm:18s} vM {B / a[0]:6.2f} / {B / a[1]:6.2f} at {a[2]} | layer {L / max(b[0], 1e-9):6.2f} / {L / max(b[1], 1e-9):6.2f} at {b[2]}')
            for nm, mk in P.regions(pos, True).items():
                keep = mk & ~zone
                rr = np.hypot(pos[:, 0] - RX, pos[:, 1] - FS.RY)
                keep &= ~((pos[:, 2] < FS.ROLL_OUT + 4.0) & (rr < 23.0)) & ~((rr < 30.5) & (pos[:, 2] < -36.0))
                if case != 'J_STOP17':
                    ry = np.hypot(pos[:, 0] - RX, pos[:, 2] - FS.YZ)
                    keep &= ~((np.abs(pos[:, 1] - FS.SEAT_Y[0]) < 4.0) & (ry < 46.0)) & ~((pos[:, 1] > FS.SEAT_Y[0] - 6.0) & (pos[:, 1] < FS.SEAT_Y[1] + 4.0) & (np.abs(ry - 36.5) < 5.5))
                else:
                    keep &= ~((pos[:, 2] < -28.0) & (rr > 24.0) & (rr < 46.0) & (pos[:, 1] < FS.RY - 18.0))
                a, b = P.worst(pos, tree, vm, keep), P.worst(pos, tree, ly, keep)
                if a:
                    print(f'     {nm:18s} vM {B / a[0]:6.2f} / {B / a[1]:6.2f} at {a[2]} | layer {L / max(b[0], 1e-9):6.2f} / {L / max(b[1], 1e-9):6.2f} at {b[2]}')


if __name__ == '__main__':
    main(sys.argv[1:] or ['p400'])
