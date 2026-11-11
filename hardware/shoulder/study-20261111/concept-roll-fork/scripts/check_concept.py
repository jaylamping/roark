"""Interference and gap sweeps for the roll drum and fork concept.

    python check_concept.py STUDY_WORK CONCEPT_OUT

STUDY_WORK: folder where the measurement study's torso.py and mesh.py ran (w/*.stl, torso_parts/), with rv.py importable.
CONCEPT_OUT: output of build_concept.py. Writes CONCEPT_OUT/check.json.

Surfaces are sampled (about 0.7 mm; frame and upper arm 1.0 mm) and compared with KD-trees, as in the study, so distances are
good to about +-0.4 mm. Motor rotors are split off the stators the same way as the study (fixsplit.py): a part bolted to an
output is not reported as touching it.
"""
import sys, os, json, time
import numpy as np, trimesh
from scipy.spatial import cKDTree

W, C = sys.argv[1], sys.argv[2]
sys.path.insert(0, W); os.chdir(W)
from rv import load_all

RX, RY, PZ, YZ = 170.49, 424.86, -0.014, 5.99
d = load_all()
for k in ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished', 'PITCH_cover', 'BRG_6808']:
    d[k] = trimesh.load(os.path.join(C, k + '.stl'))


def samp(m, sp):
    n = int(m.area / sp ** 2); p, _ = trimesh.sample.sample_surface_even(m, n, seed=1); return p


P = {}
for k, m in d.items():
    if k in ('P1', 'P2', 'SPACER', 'HUB'):
        continue
    P[k] = samp(m, 1.0 if k in ('FRAME', 'UA') else 0.7)
# rotor / stator split (fixsplit.py)
p = P['PITCH']; r = np.hypot(p[:, 1] - RY, p[:, 2] - PZ); rot = (r < 23.8) & (np.abs(p[:, 0] - 97.0) < 4.5); P['PITCH'] = p[~rot]
p = P['ROLL']; r = np.hypot(p[:, 0] - RX, p[:, 1] - RY); rot = (r < 23.8) & (np.abs(p[:, 2] - 30.64) < 4.5); P['ROLL'] = p[~rot]
p = P['YAW']; r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ); rot = (r < 21.8) & (p[:, 1] < 323.5); P['YAW'] = p[~rot]
P['UA'] = P['UA'][P['UA'][:, 1] > 200]          # the elbow end is far from everything checked here
for k in P: print(k, len(P[k]), flush=True)

FIXED = ['PITCH', 'PBRK', 'FRAME', 'PITCH_cover']
PG = ['P1_drum', 'P1_cap', 'ROLL']
RG = ['FORK_front', 'FORK_rear', 'FORK_front_cap', 'YAW']
YG = ['HUB_dished', 'UA']


def Rx(a):
    t = np.radians(a); c, s = np.cos(t), np.sin(t); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    t = np.radians(a); c, s = np.cos(t), np.sin(t); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    t = np.radians(a); c, s = np.cos(t), np.sin(t); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


OP, OR, OY = np.array([0, RY, PZ]), np.array([RX, RY, 0]), np.array([RX, 0, YZ])
tp = lambda x, a: (x - OP) @ Rx(-a).T + OP      # pitch +a = arm forward (sweep2.py sign)
tr = lambda x, a: (x - OR) @ Rz(a).T + OR       # roll +a = outward
ty = lambda x, a: (x - OY) @ Ry(a).T + OY


def pose(k, p_, r_, y_, x):
    if k in YG: x = ty(x, y_)
    if k in YG + RG: x = tr(x, r_)
    if k in YG + RG + PG: x = tp(x, p_)
    return x


TREE = {k: cKDTree(P[k]) for k in P}
SUB = {k: P[k][::3] for k in P}
res = {}


def upd(key, dist, ps):
    if key not in res or dist < res[key][0]:
        res[key] = (round(float(dist), 2), ps)


def q(tree, pts, ub=30):
    dd, _ = tree.query(pts, distance_upper_bound=ub, workers=-1); m = dd.min(); return m if np.isfinite(m) else ub


t0 = time.time()
# --- class 1: everything outboard of the pitch output against the torso (pitch, roll, yaw all matter)
ROLLS = list(range(-20, 111, 3)) + [110]
poses = [(p_, r_, y_) for r_ in ROLLS for p_ in (-90, 0, 90, 180) for y_ in (-90, 0, 90)]
poses += [(p_, r_, y_) for p_ in list(range(-90, 181, 3)) for r_ in (-20, 0, 110) for y_ in (-90, 0, 90)]
curve_frame = {}
for (p_, r_, y_) in poses:
    for m in PG + RG + YG:
        x = pose(m, p_, r_, y_, SUB[m])
        for f in FIXED:
            dist = q(TREE[f], x); upd(f'pitch|{m}|{f}', dist, (p_, r_, y_))
            if p_ == 0 and y_ == 0:
                curve_frame.setdefault(f'{m}|{f}', {})[r_] = round(float(dist), 2)
