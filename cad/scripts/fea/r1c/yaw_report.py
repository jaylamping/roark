"""YAW_17 report (2026-11-12): per-post, fin, hub lug-root, insert, bolt and lug-hole figures from a hub-seat result, optionally
with a second result added node by node (superposition estimate, e.g. G90 + yaw: same model and mesh, linear apart from contact).
    python yaw_report.py NPZ POST_TXT [NPZ2 POST_TXT2] > out.txt      (run under capped.py)
Sphere averages at 0.5 / 1 / 2 mm, as hub_r1c: PETG yield 45 (vm), across-layer 22.5 (arm sz, hub sy; tension only),
interlayer shear 13 (arm txz,tyz; hub txy,tyz). Bolts: steel 640 MPa yield; inserts brass 240."""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
BOLT_X = (147.5, 193.5)
BOLT_Y = 292.0


def load(npz, post):
    d = np.load(npz)
    p, s = d['pos'], d['s']
    runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(post).read().split('\n')[0])
    body = np.full(len(p), '?', object)
    for nm, a, b in runs:
        body[int(a):int(b) + 1] = nm
    return p, s, body


p, s, body = load(sys.argv[1], sys.argv[2])
tag = 'single'
if len(sys.argv) > 4:      # add the second result by node id
    p2, s2, b2 = load(sys.argv[3], sys.argv[4])
    # match by position (node numbering differs between runs). Coincident nodes sit on contact faces: among the 4 nearest,
    # take the one with the same body label, else the nearest
    if len(p) != len(p2):
        raise SystemExit('meshes differ: no superposition')
    dd, jj = cKDTree(p2).query(p, k=4)
    if dd[:, 0].max() > 1e-3:
        raise SystemExit(f'node positions differ by {dd[:, 0].max():.4f}: no superposition')
    same = (b2[jj] == body[:, None]) & (dd < 1e-3)
    pick = np.where(same.any(axis=1), same.argmax(axis=1), 0)
    o2 = jj[np.arange(len(p)), pick]
    print('superposition: nodes matched', len(o2), 'unique', len(np.unique(o2)))
    s = s.copy()
    s[:, 1:7] = s[:, 1:7] + s2[o2, 1:7]
    sx, sy, sz, txy, txz, tyz = (s[:, k] for k in range(1, 7))
    s[:, 10] = np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3 * (txy ** 2 + txz ** 2 + tyz ** 2))
    tag = 'superposed ' + sys.argv[3]
print('result:', sys.argv[1], '|', tag)
vm = s[:, 10]
r = np.hypot(p[:, 0] - HX, p[:, 2] - CZ)
th = np.degrees(np.arctan2(p[:, 2] - CZ, p[:, 0] - HX)) % 360
tree = {}


def worst(mask, val, allow, label, ncand=400):
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        print(f'{label:46s} no nodes')
        return
    bodyname = body[idx[0]]
    if bodyname not in tree:
        tree[bodyname] = (cKDTree(p[body == bodyname]), np.flatnonzero(body == bodyname))
    t, map_ = tree[bodyname]
    cand = idx[np.argsort(-val[idx])[:ncand]]
    out = []
    for R in (0.5, 1.0, 2.0):
        best, bn, bat = -1e9, 0, None
        for c in cand:
            nb = map_[t.query_ball_point(p[c], R)]
            nb = nb[mask[nb]]
            if len(nb) == 0:
                continue
            m = val[nb].mean()
            if m > best:
                best, bn, bat = m, len(nb), p[c]
        out.append((best, bn, bat))
    sf = ['%.2f' % (allow / v) if v > 0 else '-' for v, _, _ in out]
    print(f'{label:46s} peak {val[idx].max():6.1f} | SF .5/1/2 {"/".join(sf)} (n {out[0][1]}/{out[1][1]}/{out[2][1]}) at {np.round(out[0][2], 1).tolist()} th {th[np.argmin(np.linalg.norm(p - out[0][2], axis=1))]:.0f}')


arm, hub = body == 'arm', body == 'hub'
a_layer, a_shear = s[:, 3], np.hypot(s[:, 5], s[:, 6])
h_layer, h_shear = s[:, 2], np.hypot(s[:, 4], s[:, 6])
POSTS = {'-X front (inserts)': (138.0, 154.0, 1), '-X back (clearance)': (138.0, 154.0, -1),
         '+X front (inserts)': (187.0, 203.0, 1), '+X back (clearance)': (187.0, 203.0, -1)}
