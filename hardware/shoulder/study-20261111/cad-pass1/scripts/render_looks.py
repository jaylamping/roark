"""Look options (match the arm): the current outline-fix version beside variants a, b and c, from the same three views
(front three-quarter with the whole arm, back, drum top), plus one comparison sheet.
python render_looks.py OUTDIR    (variant meshes from cad/_wip/shoulder-pass1/stl_look_a and stl_look_c)"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
WHITE = (0.95, 0.95, 0.93)
DARK = (0.365, 0.38, 0.41)        # the arm's dark stub ring colour (left-arm-organic render_a2.py, '#5d6168')
FA = Path(r'J:/code/roark-wt/left-arm-organic/cad/exports/forearm')
FORE = [(trimesh.load(f), (0.95, 0.95, 0.93) if 'cap' not in f.name else (0.86, 0.87, 0.88), 1.0) for f in sorted(FA.glob('*.STL'))]
BAND_Y = 318.6                   # b, c: the cuff skirt below this prints dark (one filament swap), like the arm's dark stub ring


def parts(var):
    base = {k: W / 'stl' / f'{k}.stl' for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'fork_cap', 'hub', 'cover', 'port_cap')}
    if var in ('a', 'b', 'c'):
        for k in ('drum', 'port_cap', 'fork_front', 'fork_rear'):
            base[k] = W / 'stl_look_a' / f'{k}.stl'
        base.pop('fork_cap')                 # a, b, c: the 6 front screws show in the recessed disc, like the forearm caps
    if var == 'c':
        base['fork_front'] = W / 'stl_look_c' / 'fork_front.stl'
    items = []
    for k, f in base.items():
        m = trimesh.load(f)
        col = R.COL[k]
        if var in ('b', 'c') and k in ('fork_front', 'fork_rear'):
            # one dark band at the sleeve's bottom edge, like the forearm's dark stub ring at a section joint (whole dark
            # parts were tried: the rear cap read as a big dark plate, heavier than anything on the arm)
            lo = m.slice_plane((0, BAND_Y, 0), (0, -1, 0), cap=False)
            hi = m.slice_plane((0, BAND_Y, 0), (0, 1, 0), cap=False)
            items += [(lo, DARK, 1.0), (hi, col, 1.0)]
            continue
        items.append((m, col, 1.0))
    items += [(m, R.COL[k], 1.0) for k, m in R.M.items()]
    items += [(m, WHITE if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
    return items


VIEWS = []
Fw = np.array([RX - 10, 300.0, 10.0])
VIEWS.append(('front34', Fw + np.array([620.0, 120.0, 820.0]), Fw, (1200, 1600), 34, True))
Fb = np.array([RX - 10, RY - 45, -20.0])
VIEWS.append(('back', Fb + np.array([0.0, 20.0, -700.0]), Fb, (1200, 1300), 30, False))
Fs = np.array([RX - 15, RY + 20, 0.0])
VIEWS.append(('drumtop', Fs + np.array([330.0, 300.0, 420.0]), Fs, (1400, 1050), 28, False))
NAMES = {'now': 'Current (outline fixes)', 'a': 'a: shape (bobbin drum, waisted cuff, open bolt disc)',
         'b': 'b: a + one dark band at the sleeve bottom', 'c': 'c: b + seam lines carried up the cuff'}
for var in ('now', 'a', 'b', 'c'):
    it = parts(var)
    for vn, eye, foc, size, ang, arm in VIEWS:
        R.render(it + (FORE if arm else []), OUT / f'{var}_{vn}.png', eye, foc, size=size, angle=ang, title=NAMES[var])
    print(var, flush=True)
# comparison sheet: rows = views, columns = variants
CW, CH = 900, 900
rows = []
for vn, *_ in VIEWS:
    row = Image.new('RGB', (4 * CW, CH), 'white')
    for i, v in enumerate(('now', 'a', 'b', 'c')):
        im = Image.open(OUT / f'{v}_{vn}.png').convert('RGB')
        k = min(CW / im.width, CH / im.height)
        im = im.resize((int(im.width * k), int(im.height * k)))
        row.paste(im, (i * CW + (CW - im.width) // 2, (CH - im.height) // 2))
    rows.append(row)
sheet = Image.new('RGB', (4 * CW, CH * len(rows)), 'white')
for j, r in enumerate(rows):
    sheet.paste(r, (0, j * CH))
sheet.save(OUT / 'SHEET_now_a_b_c.png')
print('done')
