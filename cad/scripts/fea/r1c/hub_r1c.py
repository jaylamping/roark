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
PAD_PTS = [(147.5, 15.0), (193.5, 15.0), (147.5, -15.0), (193.5, -15.0)]      # hub_seat.py HS_PADS (R1d gap cases)
pad_all = np.zeros(len(p), bool)
for x0, dz in PAD_PTS:
    pad_all |= (np.hypot(p[:, 0] - x0, p[:, 2] - (CZ + dz)) < 0.95) & (p[:, 1] > 295.65) & (p[:, 1] < 296.05)
# Classify by BODY (rewritten 2026-11-12 after a steel bolt node was scored as PETG: the -X bolt sat at the START of the node order
# and the old index-range split counted it as arm). Every node gets a geometric label where it is certain:
#   steel bolt (inside the bolt shank or head, 0.05 margin), brass insert (inside the sleeve, R1C_INSERTS=1), soft pad (inside a
#   pad), hub (signed distance into the hub mesh > 0.2), arm (outside the hub by > 0.2 and not in any of the above);
# nodes on an interface (within those margins) take the body of the nearest certain node in node order (the solver writes nodes
# body by body). GUARD: afterwards no arm or hub node may lie inside the other (by > 0.15: the STL facets cut curved faces by up to
# ~0.1) or inside a bolt / an insert / a pad by more than
# 0.05 mm; if one does, the run stops (SystemExit) instead of scoring it.
import os as _os
INSERTS = _os.environ.get('R1C_INSERTS') == '1'
_SC = float(_os.environ.get("ARM_SLOT_CL", "0.1"))      # 2026-11-12: R1f/D3 FEA has the lug faces line-to-line (ARM_SLOT_CL=0)
LUG_F, LUG_B = CZ + 5.0 + _SC, CZ - 5.0 - _SC
SEAT = LUG_B - 7.0
N = len(p); zz = p[:, 2]; yy = p[:, 1]
if INSERTS:      # M3 x 25 DIN 912 from the back counterbore seat, Dia 4.0 x 5.7 insert from the front lug face
    def steel_in(m):
        return ((rb_all < 1.5 - m) & (zz > SEAT + m) & (zz < SEAT + 25.0 - m)) | ((rb_all < 2.75 - m) & (zz > SEAT - 3.0 + m) & (zz < SEAT - m))
    def brass_in(m):
        return (rb_all > 1.5 + m) & (rb_all < 2.0 - m) & (zz > LUG_F + m) & (zz < LUG_F + 5.7 - m)
else:            # bolts bonded in a Dia 3.0 bore, Z CZ + 4 +- 32
    def steel_in(m):
        return (rb_all < 1.5 - m) & (zz > CZ - 28.0 + m) & (zz < CZ + 36.0 - m)
    def brass_in(m):
        return np.zeros(N, bool)
SHIM_T = float(_os.environ.get('R1C_SHIM', '0'))      # R1e shim ring as its own body (r 36.2-38.4, Y 302 - t to 302)
def shim_in(m):
    if SHIM_T <= 0:
        return np.zeros(N, bool)
    rr = np.hypot(p[:, 0] - HX, zz - CZ)
    return (rr > 36.2 + m) & (rr < 38.4 - m) & (yy > 302.0 - SHIM_T + m) & (yy < 302.0 - m)
def pad_in(m):
    k = np.zeros(N, bool)
    for x0, dz in PAD_PTS:
        k |= (np.hypot(p[:, 0] - x0, zz - (CZ + dz)) < 0.9 - m) & (yy > 295.7 + m) & (yy < 296.0 - m)
    return k
