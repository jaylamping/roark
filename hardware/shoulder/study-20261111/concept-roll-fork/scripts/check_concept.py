"""Interference and gap sweeps for the roll drum and fork concept (second pass).

    python check_concept.py STUDY_WORK CONCEPT_OUT [quick]

STUDY_WORK: folder where the measurement study's torso.py and mesh.py ran (w/*.stl, torso_parts/, rv.py).
CONCEPT_OUT: output of build_concept.py. Writes CONCEPT_OUT/check.json ('quick': 9 deg roll and pitch steps, no file).

Method as the first pass (sweeplib.py): surface samples at 0.7 mm (frame and upper arm 1.0 mm), KD-trees, +-0.4 mm.
Each pair minimum is stored with its pose and the point on the moving part where it occurs (world frame at that pose).
The cap's stop lugs are split off as their own body (STOPS) so the stop contact is reported apart from the cap.
"""
import sys, os, json, time
import numpy as np, trimesh
from scipy.spatial import cKDTree
from sweeplib import (load, samples, pose, tr, ty, q, RX, RY, YZ, FIXED, PG, RG, YG, WORKERS)

W, C = sys.argv[1], sys.argv[2]
QUICK = len(sys.argv) > 3 and sys.argv[3] == 'quick'
ROLL_IN, ROLL_OUTW = -15, 110
P = samples(load(W, C))
# stop lugs: cap samples behind the cap face (Z < -39.4) at r 43.5-55.5 from the roll axis
c = P['P1_cap']; r = np.hypot(c[:, 0] - RX, c[:, 1] - RY); st = (c[:, 2] < -39.4) & (r > 43.5) & (r < 55.5)
P['STOPS'] = c[st]; P['P1_cap'] = c[~st]
PGS = PG + ['STOPS']
for k in P: print(k, len(P[k]), flush=True)
TREE = {k: cKDTree(P[k]) for k in P}
SUB = {k: P[k][::3] for k in P}
res = {}


def qa(tree, pts, ub=30):
    dd, ii = tree.query(pts, distance_upper_bound=ub, workers=WORKERS); j = int(np.argmin(dd))
    return (float(dd[j]), pts[j]) if np.isfinite(dd[j]) else (float(ub), pts[j])


def upd(key, dist, ps, at):
    if key not in res or dist < res[key][0]:
        res[key] = (round(dist, 2), list(ps), [round(float(v), 1) for v in at])


t0 = time.time()
step = 9 if QUICK else 3
ROLLS = sorted(set(list(range(ROLL_IN, ROLL_OUTW + 1, step)) + [ROLL_OUTW]))
PITCHES = sorted(set(list(range(-90, 181, step)) + [180]))
poses = [(p_, r_, y_) for r_ in ROLLS for p_ in (-90, 0, 90, 180) for y_ in (-90, 0, 90)]
poses += [(p_, r_, y_) for p_ in PITCHES for r_ in (ROLL_IN, 0, ROLL_OUTW) for y_ in (-90, 0, 90)]
poses = sorted(set(poses))
curve_frame = {}
for (p_, r_, y_) in poses:
    for m in PG + RG + YG:
        x = pose(m, p_, r_, y_, SUB[m])
        for f in FIXED:
            dist, at = qa(TREE[f], x); upd(f'pitch|{m}|{f}', dist, (p_, r_, y_), at)
            if p_ == 0 and y_ == 0:
                curve_frame.setdefault(f'{m}|{f}', {})[r_] = round(dist, 2)
print('class 1 done', len(poses), round(time.time() - t0), flush=True)
curve_roll = {}
for r_ in sorted(set(list(range(-30, 121, step)) + [ROLL_IN, ROLL_OUTW])):
    for y_ in (-90, 0, 90):
        for m in RG + YG:
            x = SUB[m]
            if m in YG: x = ty(x, y_)
            x = tr(x, r_)
            for f in PGS:
                if m == 'FORK_front' and f == 'ROLL':
                    continue
                dist, at = qa(TREE[f], x)
                if ROLL_IN <= r_ <= ROLL_OUTW:
                    upd(f'roll|{m}|{f}', dist, (0, r_, y_), at)
                if y_ == 0:
                    curve_roll.setdefault(f'{m}|{f}', {})[r_] = round(dist, 2)
for r_ in (ROLL_IN, 0, 45, ROLL_OUTW):
    dist, at = qa(TREE['ROLL'], tr(SUB['FORK_front'], r_)); upd('roll|FORK_front|ROLL', dist, (0, r_, 0), at)
print('class 2 done', round(time.time() - t0), flush=True)
curve_yaw = {}
for y_ in range(-90, 91, 15 if QUICK else 5):
    for m in YG:
        x = ty(SUB[m], y_)
        for f in RG:
            dist, at = qa(TREE[f], x); upd(f'yaw|{m}|{f}', dist, (0, 0, y_), at)
            curve_yaw.setdefault(f'{m}|{f}', {})[y_] = round(dist, 2)
print('class 3 done', round(time.time() - t0), flush=True)

