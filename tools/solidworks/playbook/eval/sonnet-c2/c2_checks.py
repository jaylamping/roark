"""C2 fixed-item checks on the exported STL (numpy only, point-in-solid)."""
import math, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2common import *
import numpy as np, trimesh
import sheet
tris = sheet.read_stl(OUT / 'link_organic.stl')
mesh = trimesh.load(OUT / 'link_organic.stl')
res = {}
def frac(name, pts, want_inside):
    ins = sheet.inside(tris, np.array(pts, float))
    ok = bool(ins.all()) if want_inside else bool((~ins).all())
    bad = int((~ins).sum() if want_inside else ins.sum())
    res[name] = dict(ok=ok, n=len(pts), bad=bad)
    print(f'{"ok  " if ok else "FAIL"} {name}: {len(pts)} points, {bad} wrong')
rng = np.random.default_rng(1)
def ring(r0, r1, n=200):
    out = []
    while len(out) < n:
        r = math.sqrt(rng.uniform(r0**2, r1**2)); a = rng.uniform(0, 2*math.pi); out.append((r, a))
    return out
hole = [(25*math.cos(math.radians(60*k)), 25*math.sin(math.radians(60*k))) for k in range(6)]
# mounting ring: solid just above Y -4, empty just below, outside the holes
P_in, P_out = [], []
for r, a in ring(15.3, 30.8, 300):
    x, z = r*math.cos(a), r*math.sin(a)
    if min(math.hypot(x-hx, z-hz) for hx, hz in hole) < 2.6: continue
    P_in.append((x, -3.9, z)); P_out.append((x, -4.1, z))
frac('ring solid at Y -3.9', P_in, True); frac('ring empty at Y -4.1 (flat, nothing proud)', P_out, False)
# holes
P = [(hx+r*math.cos(a), y, hz+r*math.sin(a)) for hx, hz in hole for r, a in ring(0, 1.6, 8) for y in (-3.9, 0, 3.9)]
frac('six D3.4 holes clear', P, False)
P = [(hx+r*math.cos(a), y, hz+r*math.sin(a)) for hx, hz in hole for r, a in [(1.85, t) for t in np.linspace(0, 6.28, 8)] for y in (-3.5, 0, 3.5)]
frac('hole walls solid at r 1.85', P, True)
frac('D30 bore clear', [(r*math.cos(a), y, r*math.sin(a)) for r, a in ring(0, 14.8, 150) for y in (-3.9, 0, 3.9)], False)
frac('D7 x 10 screw clearances clear (Y 4.2 to 13.8)', [(hx+r*math.cos(a), y, hz+r*math.sin(a)) for hx, hz in hole for r, a in ring(0, 3.4, 15) for y in (4.2, 7, 10, 13.8)], False)
# wrist
frac('pin D8 clear (Y -30 to 30)', [(r*math.cos(a), y, -200+r*math.sin(a)) for r, a in ring(0, 3.9, 40) for y in np.linspace(-30, 30, 15)], False)
lig = {}
for y in (16.2, 17, 18, 19, 20, 21):
    pts = [(r*math.cos(a), y, -200+r*math.sin(a)) for r, a in ring(4.1, 9.0, 150)]
    ins = sheet.inside(tris, np.array(pts)); lig[y] = float(ins.mean())
res['ligament_fraction_solid_r4_to_9_by_y'] = lig; print('ligament r 4..9 solid fraction by y', lig)
for sgn in (1, -1):
    frac(f'cheek inner face Y {sgn*16} flat over D16: solid behind', [(r*math.cos(a), sgn*16.1, -200+r*math.sin(a)) for r, a in ring(4.3, 7.9, 100)], True)
    frac(f'cheek inner face Y {sgn*16} flat over D16: clear in front', [(r*math.cos(a), sgn*15.9, -200+r*math.sin(a)) for r, a in ring(4.3, 7.9, 100)], False)
frac('slot clear |Y|<15.9, Z -183.2 to -230', [(rng.uniform(-30, 30), rng.uniform(-15.9, 15.9), rng.uniform(-230, -183.2)) for _ in range(1500)], False)
frac('D30 swing cylinder clear (Y +-15.9)', [(r*math.cos(a), y, -200+r*math.sin(a)) for r, a in ring(0, 15, 100) for y in (-15.9, 0, 15.9)], False)
# cable passage
frac('D6 cable passage clear, Z -15 to -183, X 0 Y 2', [(r*math.cos(a), 2.0 + r*math.sin(a), z) for r, a in ring(0, 2.95, 20) for z in np.linspace(-15, -183, 40)], False)
frac('cable passage walls solid at r 3.4 below Z -34', [(3.4*math.cos(a), 2.0 + 3.4*math.sin(a), z) for a in np.linspace(0, 6.28, 8, endpoint=False) for z in np.linspace(-34, -180, 30)], True)
# thinnest wall round the passage by section
w = []
for z in np.linspace(-15.5, -180, 40):
    sec = trimesh.intersections.mesh_plane(mesh, [0, 0, 1], [0, 0, z])
    seg = sec.reshape(-1, 3)[:, :2]
    dist = np.hypot(seg[:, 0], seg[:, 1] - 2.0)
    w.append(float(dist[dist > 3.2].min() - 3.0))
res['min_wall_round_passage_mm'] = min(w); print('min wall around the cable passage', min(w))
res['mass_g'] = float(mesh.volume * 1.19e-3); res['volume'] = float(mesh.volume)
res['watertight'] = bool(mesh.is_watertight); res['bodies'] = len(mesh.split())
res['bounds'] = mesh.bounds.tolist()
res['shape'] = sheet.shape_stats(tris)
print({k: res[k] for k in ('mass_g', 'volume', 'watertight', 'bodies', 'bounds')})
res['all_ok'] = all(v['ok'] for v in res.values() if isinstance(v, dict) and 'ok' in v)
(OUT / 'c2_checks.json').write_text(json.dumps(res, indent=1, default=float))
print('ALL OK' if res['all_ok'] else 'SOME FAILED')

