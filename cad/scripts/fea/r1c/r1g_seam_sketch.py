"""Seam pocket envelope for the extended-lug torque path (2026-11-12): sections of the R1e print halves and hub bc16e97 at the seam
(θ 180, the -X lug; θ 0 is the mirror), with the proposed lug extension and our pocket drawn on, dimensioned.
    python seam_pocket_sketch.py HALVES_DIR HUB_STL OUT_PNG      (run under capped.py)"""
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MPoly, Rectangle

HX, CZ = 170.49, 5.985875
X, HUB, OUT = sys.argv[1:4]
front = trimesh.load(X + '/upper_arm_organic_front_left.STL')
back = trimesh.load(X + '/upper_arm_organic_back_left.STL')
hub = trimesh.load(HUB)

# proposed envelope (our side): pocket r <= 37.0, Y 294.3-297.8, |Z - CZ| <= 5.0 + 0.4 shim + 0.1 = 5.5 ; lug extension r <= 36.8,
# Y 294.5-297.6, |Z - CZ| <= 5.0
POCKET = dict(r1=34.6, y0=287.5, y1=295.75, hz=5.5)
EXT = dict(r0=29.5, r1=34.4, y0=288.0, y1=296.0, hz=5.0)


def loops(m, origin, normal):
    s = m.section(plane_origin=origin, plane_normal=normal)
    return [] if s is None else [e for e in s.discrete if len(e) > 3]


fig, axs = plt.subplots(1, 2, figsize=(15, 7.5), gridspec_kw=dict(width_ratios=[1.15, 1]))
# left: side section in the seam's half (plane Z = CZ + 2.5, inside the lug), radius from the hub axis (-X side) vs Y
ax = axs[0]
for m, col, lab in ((front, '#9db7d5', 'arm, front half (Z = CZ+2.5)'), (hub, '#e3b778', 'hub bc16e97')):
    for i, e in enumerate(loops(m, [0, 0, CZ + 2.5], [0, 0, 1])):
        q = np.c_[HX - e[:, 0], e[:, 1]]
        if q[:, 0].max() < 15 or q[:, 0].min() > 45:
            continue
        ax.add_patch(MPoly(q, closed=True, fc=col, ec='k', lw=0.4, alpha=0.75, label=lab if i == 0 else None))
for e in loops(front, [0, 0, CZ + 5.3], [0, 0, 1]):      # the post, at the lug face plane
    q = np.c_[HX - e[:, 0], e[:, 1]]
    ax.plot(q[:, 0], q[:, 1], color='#1f4e8c', lw=0.6, ls='--')
ax.add_patch(Rectangle((EXT['r0'], EXT['y0']), EXT['r1'] - EXT['r0'], EXT['y1'] - EXT['y0'], fc='#d9534f', alpha=0.35, ec='#d9534f', lw=1.2, label='lug extension (hub D3b), X off 29.5-34.4, Y 288-296, R0.8 outward root'))
ax.add_patch(Rectangle((18.3, POCKET['y0']), POCKET['r1'] - 18.3, POCKET['y1'] - POCKET['y0'], fill=False, ec='#2a7f2a', lw=1.6, ls='-', label='our pocket (R1g), X off to 34.6, up to our floor Y 295.75; web post-to-wall'))
ax.axhline(297.8, color='0.4', lw=0.6, ls=':')
ax.axhline(298.3, color='#7a4e9a', lw=0.8, ls='--')
ax.axhline(295.7, color='0.4', lw=0.6, ls=':')
ax.axhline(296.0, color='#b8860b', lw=0.6, ls=':')
ax.text(15.5, 298.45, 'ridge starts Y 298.3 (kept whole)', color='#7a4e9a', fontsize=8)
ax.add_patch(Rectangle((18.96, 288.2), 34.2 - 18.96, 294.6 - 288.2, fill=False, ec='#5cb85c', lw=1.2, ls='--', label='lug plate (main face only), hole Dia 4.4'))
ax.text(15.5, 295.35, 'our floor Y 295.7 / spigot underside Y 296.0', fontsize=8, color='0.3')
for y, rs in ((288.5, 36.3), (292.0, 37.6), (295.5, 38.2)):      # skin X offset at the pocket face (Z 5.3, measured)
    ax.annotate('', xy=(34.6, y), xytext=(rs, y), arrowprops=dict(arrowstyle='<->', lw=0.8))
    ax.text(rs + 0.15, y - 0.15, f'wall {rs - 34.6:.1f} at Z 5.3', fontsize=7.5)
