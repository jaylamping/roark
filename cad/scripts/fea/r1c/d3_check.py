"""Hub rev D3 checks by section (2026-11-12): (1) D3 against bc16e97: where the sections differ; (2) D3 in the closed R1f halves
(+ the 0.70 ring on the disc): overlap and the smallest gap per Y level in the lug zones, and the gap from each lug's Z faces to
our pocket faces (shim space). Y planes from 286 to 303 every 0.1. Pure section geometry (shapely), no meshes in memory beyond
the three STLs.
    python d3_check.py D3_STL BC16_STL HALVES_DIR OUT_JSON      (run under capped.py)"""
import json
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
d3, bc, X, OUT = sys.argv[1:5]
hub = trimesh.load(d3)
old = trimesh.load(bc)
halves = [trimesh.load(X + '/upper_arm_organic_front_left.STL'), trimesh.load(X + '/upper_arm_organic_back_left.STL')]


def region(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return Polygon()
    reg = Polygon()
    for e in s.discrete:
        if len(e) > 3:
            reg = reg.symmetric_difference(Polygon(np.c_[e[:, 0], e[:, 2]]).buffer(0))
    return reg


ZONES = {'-X lug': box(HX - 40, CZ - 14, HX - 15, CZ + 14), '+X lug': box(HX + 15, CZ - 14, HX + 40, CZ + 14)}
res = dict(diff=[], fit=[])
for y in np.round(np.arange(286.0, 303.01, 0.1), 2):
    h, o = region(hub, y), region(old, y)
    dif = h.symmetric_difference(o)
    if dif.area > 0.05:
        bb = dif.bounds
        res['diff'].append(dict(y=float(y), area=round(dif.area, 3), x_off=[round(bb[0] - HX, 2), round(bb[2] - HX, 2)], z=[round(bb[1] - CZ, 2), round(bb[3] - CZ, 2)]))
    arm = unary_union([region(m, y) for m in halves])
    for zn, zb in ZONES.items():
        hz, az = h.intersection(zb), arm.intersection(zb)
        if hz.is_empty or az.is_empty:
            continue
        ov = hz.intersection(az).area
        gap = hz.distance(az) if ov < 1e-4 else 0.0
        # Z-face gaps: thin horizontal probes from the lug's Z faces (Z 1.0 / 11.0 absolute) outward
        zg = {}
        for side, z0 in (('front', 11.0), ('back', 1.0)):
            best = None
            for xo in np.arange(19.0, 36.4, 0.5):
                xs = HX + (xo if zn == '+X lug' else -xo)
                line = box(xs - 0.01, min(z0, z0 + (1 if side == 'front' else -1) * 2), xs + 0.01, max(z0, z0 + (1 if side == 'front' else -1) * 2))
                if not hz.buffer(0.02).intersects(box(xs - 0.01, z0 - 0.05, xs + 0.01, z0 + 0.05)):
                    continue
                hit = az.intersection(line)
                if hit.is_empty:
                    continue
                dz = min(abs(hit.bounds[1] - z0), abs(hit.bounds[3] - z0))
                best = dz if best is None else min(best, dz)
            if best is not None:
                zg[side] = round(best, 3)
        res['fit'].append(dict(y=float(y), zone=zn, overlap_mm2=round(ov, 4), min_gap=round(gap, 3), zface_gap=zg))
json.dump(res, open(OUT, 'w'), indent=1)
print('D3 vs bc16e97: differing Y levels', len(res['diff']), 'Y', res['diff'][0]['y'] if res['diff'] else '-', '..', res['diff'][-1]['y'] if res['diff'] else '-')
xs = [d['x_off'] for d in res['diff']]
print('  x offsets of the differences:', (min(v[0] for v in xs), max(v[1] for v in xs)) if xs else '-', 'z', (min(d['z'][0] for d in res['diff']), max(d['z'][1] for d in res['diff'])) if xs else '-')
ovs = [f for f in res['fit'] if f['overlap_mm2'] > 0]
print('D3 in R1f halves: levels with overlap', len(ovs), [(f['y'], f['zone'], f['overlap_mm2']) for f in ovs[:12]])
for zn in ZONES:
    g = [f for f in res['fit'] if f['zone'] == zn and f['overlap_mm2'] == 0]
    if g:
        m = min(g, key=lambda f: f['min_gap'])
        print(f'  {zn}: smallest gap {m["min_gap"]} at Y {m["y"]}')
        for side in ('front', 'back'):
            v = [(f['y'], f['zface_gap'][side]) for f in res['fit'] if f['zone'] == zn and side in f['zface_gap']]
            if v:
                print(f'    Z-face gap {side}: min {min(t[1] for t in v)} max {max(t[1] for t in v)} over Y {v[0][0]}-{v[-1][0]}')
