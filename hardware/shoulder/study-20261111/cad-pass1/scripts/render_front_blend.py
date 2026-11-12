"""Front-blend variants (fork front cheek running into the cuff, no lobes): current, variant 1 (plain chin) and variant 2
(chin wrapping round the cuff), front / front three-quarter with the whole arm / side, and one sheet.
python render_front_blend.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
FA = Path(r'J:/code/roark-wt/left-arm-organic/cad/exports/forearm')
FORE = [(trimesh.load(f), (0.95, 0.95, 0.93) if 'cap' not in f.name else (0.86, 0.87, 0.88), 1.0) for f in sorted(FA.glob('*.STL'))]
VAR = {'now': ('Current', W / 'stl' / 'fork_front.stl'), 'fb1': ('Variant 1: plain blend into the cuff', W / 'stl_look_fb1' / 'fork_front.stl'),
       'fb2': ('Variant 2: blend wrapping round the cuff', W / 'stl_look_fb2' / 'fork_front.stl')}
F = np.array([RX, 380.0, 10.0])
Fw = np.array([RX - 10, 300.0, 10.0])
VIEWS = [('front', F + np.array([0.0, 30.0, 620.0]), F, (1100, 1100), 30, False),
         ('front34', Fw + np.array([620.0, 120.0, 820.0]), Fw, (1200, 1600), 34, True),
         ('side', F + np.array([650.0, 40.0, 0.0]), F, (1100, 1100), 30, False)]
for v, (title, path) in VAR.items():
    P = dict(R.P); P['fork_front'] = trimesh.load(path)
    it = [(m, R.COL[k], 1.0) for k, m in P.items() if k != 'cover'] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
    it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
    for vn, eye, foc, size, ang, arm in VIEWS:
        R.render(it + (FORE if arm else []), OUT / f'{v}_{vn}.png', eye, foc, size=size, angle=ang, title=title)
    print(v, flush=True)
CW, CH = 900, 900
rows = []
for vn, *_ in VIEWS:
    row = Image.new('RGB', (3 * CW, CH), 'white')
    for i, v in enumerate(VAR):
        im = Image.open(OUT / f'{v}_{vn}.png').convert('RGB'); k = min(CW / im.width, CH / im.height)
        im = im.resize((int(im.width * k), int(im.height * k))); row.paste(im, (i * CW + (CW - im.width) // 2, (CH - im.height) // 2))
    rows.append(row)
sheet = Image.new('RGB', (3 * CW, CH * len(rows)), 'white')
for j, r in enumerate(rows):
    sheet.paste(r, (0, j * CH))
sheet.save(OUT / 'SHEET_front_blend.png')
print('done')
