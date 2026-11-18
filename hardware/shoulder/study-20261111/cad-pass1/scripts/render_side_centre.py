"""Side-centre mock-up (sleeve rear curving in toward the arm, power channel bending into the yaw exit): current vs mock-up,
side from outboard and inboard, back three-quarter, back; one sheet, and a section through the power channel (X = RX - 6).
python render_side_centre.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = R.REPO / 'cad' / '_wip' / 'shoulder-pass1'
VAR = {'now': ('Current (front blend 3)', W / 'stl'), 'sc': ('r 54.5: rear curving in, channel bend R 24', W / 'stl_look_sc'),
       'sc47': ('r 47: lower sleeve a closed ring, split at Y 340', W / 'stl_look_sc47')}
VAR = {k: v for k, v in VAR.items() if (v[1] / 'fork_front.stl').exists()}
NV = len(VAR)
F = np.array([RX, 345.0, -5.0])
Fb = np.array([RX, 340.0, -20.0])
VIEWS = [('side_out', F + np.array([620.0, 0.0, 0.0]), F, (1100, 1100), 30),
         ('side_in', F + np.array([-620.0, 0.0, 0.0]), F, (1100, 1100), 30),
         ('back34', Fb + np.array([380.0, 60.0, -560.0]), Fb, (1100, 1100), 30),
         ('back', Fb + np.array([0.0, 20.0, -640.0]), Fb, (1100, 1100), 30)]
for v, (title, d) in VAR.items():
    P = dict(R.P)
    for k in ('fork_front', 'fork_rear'):
        P[k] = trimesh.load(d / f'{k}.stl')
    it = [(m, R.COL[k], 1.0) for k, m in P.items() if k != 'cover'] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
    it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
    for vn, eye, foc, size, ang in VIEWS:
        R.render(it, OUT / f'{v}_{vn}.png', eye, foc, size=size, angle=ang, title=title)
    print(v, flush=True)
CW, CH = 900, 900
rows = []
for vn, *_ in VIEWS:
    row = Image.new('RGB', (NV * CW, CH), 'white')
    for i, v in enumerate(VAR):
        im = Image.open(OUT / f'{v}_{vn}.png').convert('RGB'); k = min(CW / im.width, CH / im.height)
        im = im.resize((int(im.width * k), int(im.height * k))); row.paste(im, (i * CW + (CW - im.width) // 2, (CH - im.height) // 2))
    rows.append(row)
sheet = Image.new('RGB', (NV * CW, CH * len(rows)), 'white')
for j, r in enumerate(rows):
    sheet.paste(r, (0, j * CH))
sheet.save(OUT / 'SHEET_side_centre.png')

# section through the power channel plane (X = RX + P_OFF): outlines of fork front, fork rear, hub and arm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, axs = plt.subplots(1, NV, figsize=(6.5 * NV, 7.5), sharey=True)
x0 = RX + P_OFF
for ax, (v, (title, d)) in zip(axs, VAR.items()):
    for k, c in (('fork_front', '#4a7ab0'), ('fork_rear', '#c0612b'), ('hub', '#777777')):
        m = trimesh.load((d if k != 'hub' else W / 'stl') / f'{k}.stl')
        s = m.section(plane_origin=[x0, 0, 0], plane_normal=[1, 0, 0])
        if s is None:
            continue
        for e in s.discrete:
            e = np.asarray(e); ax.plot(e[:, 2] - YZ, e[:, 1], color=c, lw=1.0)
    for n, m in R.UA.items():
        s = m.section(plane_origin=[x0, 0, 0], plane_normal=[1, 0, 0])
        if s is not None:
            for e in s.discrete:
                e = np.asarray(e); ax.plot(e[:, 2] - YZ, e[:, 1], color='#999999', lw=0.8)
    ax.axvline(0, color='k', lw=0.5, ls='--'); ax.axvline(JZ0 - YZ, color='#c0612b', lw=0.5, ls=':')
    ax.set_title(title, fontsize=10); ax.set_aspect('equal'); ax.set_xlim(-80, 60); ax.set_ylim(270, 380)
    ax.set_xlabel('Z from the yaw axis (mm; + front)')
axs[0].set_ylabel('Y (mm)')
fig.suptitle(f'Section at X = RX {P_OFF:+.0f} (power channel plane). Blue fork front, orange fork rear, grey hub and arm. Dotted: joint plane', fontsize=10)
fig.savefig(OUT / 'section_channel.png', dpi=110, bbox_inches='tight')
print('done')
