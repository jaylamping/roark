"""Shared loading, sampling and posing for check_concept.py and spot_check.py.

Surfaces are sampled (about 0.7 mm; frame and upper arm 1.0 mm, fixed seed) and compared with KD-trees, as in the
measurement study, so distances are good to about +-0.4 mm. Motor rotors are split off the stators the same way as the
study (fixsplit.py): a part bolted to an output is not reported as touching it.
"""
import os, sys
import numpy as np, trimesh
from scipy.spatial import cKDTree

RX, RY, PZ, YZ = 170.49, 424.86, -0.014, 5.99
CONCEPT = ['P1_drum', 'P1_cap', 'FORK_front', 'FORK_rear', 'FORK_front_cap', 'HUB_dished', 'PITCH_cover', 'BRG_6808']
FIXED = ['PITCH', 'PBRK', 'FRAME', 'PITCH_cover']
PG = ['P1_drum', 'P1_cap', 'ROLL']
RG = ['FORK_front', 'FORK_rear', 'FORK_front_cap', 'YAW']
YG = ['HUB_dished', 'UA']
WORKERS = int(os.environ.get('SWEEP_WORKERS', '4'))


def load(W, C):
    sys.path.insert(0, W); cwd = os.getcwd(); os.chdir(W)
    from rv import load_all
    d = load_all(); os.chdir(cwd)
    for k in CONCEPT:
        f = os.path.join(C, k + '.stl')
        if os.path.exists(f):
            d[k] = trimesh.load(f)
    return d


def samp(m, sp):
    n = int(m.area / sp ** 2); p, _ = trimesh.sample.sample_surface_even(m, n, seed=1); return p


def samples(d):
    P = {}
    for k, m in d.items():
        if k in ('P1', 'P2', 'SPACER', 'HUB'):
            continue
        P[k] = samp(m, 1.0 if k in ('FRAME', 'UA') else 0.7)
    p = P['PITCH']; r = np.hypot(p[:, 1] - RY, p[:, 2] - PZ); rot = (r < 23.8) & (np.abs(p[:, 0] - 97.0) < 4.5); P['PITCH'] = p[~rot]
    p = P['ROLL']; r = np.hypot(p[:, 0] - RX, p[:, 1] - RY); rot = (r < 23.8) & (np.abs(p[:, 2] - 30.64) < 4.5); P['ROLL'] = p[~rot]
    p = P['YAW']; r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ); rot = (r < 21.8) & (p[:, 1] < 323.5); P['YAW'] = p[~rot]
    P['UA'] = P['UA'][P['UA'][:, 1] > 200]
    return P


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


def q(tree, pts, ub=30):
    dd, _ = tree.query(pts, distance_upper_bound=ub, workers=WORKERS); m = dd.min(); return m if np.isfinite(m) else ub


def pair_dist(TREE, SUB, cls, m, f, p_, r_, y_):
    """Distance for one pair key 'cls|m|f' at pose (pitch, roll, yaw), as check_concept.py defines each class."""
    if cls == 'pitch':
        x = pose(m, p_, r_, y_, SUB[m])
    elif cls == 'roll':
        x = SUB[m]
        if m in YG: x = ty(x, y_)
        x = tr(x, r_)
    else:
        x = ty(SUB[m], y_)
    return float(q(TREE[f], x))
