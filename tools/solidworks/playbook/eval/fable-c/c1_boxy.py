"""C1: the forearm link as an engineer first draws it. Frame X, Y, Z in mm, joint axes along Y."""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
from swkit import *          # noqa
OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'fable-c'
HERE = Path(__file__).resolve().parent

R_DISC, T_DISC, R_BORE, R_BOLT, R_PCD = 35.0, 8.0, 15.0, 1.7, 25.0     # TASKS_C.md C1
seg = R_DISC ** 2 * math.acos(32 / R_DISC) - 32 * math.sqrt(R_DISC ** 2 - 32 ** 2)   # disc below Z -32, inside the beam
V_DISC = math.pi * R_DISC ** 2 * T_DISC
V_BEAM = 40 * 30 * 138 - seg * T_DISC
V_BLOCK = 40 * 44 * 10
V_CHEEK = 2 * 30 * 6 * 35
V_HOLES = math.pi * R_BORE ** 2 * T_DISC + 6 * math.pi * R_BOLT ** 2 * T_DISC
V_PIN = 2 * math.pi * 16 * 6
HAND = V_DISC + V_BEAM + V_BLOCK + V_CHEEK - V_HOLES - V_PIN
log('hand volume', round(HAND, 1))

with job() as j:
    d = new_part(j.sw, OUT / 'link_boxy.SLDPRT')
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), R_DISC)
    extrude(d, s.feat, 'DISC', T_DISC, mode=MID, expect_dv=V_DISC)
    with Sk(d, plane(d, 'Z', -101.0, 'BEAM_P'), 'BEAM') as s:
        s.rect((-20, -15, -101.0), (20, 15, -101.0))
    extrude(d, s.feat, 'BEAM', 138.0, mode=MID, expect_dv=V_BEAM)
    with Sk(d, plane(d, 'Z', -175.0, 'BLOCK_P'), 'FORK_BLOCK') as s:
        s.rect((-20, -22, -175.0), (20, 22, -175.0))
    extrude(d, s.feat, 'FORK_BLOCK', 10.0, mode=MID, expect_dv=V_BLOCK)
    with Sk(d, plane(d, 'Z', -197.5, 'CHEEK_P'), 'CHEEKS') as s:
        s.rect((-15, 16, -197.5), (15, 22, -197.5))
        s.rect((-15, -22, -197.5), (15, -16, -197.5))
    extrude(d, s.feat, 'CHEEKS', 35.0, mode=MID, expect_dv=V_CHEEK)
    save(d)
    with Sk(d, plane(d, 'Y', 0, 'X'), 'ELBOW_HOLES') as s:
        s.circle((0, 0, 0), R_BORE)
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((R_PCD * math.cos(a), 0, R_PCD * math.sin(a)), R_BOLT)
    extrude(d, s.feat, 'ELBOW_HOLES', T_DISC, cut=True, mode=MID, expect_dv=V_HOLES)
    with Sk(d, plane(d, 'Y', 0, 'X'), 'PIN_HOLE') as s:
        s.circle((0, 0, -200.0), 4.0)
    extrude(d, s.feat, 'PIN_HOLE', 44.0, cut=True, mode=MID, expect_dv=V_PIN)
    single_body(d)
    expect('volume', volume(d), HAND, 0.001)
    b = bbox(d)
    for k, want in enumerate((-35, -22, -215, 35, 22, 35)):
        expect(f'box[{k}]', b[k], want, 0.01)
    # every specified dimension measured on the solid
    meas = {}
    for name, r, n in (('bore', 15.0, 1), ('bolt', 1.7, 6), ('pin', 4.0, 2)):
        fs = pick(d, kind='cyl', r=r)
        expect(name + ' faces', len(fs), n, 0)
        meas[name] = [[round(v, 3) for v in face_info(f)['box']] for f in fs]
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    save(d)
    export(j.sw, d, OUT / 'link_boxy.stl')
    res = dict(volume_mm3=round(volume(d), 1), hand_volume_mm3=round(HAND, 1), mass_g=round(volume(d) * 1.19e-3, 2),
               bodies=len(bodies(d)), bbox=b, holes=meas)
    close(j.sw, d)
import trimesh
mesh = trimesh.load(OUT / 'link_boxy.stl')
expect('STL watertight', float(mesh.is_watertight), 1.0, 0)
expect('STL volume', float(mesh.volume), HAND, 0.005)
expect('STL min z', float(mesh.bounds[0][2]), -215.0, 0.01)
res['stl'] = dict(watertight=bool(mesh.is_watertight), shells=len(mesh.split()), volume=round(float(mesh.volume), 1))
(HERE / 'c1_results.json').write_text(json.dumps(res, indent=1))
print(json.dumps(res))