lo_b, hi_b = hub.bounds[0] - 0.5, hub.bounds[1] + 0.5
near_hub = np.all((p >= lo_b) & (p <= hi_b), axis=1)
sd = np.full(N, -99.0)
ix = np.flatnonzero(near_hub)
sd[ix] = np.concatenate([trimesh.proximity.signed_distance(hub, p[ix[i:i + 20000]]) for i in range(0, len(ix), 20000)]) if len(ix) else []
lab = np.full(N, -1, np.int8)
lab[sd < -0.2] = 0
lab[sd > 0.2] = 1
lab[steel_in(0.05)] = 2
lab[brass_in(0.05)] = 3
lab[pad_in(0.05)] = 4
lab[shim_in(0.05)] = 5
lab[(lab == 0) & (steel_in(-0.05) | brass_in(-0.05) | pad_in(-0.05) | shim_in(-0.05))] = -1      # near a small body's surface: decide by node order
small_in = steel_in(0.05) | brass_in(0.05) | pad_in(0.05) | shim_in(0.05)
compat = np.zeros((6, N), bool)      # which bodies a node can geometrically belong to (interface nodes: more than one)
compat[0] = (sd < 0.15) & ~small_in
compat[1] = (sd > -0.15) & ~small_in
compat[2] = steel_in(-0.05); compat[3] = brass_in(-0.05); compat[4] = pad_in(-0.05); compat[5] = shim_in(-0.05)
cert = np.flatnonzero(lab >= 0)
body = lab.copy()
if len(cert):
    body[:cert[0]] = lab[cert[0]]; body[cert[-1] + 1:] = lab[cert[-1]]
    gaps = np.flatnonzero(np.diff(cert) > 1)
    for g in gaps:      # unsure nodes between two certain ones
        i, j = cert[g], cert[g + 1]; A, B = lab[i], lab[j]; seg = np.arange(i + 1, j)
        if A == B:
            body[seg] = A
            continue
        # bodies are contiguous in node order: one cut; put it where the fewest nodes end up in a body they cannot belong to
        bad_a = np.r_[0, np.cumsum(~compat[A, seg])]; bad_b = np.r_[np.cumsum((~compat[B, seg])[::-1])[::-1], 0]
        k = int(np.argmin(bad_a + bad_b))
        body[seg[:k]] = A; body[seg[k:]] = B
body = body.astype(np.int8)
bad_arm = (body == 0) & ((sd > 0.15) | small_in)
_HM = 0.25 if _os.environ.get('R1C_D3') == '1' else 0.15      # 2026-11-13: the D3 lug's R1.2 Z-root end blends (r about 34.7, Y 295.4) are
# tessellated up to 0.2 off in the hub STL; hub surface nodes there read sd -0.17..-0.20
bad_hub = (body == 1) & ((sd < -_HM) | small_in)
if bad_arm.any() or bad_hub.any():
    for k in np.flatnonzero(bad_arm | bad_hub)[:10]:
        print('GUARD: node', k, p[k].round(3).tolist(), 'assigned', ['arm', 'hub'][body[k]], 'sd', round(float(sd[k]), 3), 'r from bolt', round(float(rb_all[k]), 3))
    raise SystemExit(f'GUARD FAILED: {int(bad_arm.sum())} arm and {int(bad_hub.sum())} hub nodes lie inside another body')
runs = np.flatnonzero(np.diff(body)) + 1
blocks = [(int(a), int(b - 1), int(body[a])) for a, b in zip(np.r_[0, runs], np.r_[runs, N])]
names = ['arm', 'hub', 'steel', 'brass', 'pad', 'shim']
big = [f'{names[c]} {a}-{b}' for a, b, c in blocks if b - a > 50]
print(f'bodies by geometry + node order ({len(blocks)} runs, {sum(b - a <= 50 for a, b, c in blocks)} of 50 nodes or fewer): ' + ', '.join(big))
print(f'GUARD OK: no arm or hub node inside another body (unsure nodes decided by node order: {int((lab < 0).sum())})')
arm = np.flatnonzero(body == 0); hb = np.flatnonzero(body == 1); bl = np.flatnonzero(body == 2); br = np.flatnonzero(body == 3)
in_hub = body == 1; bolt = (body == 2) | (body == 3)
out['body_split'] = dict(runs=big, unsure_nodes=int((lab < 0).sum()), guard='ok')
r = np.hypot(p[:, 0] - HX, p[:, 2] - CZ); y = p[:, 1]; th = np.degrees(np.arctan2(p[:, 2] - CZ, p[:, 0] - HX)) % 360
ridge_arc = ((th > 33) & (th < 147)) | ((th > 213) & (th < 327))
import os as _os
if _os.environ.get('R1C_RING') == '1':      # full-ring ridge and groove
    ridge_arc = np.ones(len(p), bool)
