"""Hub cable window study (shoulder thread question, 2026-11-13): what of ours lies inside r RMAX of the yaw (hub) axis, by Y plane
sections of the R1g halves (plus the lug bolts and seam screws as solid cylinders), and where a round cable bundle of diameter DB,
centred at r RC, can drop straight down (along -Y) from the hub bore without touching anything.
Theta convention (ours, used in every r1c script): theta = atan2(Z - CZ, X - HX), 0 deg at +X (the +X lug), increasing toward
+Z (the front half); the seam plane Z = CZ is theta 0 / 180.
    python cable_window_sections.py EXPORTS_DIR OUT_PNG OUT_TXT [HUB_STL]      (under capped.py)"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
import os
YS = tuple(float(v) for v in os.environ.get("CW_YS", "298,296,292,288,284,270").split(","))
RMAX, DB = 22.0, 16.0
RCS = (13.0, 15.5)          # bundle centre radii tried (the hub's entry centre is r 15.5)
E = Path(sys.argv[1])
out_png, out_txt = sys.argv[2], sys.argv[3]
hub = trimesh.load(sys.argv[4]) if len(sys.argv) > 4 else None
halves = {n: trimesh.load(E / f'upper_arm_organic_{n}_left.STL') for n in ('front', 'back')}


def section(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return Polygon()
    polys = []
    for e in s.discrete:      # loops in 3D; take (X, Z)
        if len(e) >= 4:
            polys.append(Polygon(e[:, [0, 2]]).buffer(0))
    # even-odd fill: XOR of the loops, then fill small holes (bolt / screw / insert holes count as solid: the hardware fills them)
    g = Polygon()
    for p in polys:
        g = g.symmetric_difference(p)
    filled = []
    for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
        if p.is_empty:
            continue
        filled.append(Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > 60.0]))
    return unary_union(filled)


lines = ['Theta: atan2(Z - CZ, X - HX); 0 deg = +X (the +X lug), positive toward +Z (front half). Seam plane at 0 / 180.',
         f'Material of ours inside r {RMAX} of the yaw axis (X {HX}, Z {CZ:.3f}), by Y plane; bolt / screw / insert holes filled.', '']
mats = {}
fig, axs = plt.subplots(2, 3, figsize=(16, 11))
th = np.radians(np.arange(0, 360, 0.5))
for k, y in enumerate(YS):
    g = unary_union([section(m, y) for m in halves.values()])
    mats[y] = g
    disc = Point(HX, CZ).buffer(RMAX, 256)
    inside = g.intersection(disc)
    lines.append(f'Y {y}: area inside r {RMAX}: {inside.area:.1f} mm2')
    for p in (inside.geoms if hasattr(inside, 'geoms') else [inside]):
        if p.is_empty or p.area < 0.5:
            continue
        c = np.array(p.exterior.coords)
        a = np.degrees(np.arctan2(c[:, 1] - CZ, c[:, 0] - HX)) % 360
        r = np.hypot(c[:, 0] - HX, c[:, 1] - CZ)
        sa = np.sort(a)
        gaps = np.diff(np.r_[sa, sa[0] + 360])
        i = np.argmax(gaps)
        a0, a1 = sa[(i + 1) % len(sa)], sa[i]
        lines.append(f'   piece {p.area:7.1f} mm2: theta {a0:6.1f} -> {a1:6.1f} (ccw), r min {r.min():5.1f}, centroid X {p.centroid.x:.1f} Z {p.centroid.y:.1f}')
    ax = axs.flat[k]
    for p in (g.geoms if hasattr(g, 'geoms') else [g]):
        if not p.is_empty:
            ax.fill(*p.exterior.xy, color='#9db4cf', lw=0.4, ec='#33557a')
            for h in p.interiors:
                ax.fill(*h.xy, color='white', lw=0.4, ec='#33557a')
    if hub is not None:
        hs = hub.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if hs is not None:
            for e in hs.discrete:
                ax.plot(e[:, 0], e[:, 2], color='#c0392b', lw=0.6)
    ax.plot(HX + RMAX * np.cos(th), CZ + RMAX * np.sin(th), 'k--', lw=0.6)
    for a in range(0, 360, 30):
        ax.plot([HX, HX + 40 * np.cos(np.radians(a))], [CZ, CZ + 40 * np.sin(np.radians(a))], color='#bbbbbb', lw=0.4)
        ax.text(HX + 42 * np.cos(np.radians(a)), CZ + 42 * np.sin(np.radians(a)), f'{a}', fontsize=7, ha='center', va='center')
    ax.set_title(f'Y {y}' + (' (hub red)' if hub is not None else ''), fontsize=10)
    ax.set_aspect('equal'); ax.set_xlim(HX - 48, HX + 48); ax.set_ylim(CZ - 48, CZ + 48)
    ax.set_xlabel('X'); ax.set_ylabel('Z')

# straight drop: a round bundle DB at r RC, theta t, must clear the union of every section (the planes it passes)
lines.append('')
union = unary_union(list(mats.values()))
for rc in RCS:
    free = []
    for t in np.arange(0, 360, 0.5):
        c = Point(HX + rc * np.cos(np.radians(t)), CZ + rc * np.sin(np.radians(t)))
        free.append(c.distance(union) >= DB / 2)
    free = np.array(free)
    ranges, i, n = [], 0, len(free)
    if free.all():
        ranges = [(0.0, 360.0)]
    else:
        start = np.argmin(free)      # begin on a blocked angle so wrapped ranges join
        run = None
        for j in range(n):
            t = (start + j) % n
            if free[t] and run is None:
                run = t
            if not free[t] and run is not None:
                ranges.append((run * 0.5, ((t - 1) % n) * 0.5)); run = None
        if run is not None:
            ranges.append((run * 0.5, ((start - 1) % n) * 0.5))
    dmin = [Point(HX + rc * np.cos(np.radians(t)), CZ + rc * np.sin(np.radians(t))).distance(union) for t in range(0, 360, 5)]
    lines.append(f'Straight drop, bundle Dia {DB} centred at r {rc}: free theta ranges (centre angle) {[(float(a), float(b)) for a, b in ranges]}')
    lines.append('   clearance (distance to our nearest material, minus 8) every 5 deg: ' +
                 ' '.join(f'{t}:{d - DB / 2:+.1f}' for t, d in zip(range(0, 360, 5), dmin)))
fig.suptitle(f'R1g halves, Y sections; dashed r {RMAX}; theta 0 = +X, positive toward +Z (front)', fontsize=12)
fig.tight_layout()
fig.savefig(out_png, dpi=110)
Path(out_txt).write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
