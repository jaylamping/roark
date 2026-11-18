"""Like-for-like post-processing of HUBL_STOP2 on rev D / D2 / D2b (cad/_sim/shoulder/HUBL_STOP2_<tag>.npz).
Cylindrical regions about the yaw axis; for each: layer (sigma_y, tensile part) and bulk (von Mises) SF at the peak node
and averaged over the nodes within 0.5 and 1.0 mm of it, plus the across-layer shear sqrt(txy^2 + tyz^2) in MPa (peak and
0.5 mm average). python hub_stop2_post.py TAG [TAG...]"""
import json
import sys

import numpy as np

import fea_shoulder as FS

RX, YZ = FS.RX, FS.YZ
YIELD, LAYER = FS.YIELD, FS.LAYER


def regions(pos):
    x, y, z = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - YZ
    r = np.hypot(x, z)
    root = (y > 294.4) & (y < 296.7) & (r > 18.0) & (r < 31.6)
    return {
        'lugA_root_Zp (-X lug, +Z)': root & (x < 0) & (z > 4.8) & (z < 6.6),
        'lugA_root_Zm (-X lug, -Z)': root & (x < 0) & (z < -4.8) & (z > -6.6),
        'lugB_root_Zp (+X lug, +Z)': root & (x > 0) & (z > 4.8) & (z < 6.6),
        'lugB_root_Zm (+X lug, -Z)': root & (x > 0) & (z < -4.8) & (z > -6.6),
        'groove_bottom (r 33.9-34.8, Y 298.3-301.3)': (r > 33.9) & (r < 34.8) & (y > 298.3) & (y < 301.3),
        'spigot_core (r < 33.8, Y 296.3-302)': (r < 33.8) & (r > 18.0) & (y > 296.3) & (y < 302.0),
        'land (r 34-35.9, Y 296-298.2)': (r > 34.0) & (r < 35.9) & (y > 295.95) & (y < 298.2),
        'lug_A whole': (x < 0) & (np.abs(z) < 7) & (y < 297.0) & (r < 32),
        'lug_B whole': (x > 0) & (np.abs(z) < 7) & (y < 297.0) & (r < 32),
    }


def post(tag):
    z_ = np.load(str(FS.F / ((tag if tag.startswith('HUBL_') else f'HUBL_STOP2_{tag}') + '.npz')))
    pos, s = z_['pos'], z_['s']
    vm, sy = s[:, 10], s[:, 2]
    syp = np.maximum(sy, 0.0)
    tau = np.hypot(s[:, 4], s[:, 6])   # across the layers (normal Y): txy, tyz (columns: node, sx, sy, sz, txy, txz, tyz, p1, p2, p3, vm)
    out = {'nodes': int(len(pos))}
    for k, mk in regions(pos).items():
        if not mk.any():
            continue
        idx = np.flatnonzero(mk)
        il, iv, it = idx[np.argmax(sy[mk])], idx[np.argmax(vm[mk])], idx[np.argmax(tau[mk])]
        row = dict(layer=round(YIELD * LAYER / max(sy[il], 1e-9), 2), layer_at=pos[il].round(2).tolist(), sy=round(float(sy[il]), 1),
                   bulk=round(YIELD / vm[iv], 2), tau=round(float(tau[it]), 1), tau_at=pos[it].round(2).tolist())
        for rad in (0.5, 1.0):
            nl = np.linalg.norm(pos - pos[il], axis=1) <= rad
            nv = np.linalg.norm(pos - pos[iv], axis=1) <= rad
            row[f'layer_{rad}'] = round(YIELD * LAYER / max(syp[nl].mean(), 1e-9), 2)
            row[f'bulk_{rad}'] = round(YIELD / vm[nv].mean(), 2)
            row[f'n_{rad}'] = int(nl.sum())
        nt = np.linalg.norm(pos - pos[it], axis=1) <= 0.5
        row['tau_0.5'] = round(float(tau[nt].mean()), 1)
        out[k] = row
    return out


if __name__ == '__main__':
    res = {t: post(t) for t in sys.argv[1:]}
    for t, rows in res.items():
        print(f'== {t}  nodes {rows["nodes"]}')
        for k, r in rows.items():
            if k == 'nodes':
                continue
            print(f"  {k:44s} layer {r['layer']:5.2f} / {r['layer_0.5']:5.2f} / {r['layer_1.0']:5.2f} (sy {r['sy']:5.1f} at {r['layer_at']})"
                  f"   bulk {r['bulk']:5.2f} / {r['bulk_0.5']:5.2f} / {r['bulk_1.0']:5.2f}   tau {r['tau']:5.1f} / {r['tau_0.5']:5.1f} MPa")
    p = FS.F / 'hub_stop2_post.json'
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(res)
    p.write_text(json.dumps(old, indent=1))