for nm, (x0, x1, side) in POSTS.items():
    m = arm & (p[:, 0] > x0) & (p[:, 0] < x1) & (p[:, 1] > 284.0) & (p[:, 1] < 296.0) & ((p[:, 2] - CZ) * side > 5.0) & (np.abs(p[:, 2] - CZ) < 20.0)
    print(f'-- post {nm}: {int(m.sum())} nodes')
    worst(m, vm, 45.0, '   vm')
    worst(m, a_layer, 22.5, '   layer (sz)')
    worst(m, a_shear, 13.0, '   shear')
for nm, (x0, x1) in (('fins -X', (136.0, 156.0)), ('fins +X', (185.0, 205.0))):
    m = arm & (p[:, 0] > x0) & (p[:, 0] < x1) & (p[:, 1] > 268.0) & (p[:, 1] <= 284.0) & (np.abs(p[:, 2] - CZ) < 20.0)
    print(f'-- {nm}: {int(m.sum())} nodes')
    worst(m, vm, 45.0, '   vm')
    worst(m, a_layer, 22.5, '   layer (sz)')
    worst(m, a_shear, 13.0, '   shear')
for nm, (x0, x1) in (('hub lug -X', (139.0, 153.0)), ('hub lug +X', (187.0, 202.0))):
    m = hub & (p[:, 0] > x0) & (p[:, 0] < x1) & (p[:, 1] > 287.0) & (p[:, 1] < 297.5)
    print(f'-- {nm} incl. roots: {int(m.sum())} nodes')
    worst(m, vm, 45.0, '   vm')
    worst(m, h_layer, 22.5, '   layer (sy)')
    worst(m, h_shear, 13.0, '   shear')
    for bx in BOLT_X:      # bolt-hole bearing in the lug: compression around the hole (min principal), within 0.8 of the hole wall
        if x0 < bx < x1:
            mb = m & (np.hypot(p[:, 0] - bx, p[:, 1] - BOLT_Y) < 2.6)
            if mb.any():
                worst(mb, -s[:, 9], 45.0, '   bolt-hole bearing (-p3)')
m = arm & (r > 35.8) & (r < 37.6) & (p[:, 1] > 300.8) & (p[:, 1] < 302.1)      # end-face corner band (chamfer + end face, all round)
print(f'-- arm end-face corner band (r 35.8-37.6, Y 300.8-302.1): {int(m.sum())} nodes')
worst(m, vm, 45.0, '   vm')
worst(m, a_layer, 22.5, '   layer (sz)')
worst(m, a_shear, 13.0, '   shear')
m = arm & (np.abs(p[:, 2] - CZ) > 20.0) & (p[:, 1] > 270.0)      # everything else in the hub end, for a 'nothing else below' check
print(f'-- arm elsewhere in the hub end (|Z - CZ| > 20, Y > 270): {int(m.sum())} nodes')
worst(m, vm, 45.0, '   vm')
worst(m, a_shear, 13.0, '   shear')
ins = body == 'brass'
for bx in BOLT_X:
    m = ins & (np.abs(p[:, 0] - bx) < 3.0)
    if m.any():
        print(f'insert at X {bx}: vm peak {vm[m].max():.0f} MPa (SF vs 240 {240 / vm[m].max():.2f}); 0.5 mm avg:', end=' ')
        worst(m, vm, 240.0, '')
st = body == 'steel'
for bx in BOLT_X:
    m = st & (np.abs(p[:, 0] - bx) < 3.0)
    if m.any():
        sh = np.hypot(s[:, 5], s[:, 6])      # transverse shear on Z sections (bolt axis along Z)
        print(f'bolt at X {bx}: vm peak {vm[m].max():.0f} MPa (SF {640 / vm[m].max():.2f}); axial/bending |sz| peak {np.abs(s[m, 3]).max():.0f} MPa; transverse shear peak {sh[m].max():.0f} MPa (SF vs 0.58*640 {0.58 * 640 / sh[m].max():.2f})')
