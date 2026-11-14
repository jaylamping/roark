"""Left shoulder against the rev A torso frame and the chest shell (first CAD pass).

    python check_reva.py FRAME_STEP SHELL_STEP

FRAME_STEP: torso_frame.step (rev A, its own coordinates: old-frame shoulder X + 38). SHELL_STEP: shell_inner.step (same
coordinates, whole chest, no shoulder opening cut). Both are moved by -38 in X into the old-frame coordinates of the parts.
Same method as check_clearance.py (surface samples, KD-trees, +-0.4 mm; contact = under 0.5 mm).

(g) inward roll 0..-25 deg (1 deg) at yaw -90..+90 (15 deg) and pitch -30/0/+24/+90: first contact angle and what it touches,
    against the frame, the frame with the 6 mm PETG gusset stand-ins (gussets 3 mm further out in Z), and the shell
    (shell points inside the r 60 collar opening round the pitch axis ignored; also given with r 80 ignored).
(h) feed placement against the frame and shell. (i) the cover and flange ring against the shell skin.
Writes cad/_wip/shoulder-pass1/reva.json.
"""
import json
import os
import sys
import time

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from build_asm import FRAME_SHIFT, pose_matrix
from check_clearance import load, samp, xf, GROUP, named_solids, tess
from dims import *
from swk import WIP

FRAME, SHELL = sys.argv[1], sys.argv[2]
CONTACT = 0.5


