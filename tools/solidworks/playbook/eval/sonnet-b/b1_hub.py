"""B1: flanged hub from a specification. Run: python b1_hub.py"""
import json, math, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-b'
OUT.mkdir(parents=True, exist_ok=True)

# ---- specification constants (TASKS_B.md B1) ----
R_FL, T_FL = 30.0, 5.0
R_BOSS, Z_TOP = 13.0, 25.0
R_BORE = 5.0
R_H6, PCD6 = 2.25, 22.0          # six holes: radius, pitch circle radius
R_DW, PCD_DW = 2.75, 15.0        # dowel holes
KEY_W, KEY_FLOOR = 3.0, 6.4
R_SS, Z_SS = 2.0, 22.6


def hand_volume():
    v = math.pi * R_FL ** 2 * T_FL + math.pi * R_BOSS ** 2 * (Z_TOP - T_FL)
    v -= math.pi * R_BORE ** 2 * Z_TOP
    v -= 6 * math.pi * R_H6 ** 2 * T_FL
    v -= 2 * math.pi * R_DW ** 2 * T_FL      # cut z 0..5 only: the 0.75 mm sliver under the boss is cut too (hole is entirely in the flange)
    # keyway: area of strip |y|<=1.5, x from bore circle to 6.4
    ys = np.linspace(-KEY_W / 2, KEY_W / 2, 200001)
    xb = np.sqrt(R_BORE ** 2 - ys ** 2)
    area = np.trapezoid(KEY_FLOOR - xb, ys)
    v -= area * Z_TOP
    # set screw hole: disc radius 2 in (x,z) at z=22.6, along +Y, from bore wall to boss outer wall; length in material
    xs = np.linspace(-R_SS, R_SS, 4001)
    tot = 0.0
    for x in xs[:-1]:
        pass
    n = 3000
    xg = (np.arange(n) + 0.5) / n * 2 * R_SS - R_SS
    zg = (np.arange(n) + 0.5) / n * 2 * R_SS - R_SS
    X, Z = np.meshgrid(xg, zg)
    inside = X ** 2 + Z ** 2 <= R_SS ** 2
    length = np.sqrt(R_BOSS ** 2 - X ** 2) - np.sqrt(R_BORE ** 2 - X ** 2)
    ss = float((length * inside).sum() * (2 * R_SS / n) ** 2)
    v -= ss
    return v, dict(keyway_area=area, setscrew=ss)


hv, parts = hand_volume()
print('hand volume', hv, parts, flush=True)
with job() as j:
    t0 = time.time()
    path = OUT / 'hub.SLDPRT'
    d = new_part(j.sw, path)

    with Sk(d, plane(d, 'Z', 2.5, 'FLANGE_P'), 'FLANGE') as s:
        s.circle((0, 0, 2.5), R_FL)
    extrude(d, s.feat, 'FLANGE', T_FL, mode=MID, expect_dv=math.pi * R_FL ** 2 * T_FL)
    with Sk(d, plane(d, 'Z', 15.0, 'BOSS_P'), 'BOSS') as s:
        s.circle((0, 0, 15.0), R_BOSS)
    extrude(d, s.feat, 'BOSS', Z_TOP - T_FL, mode=MID, expect_dv=math.pi * R_BOSS ** 2 * 20)
    save(d)
    with Sk(d, plane(d, 'Z', 12.5, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 12.5), R_BORE)
    extrude(d, s.feat, 'BORE', Z_TOP, cut=True, mode=MID, expect_dv=math.pi * R_BORE ** 2 * Z_TOP)
    with Sk(d, plane(d, 'Z', 2.5, 'HOLES6_P'), 'HOLES6') as s:
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((PCD6 * math.cos(a), PCD6 * math.sin(a), 2.5), R_H6)
    extrude(d, s.feat, 'HOLES6', T_FL, cut=True, mode=MID, expect_dv=6 * math.pi * R_H6 ** 2 * T_FL)
    with Sk(d, plane(d, 'Z', 2.5, 'DOWEL_P'), 'DOWEL') as s:
        s.circle((0, PCD_DW, 2.5), R_DW)
        s.circle((0, -PCD_DW, 2.5), R_DW)
    extrude(d, s.feat, 'DOWEL', T_FL, cut=True, mode=MID, expect_dv=2 * math.pi * R_DW ** 2 * T_FL)
    save(d)
    # keyway: x from 4.0 (inside the bore) to 6.4; y +-1.5; full length
    v0 = volume(d)
    with Sk(d, plane(d, 'Z', 12.5, 'KEY_P'), 'KEYWAY') as s:
        s.rect((4.0, -KEY_W / 2, 12.5), (KEY_FLOOR, KEY_W / 2, 12.5))
    extrude(d, s.feat, 'KEYWAY', Z_TOP, cut=True, mode=MID, expect_dv=parts['keyway_area'] * Z_TOP)
    # set screw, along +Y from the axis to past the outside (y 0..14)
    with Sk(d, plane(d, 'Y', 7.0, 'SS_P'), 'SETSCREW') as s:
        s.circle((0, 7.0, Z_SS), R_SS)
    extrude(d, s.feat, 'SETSCREW', 14.0, cut=True, mode=MID, expect_dv=parts['setscrew'])
    save(d)
    single_body(d)
    errs = feature_errors(d)
    vol = volume(d)
    bb = bbox(d)
    log('volume', vol, 'hand', hv, 'bbox', bb, 'errors', errs)
    expect('hub volume', vol, hv, 0.001)
    for k, want in enumerate((-30, -30, 0, 30, 30, 25)):
        expect(f'box[{k}]', bb[k], want, 0.01)

    # measure every feature on the finished solid
    cyls = []
    for f in faces(d):
        i = face_info(f)
        if i['kind'] == 'cyl':
            b = i['box']
            cyls.append((round(i['r'], 3), round((b[0] + b[3]) / 2, 3), round((b[1] + b[4]) / 2, 3), round(b[2], 3), round(b[5], 3), round(i['area'], 2)))
    for c in sorted(cyls):
        log('cyl r, cx, cy, z0, z1, area', c)
    # planes
    for f in faces(d):
        i = face_info(f)
        if i['kind'] == 'plane':
            log('plane n', i['normal'], 'box', [round(v, 3) for v in i['box']], 'area', round(i['area'], 2))
    close(j.sw, d) if False else None
    d.ForceRebuild3(False)
    export(j.sw, d, OUT / 'hub.step')
    export(j.sw, d, OUT / 'hub.stl')
    save(d)
    # mass
    mass = vol * 1.19e-3
    close(j.sw, d)
    import trimesh
    mesh = trimesh.load(OUT / 'hub.stl')
    wt = bool(mesh.is_watertight)
    shells = len(mesh.split())
    log('STL watertight', wt, 'shells', shells, 'vol', mesh.volume, 'bounds', mesh.bounds.tolist())
    step_txt = (OUT / 'hub.step').read_text(errors='ignore')
    mm = any('SI_UNIT' in l and '.MILLI.' in l for l in step_txt.splitlines())
    log('STEP mm', mm)
    res = dict(volume_mm3=round(vol, 2), hand_volume_mm3=round(hv, 2), mass_g=round(mass, 3), bbox_mm=[round(v, 3) for v in bb],
               bodies=1, stl_watertight=wt, stl_volume=round(float(mesh.volume), 2), stl_bounds=mesh.bounds.round(3).tolist(), step_mm=mm,
               cylinders=sorted(cyls), seconds=round(time.time() - t0))
    (OUT / 'b1_measured.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
