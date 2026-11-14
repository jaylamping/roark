"""Where the whole-arm worst sphere averages sit at each radius (review 3, item 6; 2026-11-14). Every arm node is a centre (as
hub_r1c R1C_ALL_CENTRES); for each of 0.5 / 1 / 2 mm, the worst N centres of vm, layer (sz tension) and interlayer shear, with
location, theta and r from the hub axis, so the 1 and 2 mm values can be placed.
    python worst_centres.py NPZ POST_TXT [N=4] [COMPONENTS=vm,layer,shear]"""
import re
import sys

import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
d = np.load(sys.argv[1])
p, s = d['pos'], d['s']
NW = int(sys.argv[3]) if len(sys.argv) > 3 else 4
comps = (sys.argv[4] if len(sys.argv) > 4 else 'vm,layer,shear').split(',')
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[2]).read().split('\n')[0])
body = np.full(len(p), '?', object)
for nm, a, b in runs:
    body[int(a):int(b) + 1] = nm
arm = np.flatnonzero(body == 'arm')
q = p[arm]
vm = np.sqrt(0.5 * ((s[arm, 1] - s[arm, 2]) ** 2 + (s[arm, 2] - s[arm, 3]) ** 2 + (s[arm, 3] - s[arm, 1]) ** 2) + 3 * (s[arm, 4] ** 2 + s[arm, 5] ** 2 + s[arm, 6] ** 2))
val = {'vm': (vm, 45.0), 'layer': (s[arm, 3], 22.5), 'shear': (np.hypot(s[arm, 5], s[arm, 6]), 13.0)}
t = cKDTree(q)
for R in (0.5, 1.0, 2.0):
    pairs = t.query_pairs(R, output_type='ndarray')
    n = len(q)
    rows = np.r_[pairs[:, 0], pairs[:, 1], np.arange(n)]
    cols = np.r_[pairs[:, 1], pairs[:, 0], np.arange(n)]
    M = csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(n, n))
    cnt = np.asarray(M.sum(axis=1)).ravel()
    for k in comps:
        v, al = val[k]
        avg = (M @ v) / cnt
        o = np.argsort(-avg)[:NW]
        for j in o:
            th = np.degrees(np.arctan2(q[j, 2] - CZ, q[j, 0] - HX)) % 360
            r = np.hypot(q[j, 0] - HX, q[j, 2] - CZ)
            print(f'R {R}: {k:5s} SF {al / avg[j]:5.2f} (n {int(cnt[j])}) at {np.round(q[j], 2).tolist()} theta {th:.0f} r {r:.2f}')
    del M, pairs
