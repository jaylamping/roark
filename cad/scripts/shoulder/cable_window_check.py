"""Arm bundle through the hub's cable window (dims.HUB_WIN_A) and the dish loop under the RS02, over the yaw travel.

    python cable_window_check.py [out.json]

1. The bundle inside the hub (yaw group): a flat band following the window slot's centre line (build_parts HUB_WIN: r 15.5,
   Y 298 to r 31, dish floor + 2), then straight down the bore at r 17. Two sizes: the arm bundle 3.5 x 13 and the passage
   envelope 6 x 16. Distance to the hub (and whether any of it is inside the hub), to the arm's r1g4 parts
   (left-arm-organic, read-only) and, over yaw -90..+90 and roll -11 / 0 / 45 / 110, to the RS02 (build_asm.T_RS02, so
   with its +40 deg clock), the fork front, the fork rear and the drum.
2. The dish loop: where the fork rear's yaw exit meets the annulus, where the window is at each yaw, and the arc between
   them. The loop lies flat in the annulus under the RS02 (dish floor to the RS02's underside), so it cannot cross itself.
"""
import json
import math
import os
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from build_asm import T_RS02, pose_matrix
from check_clearance import mesh_step, samp, xf
from dims import *
from swk import VENDOR, WIP

ARM = r'J:/code/roark-wt/left-arm-organic/cad/_wip/r1d_r1g_print/'
P1, P0 = np.array([15.5, 298.0]), np.array([31.0, DISH_Y + 2.0])      # slot centre line in (r, Y): bore end, dish end
U = (P0 - P1) / np.linalg.norm(P0 - P1)


def centre_line(n=160):
    """(r, Y) points: straight drop at r 17 from Y 250, a bend into the slot's line, the slot to 2 mm short of its dish end."""
    pts = [np.array([17.0, y]) for y in np.linspace(250.0, 292.0, 60)]
    a, b, c = np.array([17.0, 292.0]), np.array([17.0, 297.5]), P1 + U * 1.0
    pts += [a * (1 - t) ** 2 + 2 * (1 - t) * t * b + t ** 2 * c for t in np.linspace(0, 1, 30)[1:]]
    pts += [c + (P0 - U * 2.0 - c) * t for t in np.linspace(0, 1, n)[1:]]
    return np.array(pts)


def band(th_deg, thick, width, step=0.4):
    """Surface samples of the band in the hub's frame at yaw 0: thick in the radial plane, width across it."""
    cl = centre_line()
    t = np.gradient(cl, axis=0); t /= np.linalg.norm(t, axis=1)[:, None]
    nrm = np.c_[-t[:, 1], t[:, 0]]
    a = math.radians(th_deg)
    er, et = np.array([math.cos(a), 0.0, math.sin(a)]), np.array([-math.sin(a), 0.0, math.cos(a)])
    out = []
    ws = np.arange(-width / 2, width / 2 + 1e-6, step)
    ts = np.arange(-thick / 2, thick / 2 + 1e-6, step)
    for (r, y), n_ in zip(cl, nrm):
        for w in ws:
            for s in (-thick / 2, thick / 2):
                rr, yy = r + n_[0] * s, y + n_[1] * s
                out.append(np.array([RX, 0.0, YZ]) + er * rr + et * w + np.array([0.0, yy, 0.0]))
        for s in ts:
            for w in (-width / 2, width / 2):
                rr, yy = r + n_[0] * s, y + n_[1] * s
                out.append(np.array([RX, 0.0, YZ]) + er * rr + et * w + np.array([0.0, yy, 0.0]))
    return np.array(out)


