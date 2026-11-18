"""Hub cable window: D3b (window at 7.9 deg, over the +X lug) against D3c4 (window at 248 deg, back half). Radial sections
through each window with the arm's r1g4 halves (left-arm-organic, read-only) and the flat bundle (power 16 x 6 + signal
10 x 5, laid flat: 6 mm across the slot) drawn as a 6 mm band; and a plan section at Y 297 with the boss tubes, lugs and
the arm. python render_hub_window.py OUTDIR"""
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RX, YZ = 170.49, 5.99
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
W = Path(r'J:/code/roark-wt/shoulder-study/cad/_wip/shoulder-pass1')
A = Path(r'J:/code/roark-wt/left-arm-organic/cad/_wip/r1d_r1g_print')
HUB = {'D3b (window 7.9 deg)': (W / 'stl_look_hubD3b/hub.STL', 7.9), 'D3c4 (window 248 deg)': (W / 'stl_look_hubD3c4/hub.STL', 248.0)}
ARM = [trimesh.load(A / f) for f in ('upper_arm_organic_front_left.STL', 'upper_arm_organic_back_left.STL', 'checks/lug_plates_045_r1g4.STL')]
P1, P0 = (15.5, 298.0), (31.0, 318.36 + 2.0)        # the slot's centre line (build_parts HUB_WIN): entry and dish end


def radial(m, th):
    a = math.radians(th)
    s = m.section(plane_origin=(RX, 0, YZ), plane_normal=(-math.sin(a), 0, math.cos(a)))
    out = []
    if s is None:
        return out
    for p in s.discrete:
        p = np.asarray(p)
        r = (p[:, 0] - RX) * math.cos(a) + (p[:, 2] - YZ) * math.sin(a)
        if (r > 0).mean() > 0.5:
            out.append(np.c_[r, p[:, 1]])
    return out


def bundle(ax):
    # straight drop at r 17 (inside r 19 at the hub's lower end), then a bend into the slot's line, 6 mm thick
    u = np.subtract(P0, P1); u = u / np.linalg.norm(u)
    pts = [(17.0, 240.0), (17.0, 292.0)]
    c = np.array(P1) + u * 1.0
    for t in np.linspace(0, 1, 12):
        pts.append(tuple(np.array([17.0, 292.0]) * (1 - t) ** 2 + 2 * (1 - t) * t * np.array([17.0, 297.5]) + t ** 2 * c))
    pts.append(tuple(np.array(P0) - u * 2.0))
    pts = np.array(pts)
    ax.plot(pts[:, 0], pts[:, 1], color='tab:orange', lw=6 * 72 / 25.4 * 0.42, alpha=0.45, solid_capstyle='butt')
    ax.plot(pts[:, 0], pts[:, 1], color='tab:orange', lw=0.8)


fig, axs = plt.subplots(1, 2, figsize=(15, 9), dpi=110)
for ax, (nm, (path, th)) in zip(axs, HUB.items()):
    m = trimesh.load(path)
    for p in radial(m, th):
        ax.fill(p[:, 0], p[:, 1], color='0.8', lw=0); ax.plot(p[:, 0], p[:, 1], color='0.3', lw=0.7)
    for am in ARM:
        for p in radial(am, th):
            ax.plot(p[:, 0], p[:, 1], color='tab:blue', lw=0.7)
    bundle(ax)
    ax.axvline(19.0, color='tab:red', ls=':', lw=0.8)
    ax.set_xlim(0, 45); ax.set_ylim(250, 325); ax.set_aspect('equal'); ax.grid(lw=0.3)
    ax.set_xlabel('r from the yaw axis (mm)'); ax.set_ylabel('Y (mm)')
    ax.set_title(f'{nm}: radial section through the window. Grey hub, blue arm r1g4, orange bundle (6 mm), red r 19', fontsize=8)
fig.tight_layout(); fig.savefig(OUT / 'hub_window_radial_D3b_vs_D3c4.png'); plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(15, 7.6), dpi=110)
for ax, (nm, (path, th)) in zip(axs, HUB.items()):
    m = trimesh.load(path)
    for y_, col in ((297.0, '0.3'), (306.0, 'tab:green')):
        s = m.section(plane_origin=(0, y_, 0), plane_normal=(0, 1, 0))
        for p in s.discrete:
            p = np.asarray(p)[:, [0, 2]] - [RX, YZ]
            ax.plot(p[:, 0], p[:, 1], color=col, lw=0.7)
    for am in ARM:
        s = am.section(plane_origin=(0, 292.0, 0), plane_normal=(0, 1, 0))
        if s is not None:
            for p in s.discrete:
                p = np.asarray(p)[:, [0, 2]] - [RX, YZ]
                ax.plot(p[:, 0], p[:, 1], color='tab:blue', lw=0.6)
    a = math.radians(th)
    ax.plot([0, 45 * math.cos(a)], [0, 45 * math.sin(a)], color='tab:orange', ls='--', lw=0.8)
    for sg in (-1, 1):       # the window's +-8 mm footprint
        o = np.array([-math.sin(a), math.cos(a)]) * 8.0 * sg
        ax.plot([o[0] + 15.5 * math.cos(a), o[0] + 31 * math.cos(a)], [o[1] + 15.5 * math.sin(a), o[1] + 31 * math.sin(a)], color='tab:orange', lw=0.8)
    t = np.linspace(0, 2 * np.pi, 200); ax.plot(19 * np.cos(t), 19 * np.sin(t), 'r:', lw=0.6)
    ax.set_aspect('equal'); ax.set_xlim(-45, 45); ax.set_ylim(-45, 45); ax.grid(lw=0.3)
    ax.set_title(f'{nm}: hub at Y 297 (grey) and Y 306 (green, boss tubes), arm at Y 292 (blue), window +-8 mm (orange)', fontsize=8)
    ax.set_xlabel('X - RX'); ax.set_ylabel('Z - YZ')
fig.tight_layout(); fig.savefig(OUT / 'hub_window_plan_D3b_vs_D3c4.png'); plt.close(fig)
print('done')
