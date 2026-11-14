"""Shell contacts at the inward roll stop (rev A shell parts in torso_frame.step and shell_inner.step, moved -38 X):
which pad or skin points come within 3 mm of the moving arm at roll -11 (pitch -30/0/+24/+90, yaw -90..+90 in 5 deg),
the trim depth that would give 3 mm, and a picture of each contact.

    python check_shell_trim.py OUTDIR
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from build_asm import FRAME_SHIFT, pose_matrix
from check_clearance import named_solids, tess, samp, mesh_step, xf, UA, STL
from dims import *

OUT = Path(sys.argv[1])
CLEAR = 3.0
mov = {'upper_arm': np.vstack([samp(mesh_step(UA / f'upper_arm_organic_{n}_left.step', tol=0.3), 0.8) for n in ('front', 'back', 'rs02_ring')]),
       'hub': samp(trimesh.load(STL / 'hub.stl'), 0.7), 'fork_front': samp(trimesh.load(STL / 'fork_front.stl'), 0.7),
       'fork_rear': samp(trimesh.load(STL / 'fork_rear.stl'), 0.7)}
grp = dict(upper_arm='yaw', hub='yaw', fork_front='roll', fork_rear='roll')
tgt = {}
for nm, sh in named_solids(r'J:/code/_transfer/shoulder/torso_frame.step'):
    if nm.startswith('shellpart__spine'):
        m = tess(sh, 0.3); m.apply_translation((-FRAME_SHIFT, 0, 0)); tgt[nm.split('__')[1]] = m
import cadquery as cq
sm = trimesh.util.concatenate([tess(f, 0.4) for f in cq.importers.importStep(r'J:/code/_transfer/shoulder/shell_inner.step').faces().vals()])
sm.apply_translation((-FRAME_SHIFT, 0, 0))
c = sm.triangles_center
sm.update_faces((c[:, 0] > 20) & (c[:, 1] > 200) & (c[:, 1] < 520)); sm.remove_unreferenced_vertices()
tgt['shell_skin'] = sm
res = {}
for tn, m in tgt.items():
    P = samp(m, 0.6)
    if tn == 'shell_skin':        # ignore the shoulder opening region (r 80 round the pitch axis outboard of old X 75)
        r = np.hypot(P[:, 1] - RY, P[:, 2] - PZ); P = P[~((P[:, 0] > 75) & (r < 80))]
    tree = cKDTree(P)
    need = np.full(len(P), 0.0)
    worst = (99.0, None)
    for pitch in (-30.0, 0.0, 24.0, 90.0):
        for yaw in range(-90, 91, 5):
            for k, pts in mov.items():
                q = xf(pts, pose_matrix(grp[k], pitch, ROLL_STOP_IN, float(yaw)))
                dd, ii = cKDTree(q).query(P, distance_upper_bound=CLEAR + 0.5, workers=-1)
                ok = np.isfinite(dd)
                need[ok] = np.maximum(need[ok], CLEAR - dd[ok])
                if ok.any() and dd[ok].min() < worst[0]:
                    worst = (float(dd[ok].min()), (pitch, yaw, k))
    sel = need > 0
    if sel.any():
        bb = np.r_[P[sel].min(0), P[sel].max(0)] + np.r_[FRAME_SHIFT, 0, 0, FRAME_SHIFT, 0, 0]
        res[tn] = dict(min_dist_at_stop=round(worst[0], 2), worst_pose_pitch_yaw_part=worst[1], trim_depth_max=round(float(need.max()), 2),
                       trim_region_reva=[round(float(v), 1) for v in bb], points=int(sel.sum()))
    else:
        res[tn] = dict(min_dist_at_stop=round(worst[0], 2) if worst[1] else '>3.5', trim_depth_max=0.0)
    print(tn, res[tn], flush=True)
(OUT / 'shell_trim.json').write_text(json.dumps(res, indent=1))