def main():
    res = dict(window_deg=HUB_WIN_A)
    hub = trimesh.load(WIP / os.environ.get('HUB_STL', 'stl/hub.STL'))       # HUB_STL: another hub (with HUB_WIN_A) for a baseline
    arm = trimesh.util.concatenate([trimesh.load(ARM + f) for f in ('upper_arm_organic_front_left.STL', 'upper_arm_organic_back_left.STL',
                                                                    'checks/lug_plates_045_r1g4.STL')])
    arm_tree = cKDTree(samp(arm, 0.6))
    rs02 = mesh_step(VENDOR / 'vendor_robstride_rs02.step', T_RS02)
    p = samp(rs02, 0.6)
    rr = np.hypot(p[:, 0] - RX, p[:, 2] - YZ)
    rotor = (rr < 21.8) & (p[:, 1] < 323.5)
    trees = dict(rs02_stator=(cKDTree(p[~rotor]), 'roll'), rs02_rotor=(cKDTree(p[rotor]), 'yaw'))
    for k, f in (('fork_front', 'fork_front.stl'), ('fork_rear', 'fork_rear.STL'), ('drum', 'drum.STL')):
        trees[k] = (cKDTree(samp(trimesh.load(WIP / 'stl' / f), 0.6)), 'pitch' if k == 'drum' else 'roll')
    for nm, (th, w) in (('arm bundle 3.5 x 13', (3.5, 13.0)), ('passage envelope 6 x 16', (6.0, 16.0))):
        b = band(HUB_WIN_A, th, w)
        # exact closest point on the hub, chunked (light); inside = behind the closest face (normal side test)
        cp = [trimesh.proximity.closest_point(hub, b[s:s + 4000]) for s in range(0, len(b), 4000)]
        c_, d, tri = np.vstack([o[0] for o in cp]), np.concatenate([o[1] for o in cp]), np.concatenate([o[2] for o in cp])
        ins = np.einsum('ij,ij->i', b - c_, hub.face_normals[tri]) < -0.01
        i = int(np.argmin(d))
        r_ = dict(samples=len(b), hub_min=round(float(d.min()), 2), hub_min_at=[round(float(b[i, 0] - RX), 2), round(float(b[i, 1]), 2), round(float(b[i, 2] - YZ), 2)],
                  inside_hub=int(ins.sum()))
        if ins.any():
            q = b[ins]
            r_['inside_hub_Y'] = [round(float(q[:, 1].min()), 2), round(float(q[:, 1].max()), 2)]
            r_['inside_hub_depth_max'] = round(float(d[ins].max()), 2)
        da, _ = arm_tree.query(b)
        r_['arm_min'] = round(float(da.min()), 2)
        mov = {}
        for k, (tree, grp) in trees.items():
            best = (99.0, None)
            for roll in (ROLL_STOP_IN, 0.0, 45.0, ROLL_STOP_OUT):
                for yaw in range(-90, 91, 5):
                    M = np.linalg.inv(pose_matrix(grp, 0.0, roll, float(yaw))) @ pose_matrix('yaw', 0.0, roll, float(yaw))
                    dd, _ = tree.query(xf(b[::3], M), distance_upper_bound=40)
                    m_ = float(dd.min())
                    if m_ < best[0]:
                        best = (m_, (roll, yaw))
                if grp != 'pitch':
                    break            # roll moves only the drum against the bundle
            mov[k] = dict(min=round(best[0], 2), at_roll_yaw=best[1])
        r_['moving'] = mov
        res[nm] = r_
        print(nm, json.dumps(r_), flush=True)
    # ---- the dish loop
    ex = RX + P_OFF + CH_DX - RX, (YZ - 37.0) - YZ       # exit channel centre where it meets the annulus (X - RX, Z - YZ)
    a_ex = math.degrees(math.atan2(ex[1], ex[0])) % 360
    loop = dict(exit_deg=round(a_ex, 1), exit_xz=[round(ex[0], 2), round(ex[1], 2)], annulus_r=[DISH_R0 + DISH_FILLET, 38.5],
                annulus_axial=round(RS02_UNDER - DISH_Y, 2), rows=[])
    # Ry(yaw) turns a point at angle a (atan2(z, x)) to a - yaw
    for yaw in range(-90, 91, 15):
        w = (HUB_WIN_A - yaw) % 360
        cw = (a_ex - w) % 360          # arc from the window up to the exit, angle increasing
        loop['rows'].append(dict(yaw=yaw, window_deg=round(w, 1), arc_inc=round(cw, 1), arc_dec=round(360 - cw, 1),
                                 len_inc_r31=round(math.radians(cw) * 31.0, 1), len_dec_r31=round(math.radians(360 - cw) * 31.0, 1)))
    inc = [r['arc_inc'] for r in loop['rows']]
    # one-way loop: the same direction over the whole travel, without the window passing under the exit
    d_ = np.diff(inc)
    loop['window_passes_exit'] = bool((np.abs(d_) > 180).any())
    if loop['window_passes_exit']:
        loop['passes_at_yaw'] = round(float((HUB_WIN_A - a_ex + 180) % 360 - 180), 1)
    res['loop'] = loop
    print(json.dumps(loop, indent=1))
    out = sys.argv[1] if len(sys.argv) > 1 else str(WIP / 'cable_window_check.json')
    open(out, 'w').write(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
