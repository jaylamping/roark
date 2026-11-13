"""D2: read the nodal results d2_fea.py saved and work out what the report needs. Numpy only.

    python d2_post.py <tag>

Nodes are given to a body by geometry, with a margin at every interface (05-fea.md, contact rule 5); a node that fits
no body, or two, stops the script.
"""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from common import HERE, WIP

tag = sys.argv[1] if __name__ == '__main__' else ''
SCREWS = [(sx * 31.0, z) for sx in (1, -1) for z in (0.0, 7.0)]
A_SHANK = np.pi * 1.5 ** 2
ALLOW = dict(vm=45.0, layer=22.5, shear=13.0)
A6 = np.zeros((6, 6))
A6[:3, :3] = [[1, -.5, -.5], [-.5, 1, -.5], [-.5, -.5, 1]]
A6[3:, 3:] = 3 * np.eye(3)


def classify(p):
    x, y, z = p.T
    r = np.hypot(x, y)
    lab = np.full(len(p), '', dtype='U8')
    near_bond = np.zeros(len(p), bool)        # plastic within 1 mm of a bonded steel face (head seat, insert wall)
    ring = (r >= 23.99) & (r <= 26.02) & (z >= -0.01) & (z <= 7.01)
    plug = (r < 23.99) & (z >= 2.49) & (z <= 4.51)
    screw = np.zeros(len(p), bool)
    which = np.full(len(p), -1)
    for k, (xs, zs) in enumerate(SCREWS):
        dd = np.hypot(x - xs, z - zs)
        m = ((dd <= 1.51) & (y > -0.41) & (y < 28.51)) | ((dd <= 2.76) & (y >= 28.49) & (y <= 31.51)) | ((dd <= 2.01) & (y >= -6.41) & (y <= -0.39))
        screw |= m
        which[m] = k
        near_bond |= ((dd <= 3.75) & (np.abs(y - 28.5) <= 1.0)) | ((dd <= 3.0) & (y >= -7.4) & (y <= -0.39))
    lab[ring] = 'ring'
    lab[plug] = 'plug'
    if (screw & (ring | plug)).any():
        raise SystemExit('a node is in a screw and in the ring')
    lab[screw] = 'screw'
    rest = lab == ''
    lab[rest & (y >= 0.39)] = 'upper'
    lab[rest & (y <= -0.39)] = 'lower'
    if (lab == '').any():
        raise SystemExit(f'{(lab == "").sum()} nodes fit no body: {p[lab == ""][:5]}')
    return lab, which, near_bond


def measures(S, n, mask, pos):
    n = np.array(n, float)
    vm = np.sqrt(np.einsum('ni,ij,nj->n', S, A6, S))
    sn = n[0] ** 2 * S[:, 0] + n[1] ** 2 * S[:, 1] + n[2] ** 2 * S[:, 2] + 2 * (n[0] * n[1] * S[:, 3] + n[0] * n[2] * S[:, 4] + n[1] * n[2] * S[:, 5])
    t = np.c_[S[:, 0] * n[0] + S[:, 3] * n[1] + S[:, 4] * n[2], S[:, 3] * n[0] + S[:, 1] * n[1] + S[:, 5] * n[2],
              S[:, 4] * n[0] + S[:, 5] * n[1] + S[:, 2] * n[2]]
    tau = np.linalg.norm(t - np.outer(t @ n, n), axis=1)
    res = {}
    for key, v in (('vm', vm), ('layer', sn), ('shear', tau)):
        i = np.flatnonzero(mask)[np.argmax(v[mask])]
        res[key] = dict(mpa=round(float(v[i]), 2), at=pos[i].round(2).tolist(), sf=round(ALLOW[key] / max(float(v[i]), 1e-9), 2))
    return res


