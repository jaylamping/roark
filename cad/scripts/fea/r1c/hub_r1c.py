"""R1c hub-seat post-processing (ridge in the arm bore, groove in the hub spigot, bolted lugs). Classifies nodes against the
GROOVED hub mesh (HUB_GROOVE.STL from hub_seat.py build), so the arm's ridge (which sits inside today's spigot volume) stays arm.
Frame: hub axis Y, r from (HX, CZ), theta from +X toward +Z. Arm layer = sigma z (halves print on the seam), hub layer = sigma y
(hub prints RS02 side down, spigot up). Peaks with nothing excluded, plus 0.5/1/2 mm sphere averages (same body's nodes).
    python hub_r1c.py NPZ [HUB_STL]          prints a table and writes NPZ.r1c.json"""
import json, sys
import numpy as np, trimesh
from scipy.spatial import cKDTree
HX, CZ = 170.49, 5.985875
BOLT_X, BOLT_Y = (147.5, 193.5), 292.0
npz = sys.argv[1]
hubp = sys.argv[2] if len(sys.argv) > 2 else 'J:/code/roark-wt/left-arm-organic/cad/_sim/ua2/HUB_GROOVE.STL'
d = np.load(npz); p, s = d['pos'], d['s']; vm = s[:, 10]
hub = trimesh.load(hubp)
if hub.bounds[1][1] < 1.0:          # exported in metres
    hub.apply_scale(1000.0)
out = {}
rb_all = np.min([np.hypot(p[:, 0] - x0, p[:, 1] - BOLT_Y) for x0 in BOLT_X], axis=0)
near = np.flatnonzero((p[:, 1] > 265) & np.all((p >= hub.bounds[0] - 0.5) & (p <= hub.bounds[1] + 0.5), axis=1))
# chunked (one call on ~300k points took ~8 GB on 2026-11-11): 20k points at a time
sd = np.concatenate([trimesh.proximity.signed_distance(hub, p[near[i:i + 20000]]).astype(np.float32) for i in range(0, len(near), 20000)])        # + inside
in_hub = np.zeros(len(p), bool); in_hub[near[sd > -0.03]] = True
bolt = (rb_all < 1.6) & (np.abs(p[:, 2] - CZ) < 46)
arm = np.flatnonzero(~in_hub & ~bolt); hb = np.flatnonzero(in_hub & ~bolt); bl = np.flatnonzero(bolt)
r = np.hypot(p[:, 0] - HX, p[:, 2] - CZ); y = p[:, 1]; th = np.degrees(np.arctan2(p[:, 2] - CZ, p[:, 0] - HX)) % 360
ridge_arc = ((th > 33) & (th < 147)) | ((th > 213) & (th < 327))
groove_arc = ((th > 18) & (th < 162)) | ((th > 198) & (th < 342))
posts = (np.abs(p[:, 0] - 147.5) < 7) | (np.abs(p[:, 0] - 193.5) < 7)
trees = {'arm': (arm, cKDTree(p[arm])), 'hub': (hb, cKDTree(p[hb]))}


def rep(body, name, mask, layer_col, allow_layer=22.5):
    ids, tree = trees[body]
    a = ids[mask[ids]]
    row = {'nodes': int(len(a))}
    if len(a) == 0:
        print(f'{body:3s} {name}: no nodes'); out[f'{body}: {name}'] = row; return
    for lab, v, al in (('vm', vm, 45.0), ('layer', s[:, layer_col], allow_layer)):
        i = a[np.argmax(v[a])]
        av = [float(v[ids[tree.query_ball_point(p[i], rr)]].mean()) for rr in (0.5, 1.0, 2.0)]
        row[lab] = dict(peak=round(float(v[i]), 1), sf=round(al / v[i], 2) if v[i] > 0 else None, avg=[round(x, 1) for x in av],
                        sf_avg=[round(al / x, 2) if x > 0 else None for x in av], at=p[i].round(1).tolist(),
                        r=round(float(r[i]), 2), theta=round(float(th[i]), 1))
        print(f'{body:3s} {name:44s} {lab:5s} peak {v[i]:6.1f} SF {al / v[i] if v[i] > 0 else 0:5.2f} | avg .5/1/2 {av[0]:5.1f}/{av[1]:5.1f}/{av[2]:5.1f} '
              f'SF {al / av[0] if av[0] > 0 else 0:4.2f}/{al / av[1] if av[1] > 0 else 0:4.2f}/{al / av[2] if av[2] > 0 else 0:4.2f} at {p[i].round(1).tolist()} r {r[i]:.2f} th {th[i]:.0f}')
    out[f'{body}: {name}'] = row


