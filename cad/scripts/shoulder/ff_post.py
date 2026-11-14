"""Fork front alone (FF_* cases), today's part against a look build, like for like: per region the safety factors on
von Mises (45 MPa) and on layer tension (sigma_y against 22.5 MPa: the part prints Y up), at the peak node and for the
worst 0.5 mm ball among the region's 300 highest nodes (the read-out of record), and the deflections the run logged.

    python ff_post.py today yoke        (reads cad/_sim/shoulder/FF_<case>_<rev>.npz and cad/_wip/shoulder-pass1/FF_<rev>.txt)

Regions: head and neck (Y 392 up: the cheek above the wrap, with the boss root); lower cheek and wrap (Y 362-392); sleeve
(below Y 362). Nodes within 4 mm of the fixed boss face or of a loaded face (the RS02 seat and its screw holes; for
FF_STOP the joint face and its insert bores) are left out: the rigid load and the fixture make their own peaks there.
FF_STOP is read for both signs of the torque (the model is linear): layer tension is the larger of +-sigma_y.
"""
import ast
import json
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
from dims import JZ0, ROLL_OUT, RX, RY, SEAT_Y, YZ
from swk import WIP

CASES = ('FF_MX', 'FF_MXn', 'FF_MXb', 'FF_MXnb', 'FF_MZ', 'FF_SIDE', 'FF_STOPM')
L, B = FS.YIELD * FS.LAYER, FS.YIELD


def read(case, rev):
    z = np.load(str(FS.F / f'{case}_{rev}.npz'))
    pos, s = z['pos'], z['s']
    rr = np.hypot(pos[:, 0] - RX, pos[:, 1] - RY)
    ry = np.hypot(pos[:, 0] - RX, pos[:, 2] - YZ)
    keep = ~((pos[:, 2] < ROLL_OUT + 4.0) & (rr < 23.0))
    if case.endswith('b'):       # the joint face is a support in these
        keep &= ~(pos[:, 2] < JZ0 + 4.0)
    if case.startswith('FF_STOP'):
        keep &= ~((pos[:, 2] < JZ0 + 4.0) | ((pos[:, 2] < JZ0 + 16.0) & (pos[:, 1] > 338.0) & (pos[:, 1] < 366.0) & (np.abs(pos[:, 0] - RX) < 36.0) & (pos[:, 2] < YZ - 30.0)))
    else:
        keep &= ~((np.abs(pos[:, 1] - SEAT_Y[0]) < 4.0) & (ry < 46.0)) & ~((pos[:, 1] > SEAT_Y[0] - 6.0) & (pos[:, 1] < SEAT_Y[1] + 4.0) & (np.abs(ry - 36.5) < 5.5))
    return pos[keep], s[keep]


def regions(pos):
    y = pos[:, 1]
    return {'head and neck (Y 392 up)': y >= 392.0, 'lower cheek and wrap (Y 362-392)': (y >= 362.0) & (y < 392.0), 'sleeve (below Y 362)': y < 362.0}


def worst(pos, tree, v, mk):
    idx = np.flatnonzero(mk)
    top = idx[np.argsort(v[idx])[-300:]]
    b05 = np.array([v[tree.query_ball_point(pos[i], 0.5)].mean() for i in top])
    w = top[int(np.argmax(b05))]
    return float(v[top].max()), float(b05.max()), pos[w]


def logged(rev):
    out = {}
    case = None
    for ln in (WIP / f'FF_{rev}.txt').read_text(errors='replace').splitlines():
        if ln.startswith('FF_') and ' study ' in ln:
            case = ln.split()[0]
        if ln.startswith(' extra ') and case:
            out[case] = ast.literal_eval(ln[7:])
        if ln.startswith(' mesh ') and case and 'nodes' in ln:
            out.setdefault('mesh', ln.strip())
    return out


def main(revs):
    res = {}
    for rev in revs:
        lg = logged(rev)
        res[rev] = dict(mesh=lg.get('mesh'))
        for case in CASES:
            try:
                pos, s = read(case, rev)
            except FileNotFoundError:
                continue
            tree = cKDTree(pos)
            vm = s[:, 10]
            ly = np.abs(s[:, 2]) if case.startswith('FF_STOP') else np.maximum(s[:, 2], 0.0)
            row = {}
            for nm, mk in regions(pos).items():
                pv, bv, wv = worst(pos, tree, vm, mk)
                pl_, bl, wl = worst(pos, tree, ly, mk)
                row[nm] = dict(vm_peak=round(B / pv, 2), vm_05=round(B / bv, 2), vm_at=[round(float(wv[0] - RX), 1), round(float(wv[1]), 1), round(float(wv[2]), 1)],
                               layer_peak=round(L / max(pl_, 1e-9), 2), layer_05=round(L / max(bl, 1e-9), 2), layer_at=[round(float(wl[0] - RX), 1), round(float(wl[1]), 1), round(float(wl[2]), 1)])
            ex = lg.get(case, {})
            row['u_max'] = ex.get('u_max')
            row['u_seat'] = ex.get('u_rs02_seat')
            row['R_boss'] = ex.get('R_boss')
            res[rev][case] = row
    (WIP / 'ff_post.json').write_text(json.dumps(res, indent=1))
    for case in CASES:
        print('==', case)
        for rev in revs:
            row = res[rev].get(case)
            if not row:
                continue
            print(f'  {rev}: u_max {row["u_max"]} mm, seat mean (ux, uy, uz, |u|, n) {row["u_seat"]}')
            for nm in regions(np.zeros((1, 3))):
                q = row[nm]
                print(f'     {nm:34s} vM {q["vm_peak"]:6.2f} / {q["vm_05"]:6.2f} at {q["vm_at"]} | layer {q["layer_peak"]:6.2f} / {q["layer_05"]:6.2f} at {q["layer_at"]}')


if __name__ == '__main__':
    main(sys.argv[1:] or ['today', 'yoke'])