def main():
    t0 = time.time()
    P = load()
    shift = np.array([-FRAME_SHIFT, 0, 0])
    fr, gus, names, other = [], [], [], {}
    for nm, sh in named_solids(FRAME):
        bb = sh.BoundingBox()
        if bb.xmax < 60 or bb.ymax < 250:         # far side and low frame: nothing of the left arm reaches there
            continue
        grp = nm.split('__')[0]
        m = tess(sh)
        if m.area <= 0:
            continue
        p = samp(m, 1.0) + shift
        if grp in ('actuator',):                   # the pitch RS03 envelope: the real motor is in the model
            continue
        if grp == 'shellpart' or nm.startswith('fastener__c1_'):   # the shell collar and its screws
            other[nm] = p
            continue
        fr.append(p); names += [nm] * len(p)
        if grp == 'gusset':
            # 6 mm PETG stand-ins: 3 mm further out in Z than the 3 mm aluminium plate
            sz = np.sign(p[:, 2])
            gus += [p + np.c_[np.zeros(len(p)), np.zeros(len(p)), sz * k] for k in (1.0, 2.0, 3.0)]
    FR = np.vstack(fr); FRN = np.array(names)
    FRG = np.vstack([FR] + gus) if gus else FR
    FRGN = np.r_[FRN, np.repeat('gusset PETG allowance', sum(len(g) for g in gus))]
    import cadquery as cq
    sh = cq.importers.importStep(SHELL)
    sm = trimesh.util.concatenate([tess(f, 0.5) for f in sh.faces().vals()])
    sm.apply_translation(shift)
    SP = samp(sm, 1.0)
    rp = np.hypot(SP[:, 1] - RY, SP[:, 2] - PZ)
    near_open = SP[:, 0] > 75.0                        # the shoulder side of the shell (old X > 75 = rev A X > 113)
    SH60, SH80 = SP[~(near_open & (rp < 60))], SP[~(near_open & (rp < 80))]
    print('targets', len(FR), len(FRG), len(SH60), round(time.time() - t0), 's', flush=True)
    T = dict(frame=(cKDTree(FR), FRN), frame_petg=(cKDTree(FRG), FRGN), shell_open60=(cKDTree(SH60), None), shell_open80=(cKDTree(SH80), None))
    col = [p for nm, p in other.items() if 'collar' in nm or nm.startswith('fastener__c1_')]
    if col:
        T['shell_collar_and_screws'] = (cKDTree(np.vstack(col)), None)
    for nm, p in other.items():
        if 'spine' in nm:
            T['shellpart:' + nm.split('__')[1]] = (cKDTree(p), None)

    movers = [k for k in P if GROUP[k] in ('pitch', 'roll', 'yaw') and k != 'stops'] + (['stops'] if len(P.get('stops', [])) else [])
    res = {}
    for pitch in [float(v) for v in os.environ.get('PITCHES', '-30,0,24,90').split(',')]:
        for tname, (tree, tn) in T.items():
            first = None
            at11 = None
            curve = {}
            for roll in range(0, -26, -1):
                best = (99.0, None, None, None)
                for yaw in range(-90, 91, 15):
                    for k in movers:
                        M = pose_matrix(GROUP[k], pitch, float(roll), float(yaw))
                        q = xf(P[k][::2], M)
                        dd, ii = tree.query(q, distance_upper_bound=60, workers=2)
                        j = int(np.argmin(dd))
                        if dd[j] < best[0]:
                            best = (float(dd[j]), k, (tn[ii[j]] if tn is not None and np.isfinite(dd[j]) else tname), yaw)
                curve[roll] = round(best[0], 2)
                if roll == -11:
                    at11 = dict(min=round(best[0], 2), part=best[1], touches=best[2], yaw=best[3])
                if first is None and best[0] < CONTACT:
                    first = dict(roll=roll, part=best[1], touches=best[2], yaw=best[3], dist=round(best[0], 2))
            res[f'pitch {pitch:+.0f} | {tname}'] = dict(first_contact=first, at_roll_minus11=at11, min_by_roll=curve)
            print(f'pitch {pitch:+4.0f} {tname:28s} first {first}  at -11 {at11}', flush=True)
    # (h) the feed against the frame and the shell (the cover is fixed: neutral pose)
    cov = P['cover']
    feed = cov[(cov[:, 1] < RY - COVER['out'][1] + 0.5)]
    hres = {}
    for tname in ('frame', 'frame_petg', 'shell_open60'):
        dd, ii = T[tname][0].query(feed, workers=2)
        j = int(np.argmin(dd))
        hres[tname] = dict(min=round(float(dd[j]), 2), at_reva=[round(float(v), 1) for v in feed[j] - shift], touches=(T[tname][1][ii[j]] if T[tname][1] is not None else tname))
    hres['feed_box_reva'] = [round(float(v), 1) for v in np.r_[feed.min(0) - shift, feed.max(0) - shift]]
    # (i) the cover and ring against the shell skin: ray along +X from the torso centre plane at each (Y, Z)
    ray = trimesh.ray.ray_triangle.RayMeshIntersector(sm)

    def shell_x(pts):
        o = np.c_[np.full(len(pts), -FRAME_SHIFT), pts[:, 1], pts[:, 2]]
        loc, idx, _ = ray.intersects_location(o, np.tile([1.0, 0, 0], (len(pts), 1)), multiple_hits=True)
        xs = np.full(len(pts), np.nan)
        for (x, y, z), i in zip(loc, idx):
            if x > 0 and (np.isnan(xs[i]) or x > xs[i]):
                xs[i] = x
        return xs
    ires = {}
    for k in ('cover', 'ring'):
        pts = P[k][::4]
        xs = shell_x(pts)
        inside = pts[:, 0] < xs
        ires[k] = dict(r_max=round(float(np.hypot(P[k][:, 1] - RY, P[k][:, 2] - PZ).max()), 2), share_inside_shell=round(float(np.nanmean(inside)), 3),
                       x_reva=[round(float(P[k][:, 0].min() + FRAME_SHIFT), 1), round(float(P[k][:, 0].max() + FRAME_SHIFT), 1)])
    band = np.array([(x, y, z) for y in range(360, 461, 10) for z in range(-40, 41, 20) for x in (0.0,)], float)
    xs = shell_x(band)
    ires['shell_inner_side_x_reva_y360_460'] = [round(float(np.nanmin(xs) + FRAME_SHIFT), 1), round(float(np.nanmax(xs) + FRAME_SHIFT), 1)]
    rr = max(ires['cover']['r_max'], ires['ring']['r_max'])
    ires['opening_radius_needed'] = round(rr + 2.0, 1)
    # where the shell skin cuts through the cover ring round the pitch axis: shell X at r 56-78, all angles
    ang = np.radians(np.arange(0, 360, 10))
    ring_pts = np.array([(0.0, RY + r * np.cos(a), PZ + r * np.sin(a)) for r in (56.0, 66.0, 76.0) for a in ang])
    xs = shell_x(ring_pts)
    ires['shell_x_reva_at_cover_radii'] = dict(min=round(float(np.nanmin(xs) + FRAME_SHIFT), 1), max=round(float(np.nanmax(xs) + FRAME_SHIFT), 1))
    out = dict(method='surface samples 1.0 mm (frame, shell) / 0.7 mm (parts), KD-tree, +-0.4 mm, contact < 0.5 mm; frame and shell moved -38 X',
               roll_inward=res, feed=hres, shell_opening=ires,
               shellparts_in_frame_model=list(other))
    (WIP / 'reva.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(feed=hres, shell=ires), indent=1))


if __name__ == '__main__':
    main()
