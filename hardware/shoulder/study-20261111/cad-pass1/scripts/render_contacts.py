"""Pictures of the two shell contacts found by the rev A roll sweep (shell parts and skin from torso_frame.step and
shell_inner.step, moved -38 X; the arm posed by build_asm.pose_matrix). python render_contacts.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np
import trimesh

import render_pass1 as R
from build_asm import pose_matrix, FRAME_SHIFT
from check_clearance import named_solids, tess
from dims import *

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else R.OUT
pads = []
for nm, sh in named_solids(r'J:/code/_transfer/shoulder/torso_frame.step'):
    if nm.startswith('shellpart__spine') and sh.BoundingBox().xmax > 0:
        m = tess(sh, 0.3); m.apply_translation((-FRAME_SHIFT, 0, 0)); pads.append(m)
import cadquery as cq
sm = trimesh.util.concatenate([tess(f, 0.4) for f in cq.importers.importStep(r'J:/code/_transfer/shoulder/shell_inner.step').faces().vals()])
sm.apply_translation((-FRAME_SHIFT, 0, 0))
c = sm.triangles_center
sm.update_faces((c[:, 0] > 20) & (c[:, 1] > 200) & (c[:, 1] < 520) & (c[:, 2] > -150) & (c[:, 2] < 150)); sm.remove_unreferenced_vertices()


def posed(pitch, roll, yaw):
    grp = dict(drum='pitch', ring='pitch', cap='pitch', fork_front='roll', fork_rear='roll', fork_cap='roll', hub='yaw', cover='fixed')
    items = []
    for k, m in R.P.items():
        mm = m.copy(); mm.apply_transform(pose_matrix(grp[k], pitch, roll, yaw)); items.append((mm, R.COL[k], 1.0))
    for k, g in (('roll_rs03', 'pitch'), ('rs02', 'roll'), ('pitch_rs03', 'fixed')):
        mm = R.M[k].copy(); mm.apply_transform(pose_matrix(g, pitch, roll, yaw)); items.append((mm, R.DARK, 1.0))
    for n, m in R.UA.items():
        mm = m.copy(); mm.apply_transform(pose_matrix('yaw', pitch, roll, yaw)); items.append((mm, (0.95, 0.95, 0.93), 1.0))
    return items


F = np.array([130.0, 300.0, -60.0])
R.render(posed(-30, -11, -45) + [(m, (0.85, 0.35, 0.25), 1.0) for m in pads] + [(R.FRAME, R.FRAMEC, 1.0)], OUT / 'C1_spine_pad_contact.png',
         F + np.array([300.0, -80.0, -420.0]), F, title='Lower spine pad (shell part, red) at pitch -30, roll -11, yaw -45: 0.01 mm from the upper arm')
F2 = np.array([140.0, 330.0, 0.0])
R.render(posed(0, -13, -60) + [(sm, (0.80, 0.80, 0.80), 0.45), (R.FRAME, R.FRAMEC, 1.0)], OUT / 'C2_shell_skin_contact.png',
         F2 + np.array([330.0, -40.0, 420.0]), F2, title='Shell skin (translucent) at pitch 0, roll -13, yaw -60: first skin contact (past the -11 stop)')
print('done')
