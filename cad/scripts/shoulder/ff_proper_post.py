"""Read-out of the proper neck check of the fork front (fea_shoulder.py P_* and F2_* cases; run by
cad/_wip/shoulder-pass1/run_p.sh on the analysis builds ffT, ffTS, ffYS).

    python ff_proper_post.py [TAG ...]        (default: ffT ffTS ffYS)

Per build and case: safety factors on von Mises (45 MPa) and on layer tension (sigma_y against 22.5 MPa; the part
prints Y up), peak node / worst 0.5 mm ball among the region's 300 highest nodes, and where the ball is (X offset from
the yaw axis, Y, Z). Regions:
  boss root     within r 29 of the roll axis, Z 33 to 41 (the boss's root on the cheek's back face, and the cone)
  head and neck Y 392 up, Z 30 up, the boss root excluded
  lower cheek   Y 362 to 392, Z 20 up
  sleeve        below Y 362
  rear leg      (F2 only) Z under -30, Y over 362
Left out: nodes within 4 mm of a fixed or loaded face (the boss face, the RS02 seat and its screw holes, the 6808 seat, the
screw-head seats and pin holes in the 's' cases, the tooth flank in F2_STOP).
Writes cad/_wip/shoulder-pass1/ff_proper.json and prints one line per build, case and region.
"""
import ast
import json
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

import fea_shoulder as FS
from dims import CAP_FLOOR, ROLL_OUT, RX, RY, SEAT_Y, YZ
from swk import WIP

CASES = ('P_MXb', 'P_MXnb', 'P_MXbs', 'P_MX', 'P_MXn', 'P_MZ', 'F2_MX', 'F2_MXn', 'F2_MXs', 'F2_MZ', 'F2_STOP')
L, B = FS.YIELD * FS.LAYER, FS.YIELD
JZ0 = FS.JZ0


def read(case, tag):
    z = np.load(str(FS.F / f'{case}_{tag}.npz'))
    pos, s = z['pos'], z['s']
    x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2]
    rr = np.hypot(x, y - RY)
    ry = np.hypot(x, zz - YZ)
    keep = ~((zz < ROLL_OUT + 4.0) & (rr < 23.0))
    if case != 'F2_STOP':
        keep &= ~((np.abs(y - SEAT_Y[0]) < 4.0) & (ry < 46.0)) & ~((y > SEAT_Y[0] - 6.0) & (y < SEAT_Y[1] + 4.0) & (np.abs(ry - 36.5) < 5.5))
    if case.startswith('F2'):
        keep &= ~((rr < 30.5) & (zz < -36.0))                               # the 6808 seat
    if case == 'F2_STOP':
        keep &= ~((zz < -28.0) & (rr > 24.0) & (rr < 46.0) & (y < RY - 18.0))   # the tooth
    if case.startswith('P_') and 'b' in case:
        keep &= ~(zz < JZ0 + 4.0)                                            # the joint face is a support
    if case.endswith('s'):
        for k in range(6):                                                   # screw-head seats and the pin holes
            a = math.radians(30.0 + 60.0 * k)
            keep &= ~((np.hypot(x - 15.2 * math.cos(a), y - RY - 15.2 * math.sin(a)) < 8.0) & (zz > CAP_FLOOR - 6.0))
        for k in range(3):
            a = math.radians(120.0 * k)
            keep &= ~((np.hypot(x - 15.2 * math.cos(a), y - RY - 15.2 * math.sin(a)) < 5.5) & (zz < ROLL_OUT + 13.0))
    return pos[keep], s[keep]


def regions(pos, f2):
    x, y, z = pos[:, 0] - RX, pos[:, 1], pos[:, 2]
    rr = np.hypot(x, y - RY)
    root = (rr < 29.0) & (z > 33.0) & (z < 41.0)
    out = {'boss root': root, 'head and neck': (y >= 392.0) & (z >= 30.0) & ~root, 'lower cheek': (y >= 362.0) & (y < 392.0) & (z >= 20.0), 'sleeve': y < 362.0}
    if f2:
        out['rear leg'] = (z < -30.0) & (y >= 362.0)
    return out


def worst(pos, tree, v, mk):
    idx = np.flatnonzero(mk)
    if not len(idx):
        return None
    top = idx[np.argsort(v[idx])[-300:]]
    b05 = np.array([v[tree.query_ball_point(pos[i], 0.5)].mean() for i in top])
    w = top[int(np.argmax(b05))]
    return float(v[top].max()), float(b05.max()), [round(float(pos[w][0] - RX), 1), round(float(pos[w][1]), 1), round(float(pos[w][2]), 1)]


def logged(tag):
    out, case = {}, None
    text = chr(10).join((WIP / f'{k}_{tag}.txt').read_text(errors='replace') for k in ('P', 'F') if (WIP / f'{k}_{tag}.txt').exists())
    for ln in text.splitlines():
        if (ln.startswith('P_') or ln.startswith('F2_')) and ' study ' in ln:
            case = ln.split()[0]
        if ln.startswith(' extra ') and case:
            try:
                out[case] = ast.literal_eval(ln[7:])
            except Exception:
                pass
        if ln.startswith(' mesh ') and case and 'nodes' in ln:
            out[case + '_mesh'] = ln.strip()
    return out


def main(tags):
    res = {}
    for tag in tags:
        lg = logged(tag)
        res[tag] = {}
        for case in CASES:
            try:
                pos, s = read(case, tag)
            except FileNotFoundError:
                continue
            tree = cKDTree(pos)
            vm = s[:, 10]
            ly = np.abs(s[:, 2]) if case == 'F2_STOP' else np.maximum(s[:, 2], 0.0)       # the stop acts either way
            row = dict(mesh=lg.get(case + '_mesh'), u_max=lg.get(case, {}).get('u_max'), u_seat=lg.get(case, {}).get('u_rs02_seat'))
            for nm, mk in regions(pos, case.startswith('F2')).items():
                a, b = worst(pos, tree, vm, mk), worst(pos, tree, ly, mk)
                if a is None:
                    continue
                row[nm] = dict(vm_peak=round(B / a[0], 2), vm_05=round(B / a[1], 2), vm_at=a[2], layer_peak=round(L / max(b[0], 1e-9), 2), layer_05=round(L / max(b[1], 1e-9), 2), layer_at=b[2])
            res[tag][case] = row
    (WIP / 'ff_proper.json').write_text(json.dumps(res, indent=1))
    for case in CASES:
        print('==', case)
        for tag in tags:
            row = res[tag].get(case)
            if not row:
                continue
            print(f'  {tag}: {row["mesh"]}; u_max {row["u_max"]}, seat {row["u_seat"]}')
            for nm in ('boss root', 'head and neck', 'lower cheek', 'sleeve', 'rear leg'):
                if nm in row:
                    q = row[nm]
                    print(f'     {nm:14s} vM {q["vm_peak"]:6.2f} / {q["vm_05"]:6.2f} at {q["vm_at"]} | layer {q["layer_peak"]:6.2f} / {q["layer_05"]:6.2f} at {q["layer_at"]}')


if __name__ == '__main__':
    main(sys.argv[1:] or ['ffT', 'ffTS', 'ffYS'])
