"""Post-process saved hub FEA nodal results (cad/_sim/shoulder/<case>.npz): per region, bulk (von Mises) and layer
(sigma_y, the hub printed with the yaw axis vertical) safety factors at the peak node and averaged over the nodes within
0.5 and 1.0 mm of that peak. Layer averages use the tensile part only (max(sigma_y, 0)), so nearby compression does not
cancel the peak. python hub_post.py CASE[:NPZ] [...]  (NPZ: a saved copy, e.g. HUBB_B:HUBB_B_revC). Results merge into
cad/_sim/shoulder/hub_post_<HUB_POST_TAG>.json (default revCplus)."""
import os
import json
import sys

import numpy as np

import fea_shoulder as FS

YIELD, LAYER = FS.YIELD, FS.LAYER


def post(case, npz=None):
    z = np.load(str(FS.F / f'{npz or case}.npz'))
    pos, s = z['pos'], z['s']
    vm, sy = s[:, 10], s[:, 2]
    syp = np.maximum(sy, 0.0)
    out = {}
    for k, box in FS.CASES[case]['regions'].items():
        mk = np.all((pos >= np.array(box[:3])) & (pos <= np.array(box[3:])), axis=1)
        if not mk.any():
            continue
        iv = np.flatnonzero(mk)[np.argmax(vm[mk])]
        il = np.flatnonzero(mk)[np.argmax(sy[mk])]
        row = dict(bulk=round(YIELD / vm[iv], 2), bulk_at=pos[iv].round(1).tolist(), layer=round(YIELD * LAYER / max(sy[il], 1e-9), 2), layer_at=pos[il].round(1).tolist())
        for rad in (0.5, 1.0):
            nv = np.linalg.norm(pos - pos[iv], axis=1) <= rad
            nl = np.linalg.norm(pos - pos[il], axis=1) <= rad
            row[f'bulk_{rad}'] = round(YIELD / vm[nv].mean(), 2)
            row[f'layer_{rad}'] = round(YIELD * LAYER / max(syp[nl].mean(), 1e-9), 2)
            row[f'n_{rad}'] = int(nl.sum())
        out[k] = row
    return out


if __name__ == '__main__':
    res = {a_: post(*a_.split(':', 1)) for a_ in sys.argv[1:]}
    for c, rows in res.items():
        print('==', c)
        for k, r in rows.items():
            print(f"  {k:16s} bulk {r['bulk']:5.2f} (0.5 {r['bulk_0.5']:5.2f}, 1.0 {r['bulk_1.0']:5.2f})   layer {r['layer']:5.2f} (0.5 {r['layer_0.5']:5.2f}, 1.0 {r['layer_1.0']:5.2f})   layer at {r['layer_at']}  n0.5 {r['n_0.5']}")
    out_ = FS.F / f"hub_post_{os.environ.get('HUB_POST_TAG', 'revCplus')}.json"
    old_ = json.loads(out_.read_text()) if out_.exists() else {}
    old_.update(res)
    out_.write_text(json.dumps(old_, indent=1))
