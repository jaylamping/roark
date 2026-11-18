"""Re-run a spread of first-pass sweep poses and compare them with a stored check.json.

    python spot_check.py STUDY_WORK CONCEPT_OUT REF_CHECK_JSON OUT_JSON

Poses: every pose where a pair reached its minimum under 1.0 mm (the contacts), plus a spread of other pair-minimum poses,
plus roll and yaw curve points. At a pair-minimum pose only that pair is compared; at a curve point every pair stored in
that curve is compared. Agreement means |new - old| <= 0.4 mm (the method tolerance).
"""
import sys, json
import numpy as np
from scipy.spatial import cKDTree
from sweeplib import load, samples, pair_dist

W, C, REF, OUTJ = sys.argv[1:5]
ref = json.load(open(REF))
P = samples(load(W, C))
TREE = {k: cKDTree(P[k]) for k in P}
SUB = {k: P[k][::3] for k in P}
rows = []
# 1. pair minima: all contacts, then a spread of the rest (sorted by distance, every 4th)
sw = sorted(ref['sweeps'].items(), key=lambda kv: kv[1][0])
picked = [kv for kv in sw if kv[1][0] < 1.0] + [kv for kv in sw if 1.0 <= kv[1][0] < 30][::4]
for key, (v, ps) in picked:
    cls, m, f = key.split('|')
    rows.append(dict(kind='min', key=key, pose=ps, old=v, new=round(pair_dist(TREE, SUB, cls, m, f, *ps), 2)))
# 2. curve points (pitch 0, yaw 0 for the frame and roll curves)
for r_ in ('-20', '13', '52', '91', '110'):
    for key, c in ref['curve_frame'].items():
        m, f = key.split('|'); rows.append(dict(kind='curve_frame', key='pitch|' + key, pose=[0, int(r_), 0], old=c[r_],
                                                  new=round(pair_dist(TREE, SUB, 'pitch', m, f, 0, int(r_), 0), 2)))
for r_ in ('-30', '-9', '30', '72', '120'):
    for key, c in ref['curve_roll'].items():
        m, f = key.split('|'); rows.append(dict(kind='curve_roll', key='roll|' + key, pose=[0, int(r_), 0], old=c[r_],
                                                 new=round(pair_dist(TREE, SUB, 'roll', m, f, 0, int(r_), 0), 2)))
for y_ in ('-90', '-25', '20', '90'):
    for key, c in ref['curve_yaw'].items():
        m, f = key.split('|'); rows.append(dict(kind='curve_yaw', key='yaw|' + key, pose=[0, 0, int(y_)], old=c[y_],
                                                new=round(pair_dist(TREE, SUB, 'yaw', m, f, 0, 0, int(y_)), 2)))
for r in rows:
    r['diff'] = round(r['new'] - r['old'], 2)
poses = sorted({tuple(r['pose']) for r in rows})
worst = max(rows, key=lambda r: abs(r['diff']))
out = dict(n_poses=len(poses), n_pairs=len(rows), poses=poses, max_abs_diff=abs(worst['diff']), worst=worst,
           n_over_tol=sum(abs(r['diff']) > 0.4 for r in rows), n_exact=sum(r['diff'] == 0 for r in rows), rows=rows)
json.dump(out, open(OUTJ, 'w'), indent=0)
for r in rows:
    if r['kind'] == 'min':
        print(r['key'], r['pose'], r['old'], r['new'])
print('poses', len(poses), 'pair values', len(rows), 'max |diff|', out['max_abs_diff'], 'over 0.4:', out['n_over_tol'],
      'identical:', out['n_exact'])
