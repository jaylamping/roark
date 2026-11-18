"""Worker side of check_clearance.py's process pool: numpy and scipy only, so a worker starts fast and stays small.

Each worker loads the sampled point clouds once (an .npz written by the parent), builds the KD-tree of the part it is asked
about (keeping one at a time), and answers tasks (index, query part, target part, 4x4 matrix that moves the query part into
the target part's frame) with the smallest distance, capped at BOUND.
"""
import numpy as np
from scipy.spatial import cKDTree

BOUND = 40.0      # mm: the search bound; a pair that never comes nearer is reported as "over 40"
_P, _TREE = {}, {}


def init(npz_path):
    with np.load(npz_path) as z:
        for k in z.files:
            _P[k] = z[k]


def dist(task):
    i, q, t, M = task
    if t not in _TREE:
        _TREE.clear()      # one tree at a time: the tasks come sorted by target part
        _TREE[t] = cKDTree(_P[t])
    M = np.asarray(M)
    pts = _P[q] @ M[:3, :3].T + M[:3, 3]
    dd, _ = _TREE[t].query(pts, distance_upper_bound=BOUND, workers=1)
    d = float(dd.min())
    return i, (d if np.isfinite(d) else BOUND)
