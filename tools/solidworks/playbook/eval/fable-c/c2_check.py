"""Every fixed item of C2 measured on the finished export (link_organic.stl), by point-in-solid tests in small chunks.

python tools/pc/capped.py --mb 4096 -- python c2_check.py     -> c2_check.json
"""
import json
import math
from pathlib import Path

import numpy as np
import trimesh

import c2_build as c

OUT = c.OUT
import sys
STEM = sys.argv[1] if len(sys.argv) > 1 else "link_organic"
mesh = trimesh.load(OUT / f"{STEM}.stl")
rng = np.random.default_rng(1)


TRI = np.asarray(mesh.triangles, float)
_d = np.array([0.3713, 0.5571, 0.7428]); _d /= np.linalg.norm(_d)
_e1 = np.cross(_d, [1.0, 0, 0]); _e1 /= np.linalg.norm(_e1)
_e2 = np.cross(_d, _e1)
_U, _V, _W = TRI @ _e1, TRI @ _e2, TRI @ _d          # (n, 3) each: the triangles seen along the ray


def inside(p):
    """Point in solid by counting the triangles a ray along _d crosses beyond the point. trimesh.contains has no
    accelerator here and did not finish 20,000 points in ten minutes; this does 400 points against every triangle at once."""
    p = np.asarray(p, float).reshape(-1, 3)
    out = np.zeros(len(p), bool)
    for k in range(0, len(p), 400):
        q = p[k:k + 400]
        u, v, w = (q @ _e1)[:, None], (q @ _e2)[:, None], (q @ _d)[:, None]
        x0, y0, x1, y1, x2, y2 = _U[:, 0] - u, _V[:, 0] - v, _U[:, 1] - u, _V[:, 1] - v, _U[:, 2] - u, _V[:, 2] - v
        c0, c1, c2 = x0 * y1 - x1 * y0, x1 * y2 - x2 * y1, x2 * y0 - x0 * y2
        hit = ((c0 > 0) & (c1 > 0) & (c2 > 0)) | ((c0 < 0) & (c1 < 0) & (c2 < 0))
        area = c0 + c1 + c2
        area = np.where(area == 0, 1.0, area)
        wi = (c1 * _W[:, 0] + c2 * _W[:, 1] + c0 * _W[:, 2]) / area
        out[k:k + 400] = ((hit & (wi > w)).sum(axis=1) % 2) == 1
    return out


def ring_pts(r0, r1, n, cx=0.0, cz=0.0):
    r = np.sqrt(rng.uniform(r0 ** 2, r1 ** 2, n))
    t = rng.uniform(0, 2 * math.pi, n)
    return cx + r * np.cos(t), cz + r * np.sin(t)


res = {}
res['watertight'] = bool(mesh.is_watertight)
res['shells'] = len(mesh.split())
res['stl_volume_mm3'] = round(float(mesh.volume), 1)
res['stl_bounds'] = np.round(mesh.bounds, 2).tolist()
bolts = [(c.R_PCD * math.cos(math.radians(60 * k)), c.R_PCD * math.sin(math.radians(60 * k))) for k in range(6)]

# 1. mounting ring on Y -4, Ø30 to Ø62: solid just above the plane, empty just below, away from the holes
x, z = ring_pts(15.15, 30.95, 6000)
keep = np.all([np.hypot(x - bx, z - bz) > 1.85 for bx, bz in bolts], axis=0)
x, z = x[keep], z[keep]
res['ring_solid_at_y-3.95'] = float(inside(np.c_[x, np.full_like(x, -3.95), z]).mean())
res['ring_empty_at_y-4.05'] = float(1 - inside(np.c_[x, np.full_like(x, -4.05), z]).mean())
v = mesh.vertices
res['lowest_y_within_r31'] = round(float(v[np.hypot(v[:, 0], v[:, 2]) < 31.0][:, 1].min()), 4)
# bore and bolt holes: empty inside, solid just outside
x, z = ring_pts(0, 14.9, 1500)
res['bore_empty'] = float(1 - inside(np.c_[x, rng.uniform(-3.9, 3.9, len(x)), z]).mean())
x, z = ring_pts(15.1, 15.6, 1500)
res['bore_wall_solid'] = float(inside(np.c_[x, rng.uniform(-3.9, 3.9, len(x)), z]).mean())
he, hs, sc = [], [], []
for bx, bz in bolts:
    x, z = ring_pts(0, 1.65, 300, bx, bz)
    he.append(float(1 - inside(np.c_[x, rng.uniform(-3.9, 3.9, 300), z]).mean()))
    x, z = ring_pts(1.75, 2.1, 300, bx, bz)
    hs.append(float(inside(np.c_[x, rng.uniform(-3.9, 3.9, 300), z]).mean()))
    x, z = ring_pts(0, 3.5, 1500, bx, bz)          # 2. the Ø7 x 10 clear cylinder for the screw head and driver
    sc.append(float(1 - inside(np.c_[x, rng.uniform(4.02, 14.0, 1500), z]).mean()))
