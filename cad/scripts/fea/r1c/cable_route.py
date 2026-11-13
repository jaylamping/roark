"""Cable route from the hub window down into the arm's open cavity (2026-11-13, shoulder thread question), R1g halves.
Bundle: flat 16 x 6 (16 along u, 6 along v). At the hub window (theta, Y 298) its centre is at r RC with v radial (the 6 mm is
radial) and u tangential. Theta (ours = the hub's): atan2(Z - CZ, X - HX), 0 = +X lug, + toward +Z (front half).
Route model (bends across the thin direction only, no edgewise bend): the centre moves sideways only along the bundle's current
v axis, s(y) a half-cosine from 0 (Y >= Y1) to S_END over a drop L; the bundle may twist (u rotates about the route) by TAU over
the same stretch, at most 90 deg per 50 mm. Bend radius across the thin direction R = 2 L^2 / (|S_END| pi^2), at least RMIN.
Every route is checked against Y sections every 1 mm from 298 to 245 (both halves, holes filled); the best (largest minimum
clearance, then the largest R) is reported with: hub-end clearances (Y 298-284) of the slot footprint (+-8 across, r 15.5-19) and
of the bundle; and an assembly sweep (the front half closes along -Z last: any front-half material directly below the bundle in
Z would pass through it).
    python cable_route.py EXPORTS_DIR OUT_DIR THETA[,THETA...]      (under capped.py)"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
E, OUT = Path(sys.argv[1]), Path(sys.argv[2])
THETAS = [float(t) for t in sys.argv[3].split(',')]
W, T, RC, RMIN = 16.0, 6.0, 16.0, 30.0
YS = np.arange(298.0, 244.5, -1.0)
halves = {n: trimesh.load(E / f'upper_arm_organic_{n}_left.STL') for n in ('front', 'back')}


def section(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return unary_union([Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > 60.0])
                        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]) if not p.is_empty])


secs = {y: {n: section(m, y) for n, m in halves.items()} for y in YS}
allm = {y: unary_union(list(secs[y].values())) for y in YS}


def rect(c, psi):
    """bundle cross-section: centre c (x, z), long axis u at angle psi (deg, in the X-Z plane)"""
    r = box(-W / 2, -T / 2, W / 2, T / 2)
    return affinity.translate(affinity.rotate(r, psi, origin=(0, 0)), c[0], c[1])


def route(th, s_end, y1, L, tau):
    """centre and psi per Y plane; v = the bundle's thin axis (radial at the hub), sideways moves along v only"""
    t = np.radians(th)
    c = np.array([HX + RC * np.cos(t), CZ + RC * np.sin(t)])
    psi0 = th + 90.0      # u tangential
    out, prev_s = [], 0.0
    for y in YS:
        f = 0.0 if y >= y1 else (1.0 if y <= y1 - L else 0.5 * (1 - np.cos(np.pi * (y1 - y) / L)))
        s, psi = s_end * f, psi0 + tau * f
        ds = s - prev_s
        prev_s = s
        v = np.array([np.cos(np.radians(psi - 90.0)), np.sin(np.radians(psi - 90.0))])      # thin axis (outward radial at the hub)
        c = c + ds * v
        out.append((y, c.copy(), psi))
    return out


def clearance(rt, mats):
    worst = (1e9, None)
    for y, c, psi in rt:
        d = rect(c, psi).distance(mats[y])
        if rect(c, psi).intersects(mats[y]):
            d = -np.sqrt(rect(c, psi).intersection(mats[y]).area)
        if d < worst[0]:
            worst = (d, y)
    return worst