ax.text(19.0, 292.0, 'lug bolt Y 292\n(r 23, unchanged)', fontsize=7.5, ha='left')
ax.text(19.0, 289.3, 'post (dashed, Z = CZ+5.3)', fontsize=7.5, color='#1f4e8c')
ax.set_xlim(15, 41)
ax.set_ylim(286, 304)
ax.set_aspect('equal')
ax.set_xlabel('radius from the hub axis at θ 180 (mm)')
ax.set_ylabel('Y (mm)')
ax.set_title('Seam section θ 180 (θ 0 mirrors): side view in the lug plane')
ax.legend(loc='lower left', fontsize=7.5)
ax.grid(alpha=0.25)
# right: top section at Y 296.5 (through the pocket), around θ 180, X-Z
ax = axs[1]
for m, col in ((front, '#9db7d5'), (back, '#b5c9a8'), (hub, '#e3b778')):
    for e in loops(m, [0, 292.5, 0], [0, 1, 0]):
        q = np.c_[e[:, 0], e[:, 2]]
        if (q[:, 0] > 150).all():
            continue
        ax.add_patch(MPoly(q, closed=True, fc=col, ec='k', lw=0.4, alpha=0.75))
x_in, x_out = HX - 36.8, HX - EXT['r0']
ax.add_patch(Rectangle((HX - EXT['r1'], CZ - EXT['hz']), EXT['r1'] - EXT['r0'], 2 * EXT['hz'], fc='#d9534f', alpha=0.35, ec='#d9534f', lw=1.2))
ax.add_patch(Rectangle((HX - POCKET['r1'], CZ - POCKET['hz']), POCKET['r1'] - 18.3, 2 * POCKET['hz'], fill=False, ec='#2a7f2a', lw=1.6))
for zs in (-1, 1):
    ax.add_patch(Rectangle((HX - 36.8, CZ + zs * 5.0 if zs > 0 else CZ - 5.4), 36.8 - 18.7, 0.4, fc='#5cb85c', alpha=0.6, ec='none'))
ax.axhline(CZ, color='k', lw=0.6, ls='-.')
ax.text(HX - 44.5, CZ + 0.25, 'seam Z = CZ', fontsize=8)
ax.annotate('', xy=(HX - 37.5, CZ - 5.5), xytext=(HX - 37.5, CZ + 5.5), arrowprops=dict(arrowstyle='<->', lw=0.8))
ax.text(HX - 44.5, CZ + 3.0, 'slot 11.0 = lug 10.0' + chr(10) + '+ plates 0.5 x 2 (nominal)', fontsize=7.5)
ax.text(HX - 30, CZ + 6.3, 'lug plates (green)', fontsize=7.5, color='#2a7f2a')
ax.set_xlim(HX - 45, HX - 15)
ax.set_ylim(CZ - 12, CZ + 12)
ax.set_aspect('equal')
ax.set_xlabel('X (mm)')
ax.set_ylabel('Z (mm)')
ax.set_title('Top section at Y 292.5 (front half above the seam, back below)')
ax.grid(alpha=0.25)
fig.suptitle('R1g seam pocket with the hub D3b straight lug and the lug plates (our FEA hub shown; D3b STL check owed). mm.', fontsize=11)
fig.tight_layout()
fig.savefig(OUT, dpi=130)
print('saved', OUT)
