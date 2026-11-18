"""leg2 mock-up (rear leg 2 mm wider each side and 2 mm deeper at Y 380-402, channels 1 mm back) against the real fork
rear: side (outboard, inboard), back, rear three-quarter. python render_leg2.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
VAR = {'real': ('Real fork rear (63.7 g)', W / 'stl' / 'fork_rear.stl'), 'leg2': ('leg2 mock-up: rear leg +2 mm each side and deeper (66.1 g)', W / 'stl_look_leg2' / 'fork_rear.stl')}
F = np.array([RX, 380.0, -20.0])
VIEWS = [('side_out', F + np.array([560.0, 0.0, 0.0])), ('side_in', F + np.array([-560.0, 0.0, 0.0])),
         ('back', F + np.array([0.0, 20.0, -600.0])), ('back34', F + np.array([380.0, 60.0, -480.0]))]
for v, (title, path) in VAR.items():
    P = dict(R.P); P['fork_rear'] = trimesh.load(path)
    it = [(m, R.COL[k], 1.0) for k, m in P.items() if k != 'cover'] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
    it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
    for vn, eye in VIEWS:
        R.render(it, OUT / f'{v}_{vn}.png', eye, F, size=(1000, 1100), angle=30, title=title)
CW, CH = 900, 990
sheet = Image.new('RGB', (2 * CW, CH * len(VIEWS)), 'white')
for j, (vn, _) in enumerate(VIEWS):
    for i, v in enumerate(VAR):
        im = Image.open(OUT / f'{v}_{vn}.png').convert('RGB').resize((CW, CH)); sheet.paste(im, (i * CW, j * CH))
sheet.save(OUT / 'SHEET_leg2.png')
print('done')