groove_arc = ((th > 18) & (th < 162)) | ((th > 198) & (th < 342))
if _os.environ.get('R1C_RING') == '1':
    groove_arc = np.ones(len(p), bool)
posts = (np.abs(p[:, 0] - 147.5) < 7) | (np.abs(p[:, 0] - 193.5) < 7)
trees = {'arm': (arm, cKDTree(p[arm])), 'hub': (hb, cKDTree(p[hb]))}


def rep(body, name, mask, layer_col, allow_layer=22.5):
    ids, tree = trees[body]
    a = ids[mask[ids]]
    row = {'nodes': int(len(a))}
    if len(a) == 0:
        print(f'{body:3s} {name}: no nodes'); out[f'{body}: {name}'] = row; return
    # interlayer shear: arm layers lie in Z planes (tau xz, tau yz = s cols 5, 6), the hub's in Y planes (tau xy, tau yz = cols 4, 6)
    shear = np.hypot(s[:, 5], s[:, 6]) if layer_col == 3 else np.hypot(s[:, 4], s[:, 6])
    for lab, v, al in (('vm', vm, 45.0), ('layer', s[:, layer_col], allow_layer), ('shear', shear, 13.0)):
        i = a[np.argmax(v[a])]
        # worst average ANYWHERE in the region (review 2026-11-12), not just around the peak node: sphere averages for every
        # candidate node (value >= 40 % of the peak, top 5000), the maximum of each, and how many nodes the 0.5 mm one rests on
        cand = a[v[a] >= 0.4 * v[i]] if v[i] > 0 else a[:1]
        cand = cand[np.argsort(-v[cand])][:5000]
        worst = []
        for rr in (0.5, 1.0, 2.0):
            best = (-np.inf, None, 0)
            for j in cand:
                nb = ids[tree.query_ball_point(p[j], rr)]
                mv = float(v[nb].mean())
                if mv > best[0]:
                    best = (mv, j, len(nb))
            worst.append(best)
        av = [w[0] for w in worst]
        j5 = worst[0][1]
        row[lab] = dict(peak=round(float(v[i]), 1), sf=round(al / v[i], 2) if v[i] > 0 else None, at=p[i].round(1).tolist(),
                        r=round(float(r[i]), 2), theta=round(float(th[i]), 1),
                        worst_avg=[round(x, 1) for x in av], sf_avg=[round(al / x, 2) if x > 0 else None for x in av],
                        worst_avg_at=[p[w[1]].round(1).tolist() for w in worst], nodes_in_05=worst[0][2], allowable=al)
        print(f'{body:3s} {name:44s} {lab:5s} peak {v[i]:6.1f} SF {al / v[i] if v[i] > 0 else 0:5.2f} at {p[i].round(1).tolist()} th {th[i]:.0f} | worst avg .5/1/2 '
              f'SF {"/".join(f"{al / x:4.2f}" if x > 0 else "-" for x in av)} '      # '-': no tensile average (all compression)
              f'(0.5 mm: {worst[0][2]} nodes at {p[j5].round(1).tolist()} th {th[j5]:.0f})')
    out[f'{body}: {name}'] = row