def one(case):
    z = np.load(WIP / f'd2_{case}_{tag}.npz')
    p, s, disp, reac = z['pos'], z['s'], z['disp'], z['reac']
    lab, which, near_bond = classify(p)
    S = s[:, 1:7]
    out = dict(nodes=len(p), el=float(z['el']), seat_ctrl=float(z['cs']), bodies={k: int((lab == k).sum()) for k in ('upper', 'lower', 'ring', 'plug', 'screw')})
    # reactions: the mounting face against the plug's hub
    ids = {int(i): k for k, i in enumerate(s[:, 0])}
    rp = np.array([p[ids[int(i)]] for i in reac[:, 0]])
    live = np.abs(reac[:, 1:4]).sum(axis=1) > 0
    hubn = live & (np.hypot(rp[:, 0], rp[:, 1]) < 3.5)
    out['reaction_face_N'] = reac[live & ~hubn, 1:4].sum(axis=0).round(3).tolist()
    out['reaction_hub_N'] = reac[hubn, 1:4].sum(axis=0).round(4).tolist()
    # the ring as a rigid body
    rm = lab == 'ring'
    out['ring_moves_mm'] = disp[rm, 1:4].mean(axis=0).round(4).tolist()
    out['max_disp_mm'] = dict(upper=round(float(disp[lab == 'upper', 4].max()), 4), lower=round(float(disp[lab == 'lower', 4].max()), 4))
    # screws: a plane fitted to the stress over the shank between Y 5 and Y 24 gives the stress at the axis; times the area
    scr = []
    for k, (xs, zs) in enumerate(SCREWS):
        m = (which == k) & (p[:, 1] > 5) & (p[:, 1] < 24) & (np.hypot(p[:, 0] - xs, p[:, 2] - zs) <= 1.51)
        G = np.c_[np.ones(m.sum()), p[m, 0] - xs, p[m, 2] - zs]
        row = dict(x=xs, z=zs, nodes=int(m.sum()))
        for name, col in (('tension_N', 1), ('shear_x_N', 3), ('shear_z_N', 5)):
            row[name] = round(float(np.linalg.lstsq(G, S[m, col], rcond=None)[0][0] * A_SHANK), 2)
        # check on the method: the same fit in three slices along the shank must agree
        sl = []
        for y0, y1 in ((5, 11), (11, 18), (18, 24)):
            mm = m & (p[:, 1] > y0) & (p[:, 1] < y1)
            sl.append(round(float(np.linalg.lstsq(np.c_[np.ones(mm.sum()), p[mm, 0] - xs, p[mm, 2] - zs], S[mm, 1], rcond=None)[0][0] * A_SHANK), 2))
        row['tension_in_three_slices_N'] = sl
        scr.append(row)
    out['screws'] = scr
    out['screw_sum_N'] = dict(tension=round(sum(r['tension_N'] for r in scr), 2), shear_x=round(sum(r['shear_x_N'] for r in scr), 2))
    # the two halves: three measures for each way the layers could be stacked
    fixed_face = p[:, 1] < -32 + 3.0
    for half in ('upper', 'lower'):
        base = lab == half
        keep = base & ~near_bond & ~fixed_face
        h = dict(excluded=dict(within_1mm_of_bonded_steel=int((base & near_bond).sum()), within_3mm_of_fixed_face=int((base & fixed_face).sum()),
                               vm_max_at_bonded_steel=round(float(s[base & near_bond, 10].max()), 2) if (base & near_bond).any() else None,
                               vm_max_at_fixed_face=round(float(s[base & fixed_face, 10].max()), 2) if (base & fixed_face).any() else None))
        for label, n in (('layers_Z', (0, 0, 1)), ('layers_Y', (0, 1, 0)), ('layers_X', (1, 0, 0))):
            h[label] = measures(S, n, keep, p)
        out[half] = h
    # plain section, upper half at the crown: sx on the outer face and at the seat, mid width
    t = cKDTree(p)
    for name, at in (('crown_outer_sx', (0, 32.0, 3.5)), ('crown_seat_sx', (0, 26.075, 3.5)), ('crown_shoulder_edge_sx', (0, 24.5, 9.0))):
        idx = t.query_ball_point(at, 1.5)
        idx = [i for i in idx if lab[i] == 'upper' and abs(p[i, 1] - at[1]) < 0.05]
        out[name] = [round(float(s[idx, 1].mean()), 2), len(idx)] if idx else None
    # where the ring bears: seat nodes of each half with compressive radial stress over 1 MPa, as an angle from +X
    sr = []
    for half in ('upper', 'lower'):
        m = (lab == half) & (np.abs(np.hypot(p[:, 0], p[:, 1]) - 26.075) < 0.02) & (p[:, 2] > 0) & (p[:, 2] < 7)
        th = np.arctan2(p[m, 1], p[m, 0])
        srr = (np.cos(th) ** 2 * S[m, 0] + np.sin(th) ** 2 * S[m, 1] + 2 * np.sin(th) * np.cos(th) * S[m, 3])
        on = srr < -1.0
        sr.append(dict(half=half, seat_nodes=int(m.sum()), bearing_nodes=int(on.sum()),
                       bearing_angle_deg=[round(float(np.degrees(th[on]).min()), 1), round(float(np.degrees(th[on]).max()), 1)] if on.any() else None,
                       peak_pressure_mpa=round(float(-srr.min()), 2)))
    out['seat_contact'] = sr
    return out


if __name__ == '__main__':
    res = {}
    for case in ('Y300', 'X300', 'Y1', 'X1'):
        if (WIP / f'd2_{case}_{tag}.npz').exists():
            res[case] = one(case)
    (HERE / f'd2_post_{tag}.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
