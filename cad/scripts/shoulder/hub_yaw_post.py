"""HUBL_YAW post-processing (cad/_sim/shoulder/<npz>.npz): the yaw-torque couple on the two lugs, both directions (linear: the
other direction is -sigma). For each lug, each Z root (Z+ / Z-) and each end (inner r < 25, outer r >= 25): layer SF (sigma_y,
tensile part) as peak / 0.5 mm / 1 mm average at the 17 N.m peak, the 1 mm and 0.5 mm values at the 6 N.m rating, and the
across-layer shear sqrt(txy^2 + tyz^2) peak / 0.5 mm average in MPa. Also the lug section at the bolt hole (Y 290-294) and the
spigot core. python hub_yaw_post.py NPZ [NPZ...]"""
import json
import sys

import numpy as np

import fea_shoulder as FS

RX, YZ = FS.RX, FS.YZ
L = FS.YIELD * FS.LAYER
RATED = 17.0 / 6.0


def post(name):
    z_ = np.load(str(FS.F / f'{name}.npz'))
    pos, s = z_['pos'], z_['s']
    x, y, zz = pos[:, 0] - RX, pos[:, 1], pos[:, 2] - YZ
    r = np.hypot(x, zz)
    tau = np.hypot(s[:, 4], s[:, 6])   # across the layers (normal Y): txy, tyz (columns: node, sx, sy, sz, txy, txz, tyz, p1, p2, p3, vm)
    out = {'nodes': int(len(pos))}
    root = (y > 294.4) & (y < 296.7) & (np.abs(zz) > 4.8) & (np.abs(zz) < 6.6)
    hole = (y > 289.5) & (y < 294.4) & (np.abs(zz) < 5.2) & (r > 18.5) & (r < 30.5)
    core = (r > 18.0) & (r < 33.8) & (y > 296.3) & (y < 302.0)
    for sgn, dname in ((1.0, 'dir +'), (-1.0, 'dir -')):
        sy = sgn * s[:, 2]
        syp = np.maximum(sy, 0.0)
        regs = {}
        for lug, lx in (('-X lug', x < 0), ('+X lug', x > 0)):
            for side, sz in (('Z+', zz > 0), ('Z-', zz < 0)):
                for end, re_ in (('inner', r < 25), ('outer', r >= 25)):
                    regs[f'{lug} {side} root {end}'] = root & lx & sz & re_
            regs[f'{lug} section at the hole'] = hole & lx
            # rev D3: the R0.5 under the step (Y 294.5, X offset 34.4) and the strip outside the land band
            regs[f'{lug} D3 step corner'] = lx & (y > 293.6) & (y < 295.0) & (np.abs(x) > 34.0) & (np.abs(x) < 35.6) & (np.abs(zz) < 5.3)
            regs[f'{lug} D3 strip'] = lx & (y > 296.0) & (y < 297.7) & (np.abs(x) > 35.3) & (np.abs(x) < 36.5) & (np.abs(zz) < 5.3)
        regs['spigot core'] = core
        for k, m in regs.items():
            if not m.any():
                continue
            i = np.flatnonzero(m)[np.argmax(sy[m])]
            if sy[i] <= 0:
                continue
            d_ = np.linalg.norm(pos - pos[i], axis=1)
            n5, n1 = d_ <= 0.5, d_ <= 1.0
            a5, a1 = syp[n5].mean(), syp[n1].mean()
            out[f'{dname} | {k}'] = dict(peak=round(L / sy[i], 2), a05=round(L / a5, 2), a10=round(L / a1, 2),
                                         rated_a05=round(L / a5 * RATED, 2), rated_a10=round(L / a1 * RATED, 2),
                                         tau=round(float(tau[i]), 1), tau05=round(float(tau[n5].mean()), 1), at=pos[i].round(2).tolist(), r=round(float(r[i]), 1))
    # bearing on the lugs' flat Z faces (the shim faces, planes Z 1.0 / 11.0, below Y 294.8): the largest compression across
    # the face (sigma_z, in the layer plane) and its 1 mm average; bulk SF against 45 MPa
    for lug, lx in (('-X lug', x < 0), ('+X lug', x > 0)):
        for zp in (1.0, 11.0):
            m = lx & (np.abs(pos[:, 2] - zp) < 0.05) & (y < 294.8) & (np.abs(x) > 18.5)
            if not m.any():
                continue
            for sgn, dname in ((1.0, 'dir +'), (-1.0, 'dir -')):
                comp = -sgn * s[:, 3]
                i = np.flatnonzero(m)[np.argmax(comp[m])]
                if comp[i] <= 0:
                    continue
                n1 = m & (np.linalg.norm(pos - pos[i], axis=1) <= 1.0)
                out[f'{dname} | {lug} Z {zp:.0f} face bearing'] = dict(bearing=round(float(comp[i]), 1), bearing10=round(float(comp[n1].mean()), 1),
                                                                     bulk_sf=round(FS.YIELD / float(comp[i]), 2), r=round(float(r[i]), 1))
    return out


if __name__ == '__main__':
    res = {n: post(n) for n in sys.argv[1:]}
    for n, rows in res.items():
        print(f'== {n}  nodes {rows["nodes"]}   (layer SF peak / 0.5 / 1.0 at 17 N.m;  rated 6 N.m: 0.5 / 1.0;  tau peak / 0.5 MPa)')
        for k, v in rows.items():
            if k == 'nodes':
                continue
            if 'bearing' in v:
                print(f"  {k:42s} bearing {v['bearing']:5.1f} MPa peak / {v['bearing10']:5.1f} over 1 mm   bulk SF {v['bulk_sf']:5.2f}   r {v['r']}")
                continue
            flag = '  <-- under 1.2 @0.5 or 1.5 @1.0' if (v['a05'] < 1.2 or v['a10'] < 1.5) else ''
            print(f"  {k:42s} {v['peak']:5.2f} / {v['a05']:5.2f} / {v['a10']:5.2f}   rated {v['rated_a05']:5.2f} / {v['rated_a10']:5.2f}   tau {v['tau']:5.1f} / {v['tau05']:5.1f}  r {v['r']}{flag}")
    p = FS.F / 'hub_yaw_post.json'
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(res)
    p.write_text(json.dumps(old, indent=1))
