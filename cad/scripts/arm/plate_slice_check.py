"""Slice-preview check of the lug plates' 0.7 strip above the Dia 3.8 hole (2026-11-13, review C11): reads the sliced gcode of a
plate set, takes the extrusion moves of one layer, and plots them zoomed on the strip above each plate's hole (located from the
plate STL; gcode and STL matched by their XY bounding boxes). Reports per plate how many separate extrusion lines cross the strip
(a closed perimeter around the hole plus the outer perimeter = at least 2).
    python plate_slice_check.py SET_DIR LAYER_Z OUT_PNG [N_PLATES=4]      (SET_DIR holds lug_shims_X.stl and r1f_lug_shims_X.gcode)"""
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from shapely.geometry import Polygon

d, zl, outp = Path(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
NP = int(sys.argv[4]) if len(sys.argv) > 4 else 4
stl = next(d.glob('lug_shims_*.stl'))
gc = next(d.glob('r1f_lug_shims_*.gcode'))
m = trimesh.load(stl)
sec = m.section(plane_origin=[0, 0, 0.1], plane_normal=[0, 0, 1])
holes = [Polygon(e[:, :2]) for e in sec.discrete if 8.0 < Polygon(e[:, :2]).area < 14.0]
hc = np.array([[h.centroid.x, h.centroid.y] for h in holes])
HR = float(np.sqrt(np.mean([h.area for h in holes]) / np.pi))      # the hole radius as modelled
# gcode: extrusion segments per layer
segs, z, x, y, e_prev, cur = [], 0.0, 0.0, 0.0, 0.0, []
rel_e = False
for ln in gc.read_text(errors='replace').splitlines():
    if ln.startswith('M83'):
        rel_e = True
    if not ln.startswith(('G1', 'G0', 'G2', 'G3')):
        continue
    mz = re.search(r'Z([-\d.]+)', ln)
    if mz:
        z = float(mz.group(1))
    mx, my, me = re.search(r'X([-\d.]+)', ln), re.search(r'Y([-\d.]+)', ln), re.search(r'E([-\d.]+)', ln)
    nx = float(mx.group(1)) if mx else x
    ny = float(my.group(1)) if my else y
    ext = me is not None and (float(me.group(1)) > 0 if rel_e else float(me.group(1)) > e_prev)
    if me and not rel_e:
        e_prev = float(me.group(1))
    if ext and ln.startswith(('G2', 'G3')):      # arc moves (the slicer's arc fitting): split into short chords
        mi, mj = re.search(r'I([-\d.]+)', ln), re.search(r'J([-\d.]+)', ln)
        cx_, cy_ = x + (float(mi.group(1)) if mi else 0.0), y + (float(mj.group(1)) if mj else 0.0)
        a0, a1 = np.arctan2(y - cy_, x - cx_), np.arctan2(ny - cy_, nx - cx_)
        rr = np.hypot(x - cx_, y - cy_)
        if ln.startswith('G2'):      # clockwise
            while a1 >= a0:
                a1 -= 2 * np.pi
        else:
            while a1 <= a0:
                a1 += 2 * np.pi
        aa = np.linspace(a0, a1, max(3, int(abs(a1 - a0) / 0.1) + 2))
        px_, py_ = cx_ + rr * np.cos(aa), cy_ + rr * np.sin(aa)
        for k_ in range(len(aa) - 1):
            segs.append((z, px_[k_], py_[k_], px_[k_ + 1], py_[k_ + 1]))
    elif ext and (nx, ny) != (x, y):
        segs.append((z, x, y, nx, ny))
    x, y = nx, ny
S = np.array(segs)
zs = np.unique(np.round(S[:, 0], 2))
zpick = zs[np.argmin(np.abs(zs - zl))]
L = S[np.abs(S[:, 0] - zpick) < 1e-3]
allS = S[S[:, 0] > 0]
gx0, gy0 = allS[:, [1, 3]].min(), allS[:, [2, 4]].min()
gx1, gy1 = allS[:, [1, 3]].max(), allS[:, [2, 4]].max()
b = m.bounds
off = np.array([(gx0 + gx1) / 2 - (b[0, 0] + b[1, 0]) / 2, (gy0 + gy1) / 2 - (b[0, 1] + b[1, 1]) / 2])
order = np.lexsort((hc[:, 0], -hc[:, 1]))[:NP]
fig, axs = plt.subplots(1, NP, figsize=(4.2 * NP, 4.6))
for ax, k in zip(np.atleast_1d(axs), order):
    c = hc[k] + off
    win = (c[0] - 4.0, c[0] + 4.0, c[1] - 1.5, c[1] + 4.0)
    n_cross = 0
    for _, x0_, y0_, x1_, y1_ in L:
        if win[0] - 2 < x0_ < win[1] + 2 and win[2] - 2 < y0_ < win[3] + 2:
            ax.plot([x0_, x1_], [y0_, y1_], color='#c0392b', lw=2.2, alpha=0.8, solid_capstyle='round')
            # does this segment cross the vertical line through the hole centre above the hole (the strip)?
            if (x0_ - c[0]) * (x1_ - c[0]) <= 0 and max(y0_, y1_) > c[1] + HR - 0.3:
                n_cross += 1
    ax.add_patch(plt.Circle(c, HR, fill=False, ls='--', color='k', lw=0.8))
    top_ = float(m.bounds[1, 1]) - 0.0      # plate top in STL coordinates is per plate; draw the strip from the gcode outer perimeter instead
    ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3]); ax.set_aspect('equal'); ax.grid(alpha=0.3)
    ax.set_title(f'hole at ({c[0]:.1f}, {c[1]:.1f}): {n_cross} lines cross the strip', fontsize=9)
fig.suptitle(f'{gc.name}, layer Z {zpick:.2f}: extrusion paths (red, 0.42 wide) round the Dia {2 * HR:.1f} hole (dashed) and the strip above it to the plate top', fontsize=10)
fig.tight_layout(); fig.savefig(outp, dpi=120)
print(f'layer Z {zpick:.2f}; picture {outp}')
