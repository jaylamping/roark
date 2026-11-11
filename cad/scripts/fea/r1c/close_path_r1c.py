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
HUBP = Path(r'J:/code/roark-wt/left-arm-organic/cad/_sim/ua2/HUB_GROOVE.STL')


def mm(m):
    if m.extents.max() < 2.0:
        m.apply_scale(1000.0)
    return m


halves = {n: mm(trimesh.load(E / f'upper_arm_organic_{n}_left.STL')) for n in ('front', 'back')}
others = {'hub_grooved': mm(trimesh.load(HUBP)), 'rs02_vendor': place(CLOCK),
          'rs02_ring': mm(trimesh.load(E / 'upper_arm_organic_rs02_ring_left.STL'))}
out = {}


def dense(m, step=0.4):
    """vertices plus points sampled on the surface (so long edges and big faces are checked too)"""
    n = int(m.area / (step * step))
    pts, _ = trimesh.sample.sample_surface_even(m, min(n, 400000))
    return np.vstack([m.vertices, pts])


def sweep(src_pts, target, direction, label):
    d = np.tile(direction, (len(src_pts), 1)).astype(float)
    L, RI = [], []
    for i in range(0, len(src_pts), 20000):      # chunked to keep memory down
        l_, r_, _ = target.ray.intersects_location(src_pts[i:i + 20000], d[i:i + 20000], multiple_hits=False)
        L.append(l_); RI.append(r_ + i)
    loc, ri = np.vstack(L) if L else np.zeros((0, 3)), np.concatenate(RI) if RI else np.zeros(0, int)
    if len(ri) == 0:
        print(label, '{"hits": 0}', flush=True)
        return dict(hits=0)
    dist = np.einsum('ij,ij->i', loc - src_pts[ri], d[ri])
    # a ray that starts inside the target is a final-position overlap; one that starts outside and hits is a path collision
    inside = np.concatenate([target.contains(src_pts[ri[i:i + 20000]]) for i in range(0, len(ri), 20000)]) if target.is_watertight and len(ri) else np.zeros(len(ri), bool)
    far = (dist > 0.05) & ~inside
    yk = src_pts[ri, 1]
    cop = np.zeros(len(ri), bool)
    for yp in (296.0, 302.0):      # coplanar contact planes (bore floor on the spigot's Y 296 face, end face on the disc at Y 302): grazing rays
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
json.dump(out, open(Path(__file__).parent / 'close_path_r1c.json', 'w'), indent=1)
