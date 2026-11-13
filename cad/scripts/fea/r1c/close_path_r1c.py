"""R1c closing path: each half comes in along Z onto the grooved hub (HUB_GROOVE.STL) and the vendor RS02 (placed as in
rs02_fit.py), plus the RS02 ring. A collision on the way in shows as a ray from a half's vertex, cast in the half's opening
direction (away from the seam), that enters the other part's material; and, both ways round, as a ray from the other part's
vertices cast toward the half. Hits within 0.05 mm of the start are touching faces at the final position (bore on spigot, posts
on lugs) and are listed apart. Also reports the final-position overlap (signed distance) of ridge vertices against the hub.
    python close_path_r1c.py            writes close_path_r1c.json"""
import json
import os
from pathlib import Path
import numpy as np
import trimesh
from rs02_fit import place, CLOCK

HX, CZ = 170.49, 5.985875
E = Path(os.environ.get('ARM_EXPORTS', r'J:/code/roark-wt/left-arm-organic/cad/_wip/r1c/exports'))
HUBP = Path(os.environ.get('HUB_STL', r'J:/code/roark-wt/left-arm-organic/cad/_sim/ua2/HUB_GROOVE.STL'))
RING = Path(os.environ.get('RING_STL', str(E / 'upper_arm_organic_rs02_ring_left.STL')))
OUTJ = Path(os.environ.get('CLOSE_JSON', str(Path(__file__).parent / 'close_path_r1c.json')))


def mm(m):
    if m.extents.max() < 2.0:
        m.apply_scale(1000.0)
    return m


halves = {n: mm(trimesh.load(E / f'upper_arm_organic_{n}_left.STL')) for n in ('front', 'back')}
others = {'hub_grooved': mm(trimesh.load(HUBP)), 'rs02_vendor': place(CLOCK),
          'rs02_ring': mm(trimesh.load(RING))}
out = {}


def dense(m, step=0.4):
    """vertices plus points sampled on the surface (so long edges and big faces are checked too)"""
    n = int(m.area / (step * step))
    pts, _ = trimesh.sample.sample_surface_even(m, min(n, 400000))
    return np.vstack([m.vertices, pts])


def sweep(src_pts, target, direction, label):
    d = np.tile(direction, (len(src_pts), 1)).astype(float)
    L, RI = [], []
    for i in range(0, len(src_pts), 2000):      # chunked to keep memory down (2000: the 6 GB cap, 2026-11-12)
        l_, r_, _ = target.ray.intersects_location(src_pts[i:i + 2000], d[i:i + 2000], multiple_hits=False)
        L.append(np.asarray(l_, float).reshape(-1, 3)); RI.append(np.asarray(r_, int).reshape(-1) + i)
    loc, ri = np.vstack(L) if L else np.zeros((0, 3)), np.concatenate(RI) if RI else np.zeros(0, int)
    if len(ri) == 0:
        print(label, '{"hits": 0}', flush=True)
        return dict(hits=0)
    dist = np.einsum('ij,ij->i', loc - src_pts[ri], d[ri])
    # a ray that starts inside the target is a final-position overlap; one that starts outside and hits is a path collision
    # chunks of 200 points: the 6 GB cap (2026-11-12; 2000 still made 21 M ray-triangle candidates against the hub)
    inside = np.concatenate([target.contains(src_pts[ri[i:i + 200]]) for i in range(0, len(ri), 200)]) if (target.is_watertight or __import__('os').environ.get('CLOSE_FORCE_CONTAINS') == '1') and len(ri) else np.zeros(len(ri), bool)      # CLOSE_FORCE_CONTAINS (2026-11-12): D3's STL has one non-manifold edge (not watertight); ray-parity containment still works
    far = (dist > 0.05) & ~inside
    yk = src_pts[ri, 1]
    cop = np.zeros(len(ri), bool)
    for yp in (296.0, 302.0) + tuple(float(v) for v in __import__('os').environ.get('CLOSE_EXTRA_PLANES', '').split(',') if v):      # coplanar contact planes (R1e: + the lowered end face on the shim, CLOSE_EXTRA_PLANES=301.3) (bore floor on the spigot's Y 296 face, end face on the disc at Y 302): grazing rays
        cop |= np.abs(yk - yp) < 0.03
    res_cop = int((far & cop).sum())
    far &= ~cop
    res = dict(hits=int(len(ri)), touching_or_inside=int((~far).sum()) - res_cop, grazing_on_Y296_Y302=res_cop, path_collisions=int(far.sum()))
    if far.any():
        k = ri[far]
        P = src_pts[k]
        r = np.hypot(P[:, 0] - HX, P[:, 2] - CZ)
        th = np.degrees(np.arctan2(P[:, 2] - CZ, P[:, 0] - HX)) % 360
        res['worst'] = [dict(at=P[j].round(2).tolist(), r=round(float(r[j]), 2), theta=round(float(th[j]), 1), dist=round(float(dist[far][j]), 2))
                        for j in np.argsort(dist[far])[:8]]
        res['box'] = [P.min(0).round(1).tolist(), P.max(0).round(1).tolist()]
    print(label, json.dumps(res)[:900], flush=True)
    return res