ALL = np.ones(len(p), bool)
print(f'nodes: arm {len(arm)}, hub {len(hb)}, bolts {len(bl)}, inserts {len(br)}')
# arm side (layer = sigma z, column 3)
rep('arm', 'WHOLE ARM (nothing excluded)', ALL, 3)
rep('arm', 'ridge load flank (within 0.25 of the 30 deg flank, r 34.6-35.9)', ridge_arc & (r > 34.6) & (r < 35.9) & (np.abs((y - (298.0 + (35.8 - r) * np.tan(np.radians(30)))) * np.cos(np.radians(30))) < 0.25), 3)
rep('arm', 'ridge body (r < 35.9, Y 297.5-302)', ridge_arc & (r < 35.9) & (y > 297.5) & (y < 302.05), 3)
rep('arm', 'ridge root / bore wall (r 35.9-37.5, Y 297.5-302)', ridge_arc & (r >= 35.9) & (r < 37.5) & (y > 297.5) & (y < 302.05), 3)
rep('arm', 'seat bore + end face elsewhere (Y 295-302.6, r<38)', ~(ridge_arc & (y > 297.5) & (y < 302.05) & (r < 37.5)) & (y > 295) & (y < 302.6) & (r < 38) & (r > 33), 3)
rep('arm', 'hub posts (Y 285-296)', posts & (y > 285) & (y < 296), 3)
rep('arm', 'fins (Y 270-285, posts)', posts & (y > 270) & (y <= 285), 3)
rep('arm', 'skin elsewhere (Y 270-296)', ~posts & (y > 270) & (y < 296), 3)
# contact on the groove's load flank (arm nodes within 0.03 mm of its plane): with the R1d flank gap these are the crush ribs only.
# Bearing = stress normal to the flank (compression negative), from the full tensor.
t30_ = np.tan(np.radians(30)); dn = (y - (298.0 + (35.8 - r) * t30_)) * np.cos(np.radians(30))
on = arm[(np.abs(dn[arm]) < 0.03) & ridge_arc[arm] & (r[arm] > 34.6) & (r[arm] < 35.9)]
if len(on):
    c_, s_ = np.cos(np.radians(th[on])), np.sin(np.radians(th[on]))
    nr, ny_ = np.sin(np.radians(30)), np.cos(np.radians(30))           # flank normal in (r, Y), pointing +Y into the ridge
    n = np.c_[nr * c_, np.full(len(on), ny_), nr * s_]
    S = s[on]; sx, sy, sz, txy, txz, tyz = S[:, 1], S[:, 2], S[:, 3], S[:, 4], S[:, 5], S[:, 6]
    sn = (n[:, 0] ** 2 * sx + n[:, 1] ** 2 * sy + n[:, 2] ** 2 * sz + 2 * (n[:, 0] * n[:, 1] * txy + n[:, 0] * n[:, 2] * txz + n[:, 1] * n[:, 2] * tyz))
    out['flank_contact'] = dict(nodes=int(len(on)), theta_span=[round(float(th[on].min()), 1), round(float(th[on].max()), 1)],
                                sigma_n_min=round(float(sn.min()), 1), sigma_n_mean=round(float(sn.mean()), 1))
    print(f"load-flank contact nodes {len(on)} (theta {th[on].min():.0f}-{th[on].max():.0f}); bearing sigma_n min {sn.min():.1f} MPa, mean {sn.mean():.1f} MPa (negative = compression)")
else:
    out['flank_contact'] = dict(nodes=0); print('load-flank contact nodes: none within 0.03 mm')
# hub side (layer = sigma y, column 2)
rep('hub', 'WHOLE HUB (nothing excluded)', ALL, 2)
rep('hub', 'load flank (Y 297.8-299.1, r 34.2-35.85, arcs)', groove_arc & (y > 297.8) & (y < 299.1) & (r > 34.2) & (r < 35.85), 2)
rep('hub', 'groove bottom + 45 flank (Y 299.1-302, arcs)', groove_arc & (y >= 299.1) & (y < 302.0) & (r > 34.0) & (r < 35.85), 2)
rep('hub', '2 mm land (Y 295.5-298, r 33-35.85)', (y > 295.5) & (y < 298.0) & (r > 33) & (r < 35.85), 2)
rep('hub', 'spigot ring above groove (Y 300.5-302.2, r 31-34.3)', (y > 300.5) & (y < 302.2) & (r > 31) & (r < 34.3), 2)
rep('hub', 'spigot core behind groove (Y 297.5-301, r 31-34.3)', (y > 297.5) & (y <= 300.5) & (r > 31) & (r < 34.3), 2)
rep('hub', 'outer ring above groove (r 35.8-39.3, Y 302.5-308)', (y > 302.5) & (y < 308.0) & (r > 35.8) & (r < 39.3), 2)
rep('hub', 'same, near the seam (theta 0 +-25, 180 +-25)', (y > 302.5) & (y < 308.0) & (r > 35.8) & (r < 39.3) & ((th < 25) | (th > 335) | (np.abs(th - 180) < 25)), 2)
lugs = ((p[:, 0] < 152.5) | (p[:, 0] > 188.5)) & (np.abs(p[:, 2] - CZ) < 6.5) & (y < 297.5)
rep('hub', 'lugs incl. roots (Y < 297.5)', lugs, 2)
rep('hub', 'lug roots (Y 294-297.5)', lugs & (y > 294), 2)
if len(bl):
    i = bl[np.argmax(vm[bl])]; out['bolts'] = dict(vm_peak=round(float(vm[i]), 0), at=p[i].round(1).tolist(), sf_vs_640=round(640.0 / vm[i], 2))
