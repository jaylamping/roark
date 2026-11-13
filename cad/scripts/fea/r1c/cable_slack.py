"""Hub harness slack and sliding check (2026-11-13, shoulder thread question), R1g halves + the RS02 ring + the vendor RS02 placed.
Bundle 13 x 3.5 laid flat (13 along u, 3.5 along v), minimum bend radius RB across the thin direction (no edgewise bends).
Theta (ours = the hub's): atan2(Z - CZ, X - HX), 0 = +X lug, + toward +Z (front half). The elbow drum axis runs along X at
(Y CY, Z CZ); phi about it: 0 = +Y (toward the hub / the neck).
1. Slack loop below the waist: a rolling U-loop (two straight legs 2 RB + t apart, joined by an R RB U-bend) in a plane that
   contains Y. Its envelope in that plane is a rectangle (2 RB + t) wide along the loop's in-plane horizontal direction d, 13 thick
   across it. For every d (0-165 deg), every offset of the plane and every start Y, the longest clear vertical run is found
   (clearance >= MARGIN to the halves, ring and RS02). Travel = run - (RB + t/2); length taken up = 2 x travel.
   Also: the free radial gap around the RS02 inside the drum (X sections), for a wrap around the motor.
2. Sliding stretch Y 298-245 on the THETA route: clearance of the 13 x 3.5 bundle per plane, the nearest feature, and the corner
   angle of our section outline at the nearest point (a sharp printed edge is a corner under 135 deg with no round).
    python cable_slack.py EXPORTS_DIR RS02FIT_DIR OUT_DIR [THETA=68]      (under capped.py)"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import shapely
import trimesh
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

HX, CZ, CY = 170.49, 5.985875, 209.860668
E, FIT, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
TH = float(sys.argv[4]) if len(sys.argv) > 4 else 68.0
W, T, RB, MARGIN = 13.0, 3.5, 24.0, 0.5
sys.path.insert(0, str(FIT))
from rs02_fit import CLOCK, place      # noqa: E402

parts = {n: trimesh.load(E / f'upper_arm_organic_{n}_left.STL') for n in ('front', 'back', 'rs02_ring')}
parts['rs02'] = place(CLOCK)


def secY(m, y, fill=60.0):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return unary_union([Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > fill])
                        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]) if not p.is_empty])


res = {}
# ---- 1. U-loop below the waist (Y 256 down to 165)
YL = np.arange(256.0, 164.5, -1.0)
obst = {y: unary_union([secY(m, y) for m in parts.values()]).buffer(MARGIN) for y in YL}
# the open cavity region of each plane: inside our halves' outer outline (anything outside the skin is not usable)
skin = {y: unary_union([Polygon(p.exterior) for n in ('front', 'back') for g in [secY(parts[n], y)]
                        for p in (g.geoms if hasattr(g, 'geoms') else [g]) if not p.is_empty]) for y in YL}
Lw = 2 * RB + T
best = (0.0, None)
xs, zs = np.arange(140.0, 201.0, 2.0), np.arange(-40.0, 52.0, 2.0)
for dd in range(0, 180, 15):
    base = affinity.rotate(box(-Lw / 2, -W / 2, Lw / 2, W / 2), dd, origin=(0, 0))
    cand = [(x, z) for x in xs for z in zs]
    rects = np.array([affinity.translate(base, x, z) for x, z in cand])
    ok = np.zeros((len(YL), len(cand)), bool)
    for k, y in enumerate(YL):
        ok[k] = shapely.contains(skin[y], rects) & ~shapely.intersects(rects, obst[y])
    for j in range(len(cand)):
        run, r0 = 0, None
        for k in range(len(YL)):
            if ok[k, j]:
                run += 1
                if run > best[0]:
                    best = (run, dict(d_deg=dd, x=cand[j][0], z=cand[j][1], y_top=float(YL[k - run + 1]), y_bot=float(YL[k])))
            else:
                run = 0
run = best[0]
travel = max(0.0, run - (RB + T / 2))
res['1_u_loop'] = dict(bend_radius=RB, loop_width_needed=Lw, best_clear_run_mm=float(run), best=best[1], travel_mm=travel,
                       length_taken_up_mm=2 * travel, needed_mm=100.0)
# free radial gap around the RS02 inside the drum, by X sections (phi 0 = +Y)


def secX(m, x):
    s = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
    g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4:
            g = g.symmetric_difference(Polygon(e[:, [1, 2]]).buffer(0))
    return g.buffer(0)


gaps = {}
for x in (145.0, 150.0, 155.0, 160.0, 165.0, 170.0, 180.0, 190.0):
    mats = unary_union([secX(m, x) for m in parts.values()])
    row = {}
    for ph in range(0, 360, 15):
        a = np.radians(ph)
        rr = np.arange(20.0, 46.0, 0.25)
        pts = shapely.points(CY + rr * np.cos(a), CZ + rr * np.sin(a))
        inside = shapely.intersects(pts, mats)
        # the largest free radial run that has material on both ends (the annulus between the motor / ring and the drum wall)
        best_r, cur, seen = 0.0, 0.0, False
        for k in range(len(rr)):
            if inside[k]:
                if seen and cur > best_r:
                    best_r = cur
                seen, cur = True, 0.0
            else:
                cur += 0.25
        row[ph] = round(best_r, 2)
    gaps[x] = row
res['1_drum_annulus_free_radial_mm'] = gaps
# ---- 2. sliding stretch on the THETA route (bends across the thin direction only; R >= RB)
YS = np.arange(298.0, 244.5, -1.0)
halves = {y: unary_union([secY(parts[n], y) for n in ('front', 'back')]) for y in YS}
RC = float(sys.argv[5]) if len(sys.argv) > 5 else 17.2 + T / 2      # centre r at Y 298 (2026-11-13: inner face r 17.2, centre about 19)


def rect(c, psi):
    return affinity.translate(affinity.rotate(box(-W / 2, -T / 2, W / 2, T / 2), psi, origin=(0, 0)), c[0], c[1])


def route(s_end, y1, L, tau, rc=None):
    t = np.radians(TH)
    rc = RC if rc is None else rc
    c = np.array([HX + rc * np.cos(t), CZ + rc * np.sin(t)])
    psi0, out, prev = TH + 90.0, [], 0.0
    for y in YS:
        f = 0.0 if y >= y1 else (1.0 if y <= y1 - L else 0.5 * (1 - np.cos(np.pi * (y1 - y) / L)))
        s, psi = s_end * f, psi0 + tau * f
        v = np.array([np.cos(np.radians(psi - 90.0)), np.sin(np.radians(psi - 90.0))])
        c = c + (s - prev) * v
        prev = s
        out.append((y, c.copy(), psi))
    return out


def best_route(rc):
    bestr = None
    for s_end in np.arange(0.0, -26.1, -1.0):
        y1 = 298.0      # the slant can only start at Y 298 (the hub's lower end)
        for L in (20.0, 30.0, 40.0, 45.0, 50.0, 53.0):
            R = 2 * L ** 2 / (abs(s_end) * np.pi ** 2) if s_end else 1e9
            if R < RB:
                continue
            for tau in (-30.0, -15.0, 0.0, 15.0, 30.0):
                if abs(tau) > 90.0 * L / 50.0:
                    continue
                rt = route(s_end, y1, L, tau, rc)
                cl = min(rect(c, p_).distance(halves[y]) if not rect(c, p_).intersects(halves[y]) else -1.0 for y, c, p_ in rt)
                key = (round(cl, 2), round(min(R, 999.0), 1))
                if bestr is None or key > bestr[0]:
                    bestr = (key, dict(rc=float(rc), s_end=float(s_end), y1=y1, L=L, tau=tau, R=float(min(R, 9999.0)), min_clearance=float(cl)))
    return bestr


bestr = best_route(RC)
scan = {}
for rc in np.arange(15.0, 21.51, 0.5):
    b = best_route(rc)[1]
    scan[float(rc)] = dict(inner_face_r=round(float(rc - T / 2), 2), min_clearance=round(b['min_clearance'], 2), R=round(b['R'], 1), s_end=b['s_end'])
res['2_entry_scan'] = scan
p = bestr[1]
rt = route(p['s_end'], p['y1'], p['L'], p['tau'])
sweep = 0.0
for y, c, psi in rt:
    rb = rect(c, psi)
    cols = unary_union([rb, affinity.translate(rb, 0, -200.0)]).convex_hull
    sweep = max(sweep, cols.intersection(secY(parts['front'], y)).area)
cs = np.array([c for _, c, _ in rt])
p['max_slope_mm_per_mm'] = round(float(np.linalg.norm(np.diff(cs, axis=0), axis=1).max()), 3)
p['assembly_front_sweep_overlap_mm2'] = round(float(sweep), 3)
p['hub_end_min_clearance_Y298_284'] = round(float(min(rect(c, ps).distance(halves[y]) for y, c, ps in rt if y >= 284)), 2)


def feature(q, y):
    xo, dz = abs(q[0] - HX), q[1] - CZ
    if 266.0 <= y <= 276.0 and 13.0 <= xo <= 22.0:
        return 'fin end (Y 268-276)'
    if y >= 283.5 and 15.0 <= xo <= 36.0 and abs(dz) < 25.0:
        return 'hub post / web corner'
    if 250.0 <= y <= 272.0 and dz > 10.0:
        return 'waist front wall'
    if 250.0 <= y <= 272.0 and dz < -10.0:
        return 'waist back wall'
    return 'arm wall'


def corner_angle(g, q):
    """interior angle of our outline at the vertex nearest q (deg; 180 = straight / smooth)"""
    best = (1e9, None)
    for pg in (g.geoms if hasattr(g, 'geoms') else [g]):
        for ring in [pg.exterior] + list(pg.interiors):
            c = np.array(ring.coords)[:-1]
            k = int(np.argmin(np.hypot(c[:, 0] - q[0], c[:, 1] - q[1])))
            d = np.hypot(*(c[k] - q))
            if d < best[0]:
                a, b = c[k - 1] - c[k], c[(k + 1) % len(c)] - c[k]
                ang = np.degrees(np.arccos(np.clip(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12), -1, 1)))
                best = (d, round(float(ang), 1), round(float(np.linalg.norm(a)), 2), round(float(np.linalg.norm(b)), 2))
    return best[1:]


rows = []
for y, c, psi in rt:
    rb = rect(c, psi)
    d = rb.distance(halves[y])
    a_, b_ = shapely.ops.nearest_points(rb, halves[y])
    q = (b_.x, b_.y)
    rows.append(dict(y=float(y), clearance=round(float(d), 2), feature=feature(q, y), at=[round(q[0], 2), round(q[1], 2)],
                     corner=corner_angle(halves[y], q)))
feats = {}
for r in rows:
    f = r['feature']
    if f not in feats or r['clearance'] < feats[f]['clearance']:
        feats[f] = r
res['2_route'] = p
res['2_edges'] = feats
res['2_rows'] = rows
json.dump(res, open(OUT / 'cable_slack.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('2_rows', '1_drum_annulus_free_radial_mm')}, indent=1))
print('drum annulus free radial gap (mm), phi 0 = +Y: ')
for x, row in gaps.items():
    print(f'  X {x:.0f}: ' + ' '.join(f'{k}:{v}' for k, v in row.items()))
# picture: the U-loop envelope (if any) and the drum section with the motor
fig, axs = plt.subplots(1, 3, figsize=(20, 7))
for ax, y in zip(axs[:2], (250.0, 240.0)):
    g = unary_union([secY(m, y) for m in parts.values()])
    for pg in (g.geoms if hasattr(g, 'geoms') else [g]):
        if not pg.is_empty:
            ax.fill(*pg.exterior.xy, color='#9db4cf', ec='#33557a', lw=0.5)
            for h in pg.interiors:
                ax.fill(*h.xy, color='white', ec='#33557a', lw=0.5)
    if best[1] is not None:
        b = best[1]
        ax.plot(*affinity.translate(affinity.rotate(box(-Lw / 2, -W / 2, Lw / 2, W / 2), b['d_deg'], origin=(0, 0)), b['x'], b['z']).exterior.xy, 'r-', lw=1.2,
                label=f'best U-loop envelope (needs {Lw:.1f} x {W:.0f})')
    ax.set_aspect('equal'); ax.set_title(f'Y {y:.0f}: halves, ring and RS02 (blue)', fontsize=10); ax.legend(fontsize=8)
    ax.set_xlabel('X'); ax.set_ylabel('Z')
ax = axs[2]
g = unary_union([secX(m, 160.0) for m in parts.values()])
for pg in (g.geoms if hasattr(g, 'geoms') else [g]):
    if not pg.is_empty:
        ax.fill(*pg.exterior.xy, color='#9db4cf', ec='#33557a', lw=0.5)
        for h in pg.interiors:
            ax.fill(*h.xy, color='white', ec='#33557a', lw=0.5)
ax.add_patch(plt.Circle((CY, CZ), RB, fill=False, ls='--', color='r', label=f'R {RB:.0f} bend'))
ax.set_aspect('equal'); ax.set_title('X 160 section through the drum: RS02, ring, drum wall (Y-Z)', fontsize=10); ax.legend(fontsize=8)
ax.set_xlabel('Y'); ax.set_ylabel('Z')
fig.suptitle(f'Hub harness slack below the waist: bundle {W:.0f} x {T}, R {RB:.0f} across the thin direction; '
             f'best clear U-loop run {run:.0f} mm -> takes up {2 * travel:.0f} mm of the 100 mm needed', fontsize=11)
fig.tight_layout(); fig.savefig(OUT / 'cable_slack.png', dpi=100)

fig, axs = plt.subplots(1, 2, figsize=(15, 7))
ax = axs[0]
for y, col in ((298.0, '#bbbbbb'), (284.0, '#999999'), (272.0, '#777777'), (260.0, '#555555'), (250.0, '#333333')):
    g = halves[y]
    for pg in (g.geoms if hasattr(g, 'geoms') else [g]):
        if not pg.is_empty:
            ax.plot(*pg.exterior.xy, color=col, lw=0.6)
    for yy, c, ps in rt:
        if yy == y:
            ax.fill(*rect(c, ps).exterior.xy, alpha=0.5, label=f'bundle at Y {y:.0f}')
ax.set_aspect('equal'); ax.set_xlim(HX - 50, HX + 50); ax.set_ylim(CZ - 45, CZ + 50); ax.legend(fontsize=7)
ax.set_title(f'theta {TH:.0f}, entry centre r {RC:.2f}: X-Z sections and the 13 x 3.5 bundle', fontsize=10)
ax = axs[1]
ys = np.array([r['y'] for r in rows]); cl = np.array([r['clearance'] for r in rows])
ax.plot(ys, cl, 'b-'); ax.axhline(1.5, color='r', ls='--', lw=0.8, label='1.5 mm')
ax.invert_xaxis(); ax.grid(alpha=0.3); ax.set_xlabel('Y (hub end at the left)'); ax.set_ylabel('clearance to our halves (mm)'); ax.legend(fontsize=8)
ax.set_title(f'clearance along the route: min {p["min_clearance"]:.2f}; R {min(p["R"], 999):.0f}; slope {p["max_slope_mm_per_mm"]}', fontsize=10)
fig.tight_layout(); fig.savefig(OUT / f'cable_route_{int(TH)}_r{RC:.1f}.png', dpi=100)
