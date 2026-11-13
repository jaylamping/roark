"""Hub cable window footprint against the R1g halves (shoulder thread pick, 2026-11-13): a slot centred at THETA (ours: 0 = +X lug,
positive toward +Z front), +-W/2 tangentially, from r R0 to R1 about the yaw axis, dropped straight down (along -Y) from Y 298 to
Y 240. Every Y section of both halves every 1 mm (bolt / insert / screw holes filled) is checked for overlap with the footprint; the
smallest clearance and where it is are reported, with a picture of the footprint on the sections.
    python cable_footprint_check.py EXPORTS_DIR OUT_TXT OUT_PNG THETA[,THETA...] [W=16] [R0=15.5] [R1=19]      (under capped.py)"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import nearest_points, unary_union

HX, CZ = 170.49, 5.985875
E, out_txt, out_png = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
THETAS = [float(t) for t in sys.argv[4].split(',')]
W = float(sys.argv[5]) if len(sys.argv) > 5 else 16.0
R0 = float(sys.argv[6]) if len(sys.argv) > 6 else 15.5
R1 = float(sys.argv[7]) if len(sys.argv) > 7 else 19.0
YS = np.arange(298.0, 239.5, -1.0)
halves = {n: trimesh.load(E / f'upper_arm_organic_{n}_left.STL') for n in ('front', 'back')}


def section(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return unary_union([Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > 60.0])
                        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]) if not p.is_empty])


def footprint(th):
    t = np.radians(th)
    er, et = np.array([np.cos(t), np.sin(t)]), np.array([-np.sin(t), np.cos(t)])
    c = np.array([HX, CZ])
    return Polygon([c + R0 * er - W / 2 * et, c + R1 * er - W / 2 * et, c + R1 * er + W / 2 * et, c + R0 * er + W / 2 * et])


def theta(x, z):
    return np.degrees(np.arctan2(z - CZ, x - HX)) % 360


secs = {y: {n: section(m, y) for n, m in halves.items()} for y in YS}
L = [f'Footprint: theta (ours: 0 = +X lug, + toward +Z front; back half is 180-360), +-{W / 2} tangentially, r {R0}-{R1}; '
     f'straight drop Y 298 -> 240, sections every 1 mm.']
for th in THETAS:
    fp = footprint(th)
    worst = (1e9, None, None, None)
    per = []
    for y in YS:
        for n, g in secs[y].items():
            if g.is_empty:
                continue
            d = fp.distance(g)
            ov = fp.intersection(g).area
            if ov > 0:
                d = -np.sqrt(ov)      # overlap: report as negative (sqrt of the overlap area, a rough depth)
            if d < worst[0]:
                a, b = nearest_points(fp, g)
                worst = (d, y, n, (round(b.x, 1), round(b.y, 1)))
            per.append((y, n, d))
    ok = worst[0] > 0
    x, z = worst[3]
    L.append(f'theta {th:.0f}: {"PASS" if ok else "FAIL"}; smallest clearance {worst[0]:.2f} mm at Y {worst[1]:.0f}, {worst[2]} half, '
             f'our point X {x} Z {z} (theta {theta(x, z):.0f}, r {np.hypot(x - HX, z - CZ):.1f})')
    for ylo, yhi in ((298, 285), (284, 271), (270, 255), (254, 240)):
        band = [(d, y, n) for y, n, d in per if ylo >= y >= yhi or yhi <= y <= ylo]
        if band:
            d, y, n = min(band)
            L.append(f'   Y {ylo}-{yhi}: min {d:.2f} at Y {y:.0f} ({n})')
fig, axs = plt.subplots(1, 4, figsize=(20, 5.6))
for ax, y in zip(axs, (296.0, 288.0, 270.0, 260.0)):
    for n, g in secs[y].items():
        for p in (g.geoms if hasattr(g, 'geoms') else [g]):
            if not p.is_empty:
                ax.fill(*p.exterior.xy, color='#9db4cf' if n == 'front' else '#c9a97a', ec='#444444', lw=0.4)
    for th, col in zip(THETAS, ('#c0392b', '#2e86c1', '#27ae60')):
        ax.fill(*footprint(th).exterior.xy, color=col, alpha=0.55, label=f'theta {th:.0f}')
    for a in range(0, 360, 30):
        ax.plot([HX, HX + 45 * np.cos(np.radians(a))], [CZ, CZ + 45 * np.sin(np.radians(a))], color='#cccccc', lw=0.4)
        ax.text(HX + 47 * np.cos(np.radians(a)), CZ + 47 * np.sin(np.radians(a)), f'{a}', fontsize=7, ha='center', va='center')
    ax.set_title(f'Y {y:.0f} (front half blue, back half tan)', fontsize=10)
    ax.set_aspect('equal'); ax.set_xlim(HX - 50, HX + 50); ax.set_ylim(CZ - 50, CZ + 50)
axs[0].legend(fontsize=8, loc='lower left')
fig.suptitle(f'Hub cable window footprints (+-{W / 2} tangential, r {R0}-{R1}) on the R1g halves; theta 0 = +X, + toward +Z (front)', fontsize=11)
fig.tight_layout()
fig.savefig(out_png, dpi=110)
Path(out_txt).write_text('\n'.join(L) + '\n', encoding='utf-8')
print('\n'.join(L))
