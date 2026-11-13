"""C1: the boxy forearm link. Frame X,Y,Z mm, joint axes along Y."""
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *
import sheet
OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-c2'
OUT.mkdir(parents=True, exist_ok=True)

# hand volume (mm3). overlap beam/disc by numeric integration over the X-Z plane
xs = np.linspace(-20, 20, 4001); zs = np.linspace(-35, -32, 3001)
X, Z = np.meshgrid(xs, zs)
ov_area = ((X**2 + Z**2) <= 35**2).mean() * 40 * 3
ov = ov_area * 8     # disc is 8 thick (inside beam's Y +-15)
DISC = math.pi * 35**2 * 8
BORE = math.pi * 15**2 * 8
HOLES = 6 * math.pi * 1.7**2 * 8
BEAM = 40 * 30 * 138
BLOCK_NEW = 40 * 44 * 10   # beam ends at Z -170, the block starts there: no overlap (first try subtracted one in error)
CHEEKS_NEW = 2 * 30 * 6 * 45 - 2 * 30 * 6 * 10
PIN = 2 * math.pi * 16 * 6
HAND = DISC - BORE - HOLES + BEAM - ov + BLOCK_NEW + CHEEKS_NEW - PIN

with job(wait_s=1800) as j:
    d = new_part(j.sw, OUT / 'link_boxy.SLDPRT')
    with Sk(d, plane(d, 'Y', 0.0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), 35.0)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID, expect_dv=DISC)
    with Sk(d, plane(d, 'Y', 0.0, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 0), 15.0)
    extrude(d, s.feat, 'BORE', 10.0, cut=True, mode=MID, expect_dv=BORE)
    with Sk(d, plane(d, 'Y', 0.0, 'HOLES_P'), 'HOLES') as s:
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((25 * math.cos(a), 0, 25 * math.sin(a)), 1.7)
    extrude(d, s.feat, 'HOLES', 10.0, cut=True, mode=MID, expect_dv=HOLES)
    save(d)
    with Sk(d, plane(d, 'Z', -101.0, 'BEAM_P'), 'BEAM') as s:
        s.rect((-20, -15, -101.0), (20, 15, -101.0))
    extrude(d, s.feat, 'BEAM', 138.0, mode=MID, expect_dv=BEAM - ov)
    with Sk(d, plane(d, 'Z', -175.0, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((-20, -22, -175.0), (20, 22, -175.0))
    extrude(d, s.feat, 'BLOCK', 10.0, mode=MID, expect_dv=BLOCK_NEW)
    with Sk(d, plane(d, 'Z', -192.5, 'CHEEK_P'), 'CHEEKS') as s:
        s.rect((-15, 16, -192.5), (15, 22, -192.5))
        s.rect((-15, -22, -192.5), (15, -16, -192.5))
    extrude(d, s.feat, 'CHEEKS', 45.0, mode=MID, expect_dv=CHEEKS_NEW)
    with Sk(d, plane(d, 'Y', 0.0, 'PIN_P'), 'PIN') as s:
        s.circle((0, 0, -200), 4.0)
    extrude(d, s.feat, 'PIN', 60.0, cut=True, mode=MID, expect_dv=PIN)
    save(d)
    expect('hand volume', volume(d), HAND, 0.005)
    log('bbox', bbox(d), 'bodies', len(bodies(d)), 'errors', feature_errors(d))
    single_body(d)
    save(d)
    export(j.sw, d, OUT / 'link_boxy.step')
    export(j.sw, d, OUT / 'link_boxy.stl')
    vol = volume(d); bb = bbox(d)
    close(j.sw, d)

import trimesh, json
mesh = trimesh.load(OUT / 'link_boxy.stl')
tris = sheet.read_stl(OUT / 'link_boxy.stl')
st = sheet.shape_stats(tris)
res = dict(volume_mm3=vol * 1e9 if vol < 1 else vol, hand_volume_mm3=HAND, mass_g=mesh.volume * 1.19e-3,
           bodies=len(mesh.split()), watertight=bool(mesh.is_watertight), stl_volume=float(mesh.volume), shape=st,
           bounds=mesh.bounds.tolist())
print(json.dumps(res, indent=1, default=float))
(OUT / 'c1.json').write_text(json.dumps(res, indent=1, default=float))