ALL = np.ones(len(p), bool)
print(f'nodes: arm {len(arm)}, hub {len(hb)}, bolts {len(bl)}')
# arm side (layer = sigma z, column 3)
rep('arm', 'WHOLE ARM (nothing excluded)', ALL, 3)
rep('arm', 'ridge body (r < 35.9, Y 297.5-302)', ridge_arc & (r < 35.9) & (y > 297.5) & (y < 302.05), 3)
rep('arm', 'ridge root / bore wall (r 35.9-37.5, Y 297.5-302)', ridge_arc & (r >= 35.9) & (r < 37.5) & (y > 297.5) & (y < 302.05), 3)
rep('arm', 'seat bore + end face elsewhere (Y 295-302.6, r<38)', ~(ridge_arc & (y > 297.5) & (y < 302.05) & (r < 37.5)) & (y > 295) & (y < 302.6) & (r < 38) & (r > 33), 3)
rep('arm', 'hub posts (Y 285-296)', posts & (y > 285) & (y < 296), 3)
rep('arm', 'fins (Y 270-285, posts)', posts & (y > 270) & (y <= 285), 3)
rep('arm', 'skin elsewhere (Y 270-296)', ~posts & (y > 270) & (y < 296), 3)
# hub side (layer = sigma y, column 2)
rep('hub', 'WHOLE HUB (nothing excluded)', ALL, 2)
rep('hub', 'load flank (Y 297.8-299.1, r 34.2-35.85, arcs)', groove_arc & (y > 297.8) & (y < 299.1) & (r > 34.2) & (r < 35.85), 2)
rep('hub', 'groove bottom + 45 flank (Y 299.1-302, arcs)', groove_arc & (y >= 299.1) & (y < 302.0) & (r > 34.0) & (r < 35.85), 2)
rep('hub', '2 mm land (Y 295.5-298, r 33-35.85)', (y > 295.5) & (y < 298.0) & (r > 33) & (r < 35.85), 2)
rep('hub', 'spigot ring above groove (Y 300.5-302.2, r 31-34.3)', (y > 300.5) & (y < 302.2) & (r > 31) & (r < 34.3), 2)
rep('hub', 'spigot core behind groove (Y 297.5-301, r 31-34.3)', (y > 297.5) & (y <= 300.5) & (r > 31) & (r < 34.3), 2)
lugs = ((p[:, 0] < 152.5) | (p[:, 0] > 188.5)) & (np.abs(p[:, 2] - CZ) < 6.5) & (y < 297.5)
rep('hub', 'lugs incl. roots (Y < 297.5)', lugs, 2)
rep('hub', 'lug roots (Y 294-297.5)', lugs & (y > 294), 2)
if len(bl):
    i = bl[np.argmax(vm[bl])]; out['bolts'] = dict(vm_peak=round(float(vm[i]), 0), at=p[i].round(1).tolist(), sf_vs_640=round(640.0 / vm[i], 2))
    print(f'bolts: vm peak {vm[i]:.0f} MPa at {p[i].round(1).tolist()} (SF vs 640 MPa yield {640.0 / vm[i]:.2f})')
# lug forces: slab across each lug just below the root, hub nodes only
for name, (x0, x1) in (('lug -X', (141.0, 151.75)), ('lug +X', (189.25, 200.0))):
    m = in_hub & ~bolt & (y > 294.5) & (y < 295.5) & (p[:, 0] > x0 + 0.2) & (p[:, 0] < x1 - 0.2) & (p[:, 2] > 1.2) & (p[:, 2] < 10.8)
    idx = np.flatnonzero(m)
    if len(idx) == 0:
        print(name, 'no nodes'); continue
    A = (x1 - x0) * 10.0
    fy, fx, fz = s[idx, 2].mean() * A, s[idx, 4].mean() * A, s[idx, 6].mean() * A
    out[name] = dict(nodes=int(len(idx)), Fy_axial=round(float(fy)), Fx_shear=round(float(fx)), Fz_shear=round(float(fz)))
    print(f'{name}: nodes {len(idx)}, axial Fy ~ {fy:7.0f} N, shear Fx ~ {fx:6.0f} N, shear Fz ~ {fz:6.0f} N (section {A:.0f} mm2)')
json.dump(out, open(npz + '.r1c.json', 'w'), indent=1)
