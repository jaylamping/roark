"""Fork joint screws seen from behind: the earlier two-screw joint vs the real six-screw joint (both on the r 47 sleeve).
python render_rear_screws.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
VAR = {'N': ('Layout N (real parts): -27, -17, +17, +26 at Y 357; -22, +20 at Y 345.5, all closed', W / 'stl' / 'fork_rear.stl'),
       'G': ('Rejected: symmetric G (+-12, +-24; +-20), joint SF 1.33', W / 'stl_look_rsG' / 'fork_rear.stl')}
import os
if (W / 'stl_look_rsNc' / 'fork_rear.stl').exists():
    VAR['Nc'] = ('N with flush printed caps (option b)', W / 'stl_look_rsNc' / 'fork_rear.stl')
Fb = np.array([RX, 352.0, -40.0])
VIEWS = [('back', Fb + np.array([0.0, 10.0, -420.0]), Fb, 26), ('back34', Fb + np.array([300.0, 60.0, -380.0]), Fb, 26)]
for v, (title, path) in VAR.items():
    P = dict(R.P); P['fork_rear'] = trimesh.load(path)
    it = [(m, R.COL[k], 1.0) for k, m in P.items() if k != 'cover'] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
    it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
    for vn, eye, foc, ang in VIEWS:
        R.render(it, OUT / f'{v}_{vn}.png', eye, foc, size=(1100, 1000), angle=ang, title=title)
CW, CH = 1000, 910
sheet = Image.new('RGB', (len(VAR) * CW, CH * len(VIEWS)), 'white')
for j, (vn, *_) in enumerate(VIEWS):
    for i, v in enumerate(VAR):
        im = Image.open(OUT / f'{v}_{vn}.png').convert('RGB'); k = min(CW / im.width, CH / im.height)
        im = im.resize((int(im.width * k), int(im.height * k))); sheet.paste(im, (i * CW, j * CH))
sheet.save(OUT / 'SHEET_rear_screws.png')
print('done')
