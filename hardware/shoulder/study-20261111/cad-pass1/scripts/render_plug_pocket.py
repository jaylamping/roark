"""Plug pocket (a) mock-up: front, side, three-quarter against the real fork front, and a section through the 173 deg
socket showing the XT30(2+2)-F envelope, the lead's U-turn and the drum's 2 mm envelope. python render_plug_pocket.py OUTDIR"""
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
VAR = {'now': ('Real fork front (no column)', W / 'stl' / 'fork_front.stl'), 'ppa': ('Mock-up (a): hidden plug column', W / 'stl_look_pp_a' / 'fork_front.stl')}
F = np.array([RX, 370.0, 0.0])
VIEWS = [('front', F + np.array([0.0, 20.0, 560.0]), F), ('side_in', F + np.array([-560.0, 20.0, 0.0]), F),
         ('front34_in', F + np.array([-400.0, 80.0, 420.0]), F), ('top_in', F + np.array([-250.0, 420.0, 60.0]), F)]
for v, (title, path) in VAR.items():
    P = dict(R.P); P['fork_front'] = trimesh.load(path)
    it = [(m, R.COL[k], 1.0) for k, m in P.items() if k not in ('cover', 'drum', 'ring', 'cap')] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
    for vn, eye, foc in VIEWS:
        R.render(it, OUT / f'{v}_{vn}.png', eye, foc, size=(1000, 1000), angle=30, title=title + ' (drum hidden)')
CW = 900
sheet = Image.new('RGB', (2 * CW, CW * len(VIEWS)), 'white')
for j, (vn, *_) in enumerate(VIEWS):
    for i, v in enumerate(VAR):
        im = Image.open(OUT / f'{v}_{vn}.png').convert('RGB').resize((CW, CW)); sheet.paste(im, (i * CW, j * CW))
sheet.save(OUT / 'SHEET_plug_pocket.png')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
z0 = YZ + 34.4 * math.sin(math.radians(173.0))      # through the socket centre, normal ~ Z (tangential at 173 deg)
fig, ax = plt.subplots(figsize=(8, 9))
for k, path, c in (('fork_front', W / 'stl_look_pp_a' / 'fork_front.stl', '#4a7ab0'), ('drum', W / 'stl' / 'drum.stl', '#999999')):
    s = trimesh.load(path).section(plane_origin=[0, 0, z0], plane_normal=[0, 0, 1])
    if s is not None:
        for e in s.discrete:
            e = np.asarray(e); ax.plot(e[:, 0] - RX, e[:, 1], color=c, lw=0.9)
for n, m in R.M.items():
    s = m.section(plane_origin=[0, 0, z0], plane_normal=[0, 0, 1])
    if s is not None:
        for e in s.discrete:
            e = np.asarray(e); ax.plot(e[:, 0] - RX, e[:, 1], color='#333333', lw=0.6)
t = np.linspace(-math.pi, 0, 200)
xe = 59.0 * np.cos(t); ye = RY + 59.0 * np.sin(t); keep = np.abs(xe) < np.sqrt(max(59 ** 2 - 0, 0))
ax.plot(xe, ye, 'r--', lw=0.8, label='drum r 57 + 2 mm envelope')
# plug envelope (worst credible: 15 mm above the socket top incl. cups and lead bend) and the lead's U-turn
ax.add_patch(plt.Rectangle((-37.4, 360.1), 6.2, 11.0, fill=False, ec='#d08000', lw=1.2, label='XT30(2+2)-F, +3 mm cups'))
th = np.linspace(0, math.pi, 50)
ax.plot(-39.4 + 2.0 * np.cos(th + math.pi), 371.1 + 4.0 * np.sin(th) * 0 + 2.0 * np.sin(th), color='#d08000', lw=1.0)
ax.plot([-41.4, -41.4], [371.1, 357.0], color='#d08000', lw=1.0, label='lead U-turn down to the tap')
ax.axhline(375.1, color='#d08000', ls=':', lw=0.6)
ax.set_xlim(-60, -15); ax.set_ylim(345, 392); ax.set_aspect('equal'); ax.legend(fontsize=7, loc='upper right')
ax.set_title(f'Section at Z {z0:.1f} through the 173 deg RS02 socket (X from the yaw axis)', fontsize=9)
fig.savefig(OUT / 'section_plug_pocket.png', dpi=130, bbox_inches='tight')
print('done')