for n, h in halves.items():
    zc = h.bounds.mean(0)[2]
    opening = np.array([0, 0, 1.0 if zc > CZ else -1.0])
    print(f'{n}: Z centre {zc:.1f} -> opens along {opening[2]:+.0f} Z; watertight {h.is_watertight}', flush=True)
    hp = dense(h)
    for on, o in others.items():
        # half points travel the reverse of their approach: from the final position out along the opening direction
        a = sweep(hp, o, opening, f'  {n} -> {on} (half points, opening dir)')
        b = sweep(dense(o), h, -opening, f'  {on} -> {n} (part points, toward the half)')
        out[f'{n} vs {on}'] = dict(half_points=a, part_points=b)
    # final position: ridge vertices against the grooved hub (signed distance, + inside)
    v = h.vertices
    r = np.hypot(v[:, 0] - HX, v[:, 2] - CZ)
    sel = (v[:, 1] > 297.0) & (v[:, 1] < 302.1) & (r < 35.95)
    sd = trimesh.proximity.signed_distance(others['hub_grooved'], v[sel])
    i = int(np.argmax(sd))
    out[f'{n} ridge/bore final overlap'] = dict(n=int(sel.sum()), max_into_hub=round(float(sd[i]), 3), at=v[sel][i].round(2).tolist())
    print(f'  {n}: ridge/bore vertices {sel.sum()}, max into hub {sd[i]:.3f} mm at {v[sel][i].round(2).tolist()}', flush=True)
# final position, all of each half near the seat (review 2026-11-12): signed distance of vertices + surface samples into the hub;
# anything over 0.02 mm is reported with where it is (the R1d crush ribs are meant to be 0.15 into the hub's flank)
hubm = others['hub_grooved']
for n, h in halves.items():
    P = dense(h, 0.25); P = P[(P[:, 1] > 285.0) & (P[:, 1] < 303.0)]
    sd = np.concatenate([trimesh.proximity.signed_distance(hubm, P[i:i + 300]) for i in range(0, len(P), 300)])      # 300: the 6 GB cap (1000 still hit it on the back half)
    k = sd > 0.02
    r_ = np.hypot(P[:, 0] - HX, P[:, 2] - CZ); th_ = np.degrees(np.arctan2(P[:, 2] - CZ, P[:, 0] - HX)) % 360
    res = dict(points=int(len(P)), into_hub_over_0p02=int(k.sum()), max_into_hub=round(float(sd.max()), 3))
    if k.any():
        res['where'] = dict(r=[round(float(r_[k].min()), 2), round(float(r_[k].max()), 2)], Y=[round(float(P[k, 1].min()), 2), round(float(P[k, 1].max()), 2)],
                            theta=sorted(set(int(round(t / 3.0) * 3) for t in th_[k])))
    out[f'{n} final overlap with the hub'] = res
    print(f'  {n}: final overlap with the hub', json.dumps(res)[:500], flush=True)
json.dump(out, open(OUTJ, 'w'), indent=1)
