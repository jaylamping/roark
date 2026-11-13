"""D2: is each governing peak a stress or a corner? Follow the SAME place through the three meshes.

For every case, half and measure (layers stacked along Z) the peak of the finest mesh is located; then on each mesh
the largest value within 1.5 mm of that place, and the mean within 1 mm and within 2 mm with their node counts
(05-fea.md: a value that recovers within 1 mm on a few nodes is a corner; one that holds over 2 mm is the section).
"""
import json

import numpy as np
from scipy.spatial import cKDTree

from common import HERE, WIP
from d2_post import A6, classify

TAGS = [t for t in ('c', 'm', 'f') if (WIP / f'd2_Y300_{t}.npz').exists()]
ALLOW = dict(vm=45.0, layer=22.5, shear=13.0)


def fields(S):
    vm = np.sqrt(np.einsum('ni,ij,nj->n', S, A6, S))
    return dict(vm=vm, layer=S[:, 2], shear=np.hypot(S[:, 4], S[:, 5]))


out = {}
for case in ('Y300', 'X300'):
    data = {}
    for t in TAGS:
        z = np.load(WIP / f'd2_{case}_{t}.npz')
        p = z['pos']
        lab, which, near = classify(p)
        data[t] = (p, fields(z['s'][:, 1:7]), lab, near | (p[:, 1] < -29.0), int(len(p)))
    fine = TAGS[-1]
    for half in ('upper', 'lower'):
        for key in ('vm', 'layer', 'shear'):
            p, f, lab, bad, _ = data[fine]
            m = (lab == half) & ~bad
            i = np.flatnonzero(m)[np.argmax(f[key][m])]
            at = p[i]
            rows = []
            for t in TAGS:
                p, f, lab, bad, n = data[t]
                m = (lab == half) & ~bad
                tree = cKDTree(p[m])
                v = f[key][m]
                near15, near1, near2 = (tree.query_ball_point(at, r) for r in (1.5, 1.0, 2.0))
                rows.append(dict(mesh=t, nodes=n, peak_within_1p5mm=round(float(v[near15].max()), 2) if near15 else None,
                                 mean_within_1mm=[round(float(v[near1].mean()), 2), len(near1)] if near1 else None,
                                 mean_within_2mm=[round(float(v[near2].mean()), 2), len(near2)] if near2 else None,
                                 peak_anywhere=round(float(v.max()), 2)))
            last = [r['peak_within_1p5mm'] for r in rows]
            step = abs(last[-1] - last[-2]) / last[-2] if len(last) > 1 and last[-2] else None
            out[f'{case} {half} {key}'] = dict(at=at.round(2).tolist(), rows=rows, last_step=round(step, 3) if step is not None else None,
                                               converged=bool(step is not None and step <= 0.05),
                                               sf_at_finest_peak=round(ALLOW[key] / rows[-1]['peak_anywhere'], 2),
                                               sf_on_2mm_mean=round(ALLOW[key] / max(rows[-1]['mean_within_2mm'][0], 1e-9), 1))
(HERE / 'd2_corner.json').write_text(json.dumps(out, indent=1))
for k, v in out.items():
    print(k, v['at'], [(r['mesh'], r['peak_within_1p5mm'], r['mean_within_1mm'], r['mean_within_2mm']) for r in v['rows']], 'last step', v['last_step'], 'sf', v['sf_at_finest_peak'])