# --- stops: at fine steps round both ends, the fork rear against the lugs and every roll-class pair (full samples)
stops = {}
for r_ in [ROLL_IN - 1, ROLL_IN - 0.5, ROLL_IN, ROLL_IN + 0.5, ROLL_IN + 1, ROLL_IN + 2, ROLL_IN + 5,
           ROLL_OUTW - 5, ROLL_OUTW - 2, ROLL_OUTW - 1, ROLL_OUTW - 0.5, ROLL_OUTW, ROLL_OUTW + 0.5, ROLL_OUTW + 1]:
    row = {}
    for y_ in (-90, 0, 90):
        for m in RG + YG:
            x = P[m]
            if m in YG: x = ty(x, y_)
            x = tr(x, r_)
            for f in PGS:
                if m == 'FORK_front' and f == 'ROLL':
                    continue
                d_, _ = qa(TREE[f], x)
                k = f'{m}|{f}'; row[k] = min(row.get(k, 99.0), round(d_, 2))
    lug = row.pop('FORK_rear|STOPS'); others = {k: v for k, v in row.items() if k.endswith('|STOPS')}
    rest = {k: v for k, v in row.items() if not k.endswith('|STOPS')}
    stops[str(r_)] = dict(arm_to_lug=lug, other_parts_to_lugs=min(others.values()) if others else None,
                          closest_other_pair=min(rest, key=rest.get), closest_other=rest[min(rest, key=rest.get)])
    print('stop', r_, stops[str(r_)], flush=True)
# arm to cage at the inward stop and beyond, every pitch (the upper arm meets the cage near -20)
ua_cage = {}
for r_ in (ROLL_IN, ROLL_IN - 2, ROLL_IN - 5):
    best = 99
    for p_ in PITCHES:
        for y_ in (-90, 0, 90):
            best = min(best, qa(TREE['FRAME'], pose('UA', p_, r_, y_, SUB['UA']))[0])
    ua_cage[r_] = round(best, 2)

# --- static, inside one group (neutral): fits, joints and running gaps that do not move
static = {}
for a, b in [('P1_drum', 'ROLL'), ('P1_cap', 'ROLL'), ('P1_drum', 'P1_cap'), ('P1_drum', 'PITCH'), ('PITCH_cover', 'P1_drum'),
             ('FORK_front', 'FORK_rear'), ('FORK_front', 'YAW'), ('FORK_rear', 'YAW'), ('FORK_rear', 'BRG_6808'),
             ('P1_cap', 'BRG_6808'), ('HUB_dished', 'YAW'), ('UA', 'HUB_dished'), ('FORK_rear', 'P1_cap'),
             ('FORK_front', 'P1_drum'), ('FORK_rear', 'STOPS')]:
    static[f'{a}|{b}'] = round(float(q(cKDTree(P[b]), P[a], 60)), 2)
h = P['HUB_dished']; rr = np.hypot(h[:, 0] - RX, h[:, 2] - YZ); top = h[(rr > 24) & (rr < 38) & (h[:, 1] > 312)]
yv = P['YAW']; ry = np.hypot(yv[:, 0] - RX, yv[:, 2] - YZ); und = yv[(ry > 24) & (ry < 38) & (yv[:, 1] < 330)]
static['yaw_gap_axial_r24_38'] = [round(float(und[:, 1].min() - top[:, 1].max()), 2), round(float(top[:, 1].max()), 2), round(float(und[:, 1].min()), 2)]

# --- passages: no part's surface may lie more than 0.3 mm inside a cut volume (neutral pose); [count, deepest mm]
pas = {}
for f in sorted(os.listdir(C)):
    if not f.startswith('WIRE_') or not f.endswith('.stl'):
        continue
    m = trimesh.load(os.path.join(C, f)); lo, hi = m.bounds[0] - 0.01, m.bounds[1] + 0.01; hits = {}
    for k in P:
        x = P[k]; s = np.all((x > lo) & (x < hi), axis=1)
        if s.sum():
            xi = x[s][m.contains(x[s])]
            if len(xi):     # count only surface points deeper than 0.3 mm inside the passage (faces on its boundary are walls)
                _, dep, _ = trimesh.proximity.closest_point(m, xi)
                n = int((dep > 0.3).sum())
                if n: hits[k] = [n, round(float(dep.max()), 2)]
    pas[f[:-4]] = hits
out = dict(sweeps=res, curve_roll=curve_roll, curve_frame=curve_frame, curve_yaw=curve_yaw, static=static, stops=stops,
           ua_cage_at_inward_stop=ua_cage, passages=pas, n_poses=len(poses), roll_range=[ROLL_IN, ROLL_OUTW])
if not QUICK:
    json.dump(out, open(os.path.join(C, 'check.json'), 'w'), indent=0)
for k, v in sorted(res.items(), key=lambda kv: kv[1][0])[:30]:
    print(k, v)
print('static', static); print('ua-cage', ua_cage); print('passages', pas)
print('done', round(time.time() - t0))