if len(br):
    i = br[np.argmax(vm[br])]; out['inserts'] = dict(vm_peak=round(float(vm[i]), 0), at=p[i].round(1).tolist(), sf_vs_240=round(240.0 / vm[i], 2))
    print(f'inserts: vm peak {vm[i]:.0f} MPa at {p[i].round(1).tolist()} (SF vs 240 MPa brass yield {240.0 / vm[i]:.2f})')
if len(bl):
    i = bl[np.argmax(vm[bl])]
    print(f'bolts: vm peak {vm[i]:.0f} MPa at {p[i].round(1).tolist()} (SF vs 640 MPa yield {640.0 / vm[i]:.2f})')
# lug forces: slab across each lug just below the root, hub nodes only
D3 = _os.environ.get('R1C_D3') == '1'      # 2026-11-12: hub rev D3 extended lugs (X offset 18.7-36.35): the slab spans the whole lug at the root band
LUG_SLABS = (('lug -X', (170.49 - 36.4, 170.49 - 18.7)), ('lug +X', (170.49 + 18.7, 170.49 + 36.4))) if D3 else (('lug -X', (141.0, 151.75)), ('lug +X', (189.25, 200.0)))
SLAB_Y = (295.5, 295.9) if D3 else (294.5, 295.5)
for name, (x0, x1) in LUG_SLABS:
    m = in_hub & ~bolt & (y > SLAB_Y[0]) & (y < SLAB_Y[1]) & (p[:, 0] > x0 + 0.2) & (p[:, 0] < x1 - 0.2) & (p[:, 2] > 1.2) & (p[:, 2] < 10.8)
    idx = np.flatnonzero(m)
    if len(idx) == 0:
        print(name, 'no nodes'); continue
    A = (x1 - x0) * 10.0
    fy, fx, fz = s[idx, 2].mean() * A, s[idx, 4].mean() * A, s[idx, 6].mean() * A
    out[name] = dict(nodes=int(len(idx)), Fy_axial=round(float(fy)), Fx_shear=round(float(fx)), Fz_shear=round(float(fz)))
    print(f'{name}: nodes {len(idx)}, axial Fy ~ {fy:7.0f} N, shear Fx ~ {fx:6.0f} N, shear Fz ~ {fz:6.0f} N (section {A:.0f} mm2)')
if pad_all.any():      # soft pads: axial force each carries (mean sigma y over its nodes x area), against the applied load
    pf_ = []
    for x0, dz in PAD_PTS:
        k_ = pad_all & (np.hypot(p[:, 0] - x0, p[:, 2] - (CZ + dz)) < 0.95)
        pf_.append(round(float(s[k_, 2].mean() * np.pi * 0.9 ** 2), 3) if k_.any() else None)
    out['pad_forces_N'] = pf_
    print(f'soft pads: axial force each (N) {pf_}, sum {sum(abs(v) for v in pf_ if v is not None):.3f} N')
flags = []
for k_ in ('lug -X', 'lug +X'):
    if k_ in out and abs(out[k_]['Fy_axial']) > 50: flags.append(f"{k_} axial {out[k_]['Fy_axial']} N > 50 N: ridge not carrying the tie?")
if 'bolts' in out and out['bolts']['vm_peak'] > 200: flags.append(f"bolt vm {out['bolts']['vm_peak']} MPa > 200: ridge not carrying the tie?")
out['sanity_flags'] = flags
print('SANITY:', 'OK' if not flags else '; '.join(flags))
json.dump(out, open(npz + '.r1c.json', 'w'), indent=1)