print('class 1 done', len(poses), round(time.time() - t0), flush=True)
# --- class 2: roll group + yaw group against the pitch group (roll, yaw matter)
curve_roll = {}
for r_ in sorted(set(list(range(-30, 121, 3)) + [-20, 110])):
    for y_ in (-90, 0, 90):
        for m in RG + YG:
            x = SUB[m]
            if m in YG: x = ty(x, y_)
            x = tr(x, r_)
            for f in PG:
                if m == 'FORK_front' and f == 'ROLL':
                    continue    # bolted to the roll output (rotor removed); boss vs stator is checked below with the stator ring
                dist = q(TREE[f], x)
                if -20 <= r_ <= 110:
                    upd(f'roll|{m}|{f}', dist, (0, r_, y_))
                if y_ == 0:
                    curve_roll.setdefault(f'{m}|{f}', {})[r_] = round(float(dist), 2)
print('class 2 done', round(time.time() - t0), flush=True)
# fork boss against the roll stator (rotor excluded) at any roll angle: the stator is axisymmetric enough to sample a few
for r_ in (-20, 0, 45, 110):
    upd('roll|FORK_front|ROLL', q(TREE['ROLL'], tr(SUB['FORK_front'], r_)), (0, r_, 0))
# --- class 3: yaw group against the roll group
curve_yaw = {}
for y_ in range(-90, 91, 5):
    for m in YG:
        x = ty(SUB[m], y_)
        for f in RG:
            dist = q(TREE[f], x); upd(f'yaw|{m}|{f}', dist, (0, 0, y_))
            curve_yaw.setdefault(f'{m}|{f}', {})[y_] = round(float(dist), 2)
print('class 3 done', round(time.time() - t0), flush=True)
# --- static, inside one group (neutral): fits, joints and running gaps that do not move
static = {}
for a, b in [('P1_drum', 'ROLL'), ('P1_cap', 'ROLL'), ('P1_drum', 'P1_cap'), ('P1_drum', 'PITCH'), ('PITCH_cover', 'P1_drum'),
             ('FORK_front', 'FORK_rear'), ('FORK_front', 'YAW'), ('FORK_rear', 'YAW'), ('FORK_rear', 'BRG_6808'),
             ('P1_cap', 'BRG_6808'), ('HUB_dished', 'YAW'), ('UA', 'HUB_dished')]:
    static[f'{a}|{b}'] = round(float(q(cKDTree(P[b]), P[a], 60)), 2)
# yaw-crossing gap under the RS02 over r 23.5-38.5 (axial, hub dish to RS02 stator)
h = P['HUB_dished']; rr = np.hypot(h[:, 0] - RX, h[:, 2] - YZ); top = h[(rr > 24) & (rr < 38) & (h[:, 1] > 312)]
yv = P['YAW']; ry = np.hypot(yv[:, 0] - RX, yv[:, 2] - YZ); und = yv[(ry > 24) & (ry < 38) & (yv[:, 1] < 330)]
static['yaw_gap_axial_r24_38'] = [round(float(und[:, 1].min() - top[:, 1].max()), 2), round(float(top[:, 1].max()), 2), round(float(und[:, 1].min()), 2)]


# --- stop check: rear arm against the cap's stop lugs, fine steps near the ends
stopc = {}
for r_ in [-23, -22, -21, -20.5, -20, -19.5, -19, -18, -15, 0, 105, 108, 109, 109.5, 110, 110.5, 111, 112, 113]:
    stopc[r_] = round(float(q(TREE['P1_cap'], tr(P['FORK_rear'], r_))), 2)

# --- passages: no other part's surface may enter a cut volume (neutral pose)
pas = {}
for f in sorted(os.listdir(C)):
    if not f.startswith('WIRE_') or not f.endswith('.stl'):
        continue
    m = trimesh.load(os.path.join(C, f)); lo, hi = m.bounds[0] - 0.01, m.bounds[1] + 0.01; hits = {}
    for k in P:
        x = P[k]; s = np.all((x > lo) & (x < hi), axis=1)
        if s.sum():
            ins = m.contains(x[s]).sum()
            if ins: hits[k] = int(ins)
    pas[f[:-4]] = hits
out = dict(sweeps=res, curve_roll=curve_roll, curve_frame=curve_frame, curve_yaw=curve_yaw, static=static, stops=stopc,
           passages=pas, n_poses=len(poses))
json.dump(out, open(os.path.join(C, 'check.json'), 'w'), indent=0)
for k, v in sorted(res.items(), key=lambda kv: kv[1][0])[:40]:
    print(k, v)
print('static', static); print('stops', stopc); print('passages', pas)
print('done', round(time.time() - t0))