res['bolt_holes_empty'], res['bolt_hole_walls_solid'], res['screw_head_cylinders_clear'] = he, hs, sc

# 3. wrist: pin hole empty through both cheeks, inner faces flat at Y +-16 over Ø16, 5 mm of material round the hole
x, z = ring_pts(0, 3.95, 2000, 0, c.Z_PIN)
res['pin_hole_empty'] = float(1 - inside(np.c_[x, rng.uniform(-23.5, 23.5, 2000), z]).mean())
x, z = ring_pts(4.1, 8.0, 2000, 0, c.Z_PIN)
res['cheek_face_flat_O16'] = {s: [float(inside(np.c_[x, np.full_like(x, s * 16.05), z]).mean()),
                                  float(1 - inside(np.c_[x, np.full_like(x, s * 15.95), z]).mean())] for s in (1, -1)}
x, z = ring_pts(4.05, 9.0, 500, 0, c.Z_PIN)
full = {}
for s in (1, -1):
    ys = np.arange(16.05, 23.3, 0.25)
    ok = [bool(inside(np.c_[x, np.full_like(x, s * y), z]).all()) for y in ys]
    full[s] = round(float(ys[np.flatnonzero(ok)[-1]]), 2) if any(ok) else None
res['5mm_ring_solid_from_16_to_abs_y'] = full
# 4. the slot: nothing between the cheeks from Z -183 downward, and the Ø30 sweep about the pin
p = np.c_[rng.uniform(-20, 20, 8000), rng.uniform(-15.95, 15.95, 8000), rng.uniform(-225, -183.0, 8000)]
res['slot_clear_below_-183'] = float(1 - inside(p).mean())
x, z = ring_pts(0, 15.0, 4000, 0, c.Z_PIN)
res['sweep_O30_clear'] = float(1 - inside(np.c_[x, rng.uniform(-15.95, 15.95, 4000), z]).mean())
# 5. the cable passage: a straight Ø6 cylinder along the tunnel axis
A, B = np.array(c.TUNNEL[0], float), np.array(c.TUNNEL[1], float)
u = (B - A) / np.linalg.norm(B - A)
e1, e2 = np.array([1.0, 0, 0]), np.cross(u, [1.0, 0, 0])
n = 8000
s_ = rng.uniform(0, np.linalg.norm(B - A), n)
r = 2.98 * np.sqrt(rng.uniform(0, 1, n))
t = rng.uniform(0, 2 * math.pi, n)
p = A + np.outer(s_, u) + np.outer(r * np.cos(t), e1) + np.outer(r * np.sin(t), e2)
res['cable_O6_clear'] = float(1 - inside(p).mean())
res['cable_axis'] = [list(map(float, A)), list(map(float, B))]
# where the cable is under the skin: at each station, is there solid above it (+Y) in the plane X 0?
st = []
for zq in np.arange(-25, -180, -5.0):
    yq = float(A[1] + (zq - A[2]) * u[1] / u[2])
    above = inside(np.c_[np.zeros(40), np.linspace(yq + 3.05, yq + 30, 40), np.full(40, zq)]).any()
    st.append((float(zq), round(yq, 2), bool(above)))
res['cable_roofed_from_z'] = max((s[0] for s in st if s[2]), default=None)
res['cable_roofed_to_z'] = min((s[0] for s in st if s[2]), default=None)
res['mass_g_from_stl'] = round(float(mesh.volume) * 1.19e-3, 1)
step = (OUT / f'{STEM}.step').read_text(errors='ignore')
res['step_mm'] = any('.MILLI.' in ln for ln in step.splitlines() if 'SI_UNIT' in ln)
(Path(__file__).parent / f'c2_check_{STEM}.json').write_text(json.dumps(res, indent=1))
bad = [k for k, v in res.items() if k.endswith(('clear', 'empty', 'solid', 'clear_below_-183')) and (min(v) if isinstance(v, list) else v) < 1.0]
bad += [k for k in ('ring_solid_at_y-3.95', 'ring_empty_at_y-4.05', 'watertight', 'step_mm') if res[k] < 1]
bad += ['cheek_face'] if min(min(v) for v in res['cheek_face_flat_O16'].values()) < 1 else []
bad += ['5mm ring'] if min(v or 0 for v in res['5mm_ring_solid_from_16_to_abs_y'].values()) < 21.0 else []
bad += ['shells'] if res['shells'] != 1 else []
res['fixed_items_ok'], res['failed'] = not bad, bad
(Path(__file__).parent / f'c2_check_{STEM}.json').write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