res = {}
for th in THETAS:
    best = None
    for s_end in np.arange(0.0, -24.1, -1.0):
        for y1 in (298.0, 294.0, 290.0, 286.0, 282.0, 278.0):
            for L in (20.0, 30.0, 40.0, 50.0):
                R = 2 * L ** 2 / (abs(s_end) * np.pi ** 2) if s_end else 1e9
                if R < RMIN:
                    continue
                for tau in (-45.0, -30.0, -15.0, 0.0, 15.0, 30.0, 45.0):
                    if abs(tau) > 90.0 * L / 50.0:
                        continue
                    rt = route(th, s_end, y1, L, tau)
                    cl, yc = clearance(rt, allm)
                    key = (round(cl, 2), round(min(R, 999.0), 1))
                    if best is None or key > best[0]:
                        best = (key, dict(s_end=float(s_end), y1=y1, L=L, tau=tau, R=float(min(R, 9999.0)), min_clearance=float(cl), at_Y=yc))
    p = best[1]
    rt = route(th, p['s_end'], p['y1'], p['L'], p['tau'])
    # hub end: slot footprint and the bundle, Y 298-284
    t = np.radians(th)
    er, et = np.array([np.cos(t), np.sin(t)]), np.array([-np.sin(t), np.cos(t)])
    c0 = np.array([HX, CZ])
    slot = Polygon([c0 + 15.5 * er - 8 * et, c0 + 19 * er - 8 * et, c0 + 19 * er + 8 * et, c0 + 15.5 * er + 8 * et])
    hub_slot = min(slot.distance(allm[y]) for y in YS if y >= 284)
    hub_bundle = min(rect(c, psi).distance(allm[y]) for y, c, psi in rt if y >= 284)
    # assembly: front half closes along -Z; front material directly below the bundle (in -Z) at the same X would pass through it
    sweep = 0.0
    for y, c, psi in rt:
        rb = rect(c, psi)
        cols = unary_union([rb, affinity.translate(rb, 0, -200.0)]).convex_hull      # the bundle and everything below it in Z (rb is convex)
        a = cols.intersection(secs[y]['front']).area
        sweep = max(sweep, a)
    # bend / slope
    cs = np.array([c for _, c, _ in rt])
    dl = np.linalg.norm(np.diff(cs, axis=0), axis=1)
    slope = float(dl.max())
    tw = np.abs(np.diff([psi for _, _, psi in rt]))
    res[th] = dict(**p, hub_end_slot_clearance=round(float(hub_slot), 2), hub_end_bundle_clearance=round(float(hub_bundle), 2),
                   max_slope_mm_per_mm=round(slope, 3), twist_deg_total=p['tau'], twist_max_deg_per_50mm=round(float(tw.max()) * 50, 1),
                   assembly_front_sweep_overlap_mm2=round(float(sweep), 3),
                   start=[round(float(v), 2) for v in cs[0]], end=[round(float(v), 2) for v in cs[-1]])
    # pictures: X-Z (sections and the bundle at chosen planes) and Y-Z / Y-X (centre line, bundle extent, front wall)
    fig, axs = plt.subplots(1, 3, figsize=(20, 7))
    ax = axs[0]
    for y, col in ((298.0, '#bbbbbb'), (284.0, '#999999'), (270.0, '#777777'), (260.0, '#555555'), (250.0, '#333333')):
        g = allm[y]
        for pg in (g.geoms if hasattr(g, 'geoms') else [g]):
            if not pg.is_empty:
                ax.plot(*pg.exterior.xy, color=col, lw=0.6)
        for yy, c, psi in rt:
            if yy == y:
                ax.fill(*rect(c, psi).exterior.xy, alpha=0.45, label=f'bundle at Y {y:.0f}')
    ax.set_aspect('equal'); ax.set_xlim(HX - 50, HX + 50); ax.set_ylim(CZ - 45, CZ + 50)
    ax.set_title(f'theta {th:.0f}: X-Z, sections (grey, darker = lower Y) and the bundle', fontsize=10); ax.legend(fontsize=7)
    ax.set_xlabel('X'); ax.set_ylabel('Z')
    for k, (ax, idx, lab) in enumerate(((axs[1], 1, 'Z'), (axs[2], 0, 'X'))):
        ys = np.array([y for y, _, _ in rt])
        lo, hi, wl, wh = [], [], [], []
        for y, c, psi in rt:
            b = np.array(rect(c, psi).exterior.coords)[:, idx]
            lo.append(b.min()); hi.append(b.max())
            # material bounds along this axis through the bundle centre line (the cavity walls)
            line = box(c[0] - 0.01, -200, c[0] + 0.01, 200) if idx == 1 else box(-200 + 0 * c[1], c[1] - 0.01, 400, c[1] + 0.01)
            m = allm[y].intersection(line)
            vals = []
            for pg in (m.geoms if hasattr(m, 'geoms') else [m]):
                if not pg.is_empty:
                    bb = pg.bounds
                    vals += [bb[idx], bb[idx + 2]]
            vals = np.array(vals) if vals else np.array([np.nan])
            ctr = c[idx]
            wl.append(np.nanmax(vals[vals < ctr]) if np.any(vals < ctr) else np.nan)
            wh.append(np.nanmin(vals[vals > ctr]) if np.any(vals > ctr) else np.nan)
        ax.fill_between(ys, lo, hi, color='#2e86c1', alpha=0.45, label='bundle extent')
        ax.plot(ys, wl, 'k-', lw=1, label='our wall (below)'); ax.plot(ys, wh, 'r-', lw=1, label='our wall (above)')
        ax.set_xlabel('Y (hub end at the left)'); ax.set_ylabel(lab); ax.invert_xaxis(); ax.grid(alpha=0.3); ax.legend(fontsize=8)
        ax.set_title(f'theta {th:.0f}: Y-{lab} along the route through the bundle centre', fontsize=10)
    fig.suptitle(f'Cable route theta {th:.0f}: min clearance {p["min_clearance"]:.2f} at Y {p["at_Y"]:.0f}; sideways {p["s_end"]:.0f} mm along the thin axis '
                 f'from Y {p["y1"]:.0f} over {p["L"]:.0f} mm (R {min(p["R"], 999):.0f}); twist {p["tau"]:.0f} deg', fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / f'cable_route_{int(th)}.png', dpi=100)
    plt.close(fig)
    print(th, json.dumps(res[th]))
json.dump(res, open(OUT / 'cable_route.json', 'w'), indent=1)
