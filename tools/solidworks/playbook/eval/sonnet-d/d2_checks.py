"""D2: does the pair go together. Distances between the exported STLs (what touches, what clears), under the memory cap."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
import sheet  # noqa

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d2")
RES = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d")
up = trimesh.load(OUT / 'housing_upper.stl')
lo = trimesh.load(OUT / 'housing_lower.stl')
rg = trimesh.load(OUT / 'ring.stl')
res = dict(volumes_mm3=dict(upper=round(float(up.volume), 1), lower=round(float(lo.volume), 1), ring=round(float(rg.volume), 1)),
           watertight=dict(upper=bool(up.is_watertight), lower=bool(lo.is_watertight), ring=bool(rg.is_watertight)),
           boxes=dict(upper=up.bounds.round(3).tolist(), lower=lo.bounds.round(3).tolist(), ring=rg.bounds.round(3).tolist()))
both = trimesh.util.concatenate([up, lo])
res['pair_box'] = both.bounds.round(3).tolist()
tree_h = cKDTree(both.sample(300000))
rng = np.random.default_rng(3)


def min_dist(points):
    return float(tree_h.query(points)[0].min())


def ring_pts(r, z0, z1, n=6000):
    a = rng.uniform(0, 2 * math.pi, n)
    z = rng.uniform(z0, z1, n)
    return np.c_[r * np.cos(a), r * np.sin(a), z]


c = {}
# the outer ring's outside against the seat (touching: 0), the ring's ends against the shoulders
c['ring_outside_to_seat_mm (line to line by design)'] = round(min_dist(ring_pts(26.0, 0.2, 7.2)), 3)
a = rng.uniform(0, 2 * math.pi, 6000)
rr = rng.uniform(24.0, 25.5, 6000)
c['ring_top_face_to_upper_shoulder_mm'] = round(min_dist(np.c_[rr * np.cos(a), rr * np.sin(a), np.full(6000, 7.2)]), 3)
c['ring_bottom_face_to_lower_shoulder_mm'] = round(min_dist(np.c_[rr * np.cos(a), rr * np.sin(a), np.full(6000, 0.2)]), 3)
# the turning inner ring: Ø44.0, same width as the ring; it may be anywhere in Z 0.2 to 7.2 and turns about Z
c['inner_ring_outside_to_shoulders_mm (radial, turning)'] = round(min_dist(ring_pts(22.0, 0.2, 7.2)), 3)
c['inner_ring_end_face_circle_to_shoulders_mm'] = round(min(min_dist(ring_pts(r, 0.2, 0.2)) for r in (20.0, 22.0)), 3)
c['shaft_Ø40_to_shoulders_mm (radial)'] = round(min_dist(ring_pts(20.0, -4, 11)), 3)
# screws: head in the counterbore, shank in the clearance hole, M3 thread in the insert
c['screw_clearance_hole_radial_mm (Ø3.4 for M3)'] = 0.2
c['screw_head_in_counterbore_radial_mm (Ø6 for a Ø5.5 head)'] = 0.25
c['screw_head_height_vs_counterbore_mm (3.0 head, 3.5 deep)'] = 0.5
# walls between features from the exported solids: the screw holes against the seat, and the M4 holes
for name, mesh in (('upper', up), ('lower', lo)):
    pts = []
    for sx in (-1, 1):
        for z in (1.0, 6.0):
            a2 = rng.uniform(0, 2 * math.pi, 400)
            yy = 8.0 if name == 'upper' else -8.0
            pts.append(np.c_[sx * 30.0 + 1.7 * np.cos(a2), np.full(400, yy), z + 1.7 * np.sin(a2)])
    pts = np.vstack(pts)
    seat_tree = cKDTree(np.array([[26.0 * math.cos(t), 26.0 * math.sin(t), z] for t in np.linspace(0, 2 * math.pi, 1500) for z in np.linspace(0, 7.4, 20)]))
    c[f'{name}: M3 hole wall to the seat (clear hole r1.7, hole centre X30), mm'] = round(float(seat_tree.query(pts[:, :3] * [1, 0, 1] + [0, 0, 0])[0].min()), 3)
c['spec as drawn: screw at X 28.2 with a Ø4.0 insert hole, wall to the Ø52 seat (r 26), mm'] = round(28.2 - 2.0 - 26.0, 3)
c['spec as drawn: screw at X 28.2 with a Ø3.4 clearance hole, wall to the seat, mm'] = round(28.2 - 1.7 - 26.0, 3)
c['built: Ø4.0 insert hole wall to the seat at X 30, mm'] = round(30.0 - 2.0 - 26.0, 3)
c['M4 insert hole (Ø5.6 at X 24, Z 3.5, 8 deep from Y -32) to the seat, mm'] = round(math.hypot(24.0, 24.0) - 2.8 - 26.0, 3)
res['clearances_mm'] = c
# split gap and what it leaves the printer: gap as built
res['split_gap_mm'] = round(float(lo.bounds[1][1] * -1 + up.bounds[0][1]), 3) if False else round(float(up.bounds[0][1] - lo.bounds[1][1]), 3)
(RES / 'd2_checks.json').write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
