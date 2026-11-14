"""Frame-rebuild decision pictures (rev A frame, moved -38 X into the parts' coordinates): the arm at the -11 inward stop
(the frame as drawn), and at the first frame contact found by the roll sweep (hardpoint H5), with H5 in red.
python render_frame_options.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np

import render_pass1 as R
from build_asm import pose_matrix, FRAME_SHIFT
from check_clearance import named_solids, tess
from dims import *

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else R.OUT
h5 = []
for nm, sh in named_solids(r'J:/code/_transfer/shoulder/torso_frame.step'):
    if 'H5' in nm:
        m = tess(sh, 0.3); m.apply_translation((-FRAME_SHIFT, 0, 0)); h5.append(m)
        bb = sh.BoundingBox()
        print(nm, 'rev A box', [round(v, 1) for v in (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)])


def posed(pitch, roll, yaw):
    grp = dict(drum='pitch', ring='pitch', cap='pitch', fork_front='roll', fork_rear='roll', fork_cap='roll', hub='yaw', cover='fixed',
               port_cap='pitch')
    items = []
    for k, m in R.P.items():
        mm = m.copy(); mm.apply_transform(pose_matrix(grp.get(k, 'pitch'), pitch, roll, yaw)); items.append((mm, R.COL.get(k, (0.9, 0.9, 0.88)), 1.0))
    for k, g in (('roll_rs03', 'pitch'), ('rs02', 'roll'), ('pitch_rs03', 'fixed')):
        mm = R.M[k].copy(); mm.apply_transform(pose_matrix(g, pitch, roll, yaw)); items.append((mm, R.DARK, 1.0))
    for n, m in R.UA.items():
        mm = m.copy(); mm.apply_transform(pose_matrix('yaw', pitch, roll, yaw)); items.append((mm, (0.95, 0.95, 0.93), 1.0))
    return items


F = np.array([60.0, 258.0, -65.0])
eye = F + np.array([120.0, -430.0, -200.0])
red = [(m, (0.85, 0.25, 0.2), 1.0) for m in h5]
R.render(posed(-30, -11, -45) + red + [(R.FRAME, R.FRAMEC, 1.0)], OUT / 'F1_frame_as_drawn_stop_m11.png', eye, F, size=(1500, 1200), angle=34,
         title='Option 1, rev A as drawn: arm at the -11 inward stop (pitch -30, yaw -45). Upper arm 34 mm from hardpoint H5 (red)')
R.render(posed(-30, -21, -45) + red + [(R.FRAME, R.FRAMEC, 1.0)], OUT / 'F2_frame_first_contact_m21.png', eye, F, size=(1500, 1200), angle=34,
         title='What H5 limits: same pose at roll -21, the upper arm reaches hardpoint H5 (red), the first frame contact')
print('done')
