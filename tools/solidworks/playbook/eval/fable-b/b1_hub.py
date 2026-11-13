"""B1: flanged hub from the specification in TASKS_B.md. Axis along Z, mm."""
import math

from common import DENS, WIP, cyl, put, sha
from swkit import *

import numpy as np

# ---- the specification (TASKS_B.md, B1) ------------------------------------------------------------------------------
FL_R, FL_Z0, FL_Z1 = 30.0, 0.0, 5.0            # flange dia 60, Z 0 to 5
BO_R, BO_Z1 = 13.0, 25.0                       # boss dia 26, Z 5 to 25
BORE_R = 5.0                                   # bore dia 10, through
BOLT_R, BOLT_PCR, BOLT_N = 2.25, 22.0, 6       # six dia 4.5 on a dia 44 circle, first on +X
DOW_R, DOW_PCR = 2.75, 15.0                    # two dia 5.5 on a dia 30 circle, +Y and -Y
KEY_W, KEY_FLOOR = 3.0, 6.4                    # keyway 3 wide on +X, floor 6.4 from the axis
SS_R, SS_Z = 2.0, 22.6                         # dia 4 set-screw hole along +Y at Z 22.6, bore to outside

# ---- hand volumes -----------------------------------------------------------------------------------------------------
v_flange = math.pi * FL_R ** 2 * (FL_Z1 - FL_Z0)
v_boss = math.pi * BO_R ** 2 * (BO_Z1 - FL_Z1)
v_bore = math.pi * BORE_R ** 2 * BO_Z1
v_bolts = BOLT_N * math.pi * BOLT_R ** 2 * (FL_Z1 - FL_Z0)
v_dowels = 2 * math.pi * DOW_R ** 2 * (FL_Z1 - FL_Z0)
h = KEY_W / 2                                  # keyway: the rectangle beyond the bore circle
a_key = KEY_W * KEY_FLOOR - 2 * (h / 2 * math.sqrt(BORE_R ** 2 - h ** 2) + BORE_R ** 2 / 2 * math.asin(h / BORE_R))
v_key = a_key * BO_Z1
xs = np.linspace(-SS_R, SS_R, 400001)          # set screw: a dia 4 cylinder between the bore and the boss surface
f = 2 * np.sqrt(np.maximum(SS_R ** 2 - xs ** 2, 0)) * (np.sqrt(BO_R ** 2 - xs ** 2) - np.sqrt(BORE_R ** 2 - xs ** 2))
v_ss = float(np.sum((f[1:] + f[:-1]) / 2 * np.diff(xs)))
HAND = v_flange + v_boss - v_bore - v_bolts - v_dowels - v_key - v_ss
log(f'hand: flange {v_flange:.2f} boss {v_boss:.2f} bore {v_bore:.2f} bolts {v_bolts:.2f} dowels {v_dowels:.2f} '
    f'key {v_key:.2f} setscrew {v_ss:.2f} -> {HAND:.2f} mm3')

P = WIP / 'hub.SLDPRT'
with job() as j:
    d = new_part(j.sw, P)
    with Sk(d, plane(d, 'Z', 2.5, 'FLANGE_P'), 'FLANGE') as s:
        s.circle((0, 0, 2.5), FL_R)
    extrude(d, s.feat, 'FLANGE', 5.0, mode=MID, expect_dv=v_flange)
    with Sk(d, plane(d, 'Z', 15.0, 'BOSS_P'), 'BOSS') as s:
        s.circle((0, 0, 15.0), BO_R)
    extrude(d, s.feat, 'BOSS', 20.0, mode=MID, expect_dv=v_boss)
    save(d)
    with Sk(d, plane(d, 'Z', 12.5, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 12.5), BORE_R)
    extrude(d, s.feat, 'BORE', 25.0, cut=True, mode=MID, expect_dv=v_bore)
    with Sk(d, plane(d, 'Z', 2.5, 'BOLT_P'), 'BOLT_HOLES') as s:
        for k in range(BOLT_N):
            a = math.radians(60 * k)
            s.circle((BOLT_PCR * math.cos(a), BOLT_PCR * math.sin(a), 2.5), BOLT_R)
    extrude(d, s.feat, 'BOLT_HOLES', 5.0, cut=True, mode=MID, expect_dv=v_bolts)
    # "through the flange": Z 0 to 5 only. The holes reach r 17.75 from r 12.25 and the boss is r 13, so 0.75 mm of each
    # hole lies under the boss; cutting further would gouge the boss, which the specification does not ask for.
    with Sk(d, plane(d, 'Z', 2.5, 'DOWEL_P'), 'DOWEL_HOLES') as s:
        s.circle((0, DOW_PCR, 2.5), DOW_R)
        s.circle((0, -DOW_PCR, 2.5), DOW_R)
    extrude(d, s.feat, 'DOWEL_HOLES', 5.0, cut=True, mode=MID, expect_dv=v_dowels)
    save(d)
    # keyway: the tool starts inside the bore (x 3) so no face is nearly flush with the bore wall
    with Sk(d, plane(d, 'Z', 12.5, 'KEY_P'), 'KEYWAY') as s:
        s.rect((3.0, -KEY_W / 2, 12.5), (KEY_FLOOR, KEY_W / 2, 12.5))
    extrude(d, s.feat, 'KEYWAY', 25.0, cut=True, mode=MID, expect_dv=v_key)
    # set screw: tool from y 4 (inside the bore) to y 14 (outside the boss), mid plane y 9
    with Sk(d, plane(d, 'Y', 9.0, 'SS_P'), 'SETSCREW') as s:
        s.circle((0, 9.0, SS_Z), SS_R)
    extrude(d, s.feat, 'SETSCREW', 10.0, cut=True, mode=MID, expect_dv=v_ss)
    save(d)

    # ---- checks: totals ----
    V = volume(d)
    expect('hub volume', V, HAND, 0.001)
    b = bbox(d)
    for k, want in enumerate((-30, -30, 0, 30, 30, 25)):
        expect(f'box[{k}]', b[k], want, 0.01)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    nb = len(bodies(d))

    # ---- checks: every dimension measured on the solid ----
    meas = {}

    def one(what, fs, n=1):
        expect(what + ' face count', len(fs), n, 0)
        return fs

    fl = one('flange OD', pick(d, kind='cyl', r=FL_R))[0]
    c, ax, r = cyl(fl)
    i = face_info(fl)
    meas['flange'] = dict(r=r, axis_xy=c[:2], z=[i['box'][2], i['box'][5]])
    expect('flange axis x', c[0], 0, 0.001); expect('flange axis y', c[1], 0, 0.001)
    expect('flange z0', i['box'][2], 0, 0.001); expect('flange z1', i['box'][5], 5, 0.001)
    bo = one('boss OD', pick(d, kind='cyl', r=BO_R))[0]
    c, ax, r = cyl(bo)
    i = face_info(bo)
    meas['boss'] = dict(r=r, axis_xy=c[:2], z=[i['box'][2], i['box'][5]])
    expect('boss axis x', c[0], 0, 0.001); expect('boss axis y', c[1], 0, 0.001)
    expect('boss z0', i['box'][2], 5, 0.001); expect('boss z1', i['box'][5], 25, 0.001)
    br = one('bore', pick(d, kind='cyl', r=BORE_R))[0]
    c, ax, r = cyl(br)
    i = face_info(br)
    meas['bore'] = dict(r=r, axis_xy=c[:2], z=[i['box'][2], i['box'][5]])
    expect('bore axis x', c[0], 0, 0.001); expect('bore axis y', c[1], 0, 0.001)
    expect('bore z0', i['box'][2], 0, 0.001); expect('bore z1', i['box'][5], 25, 0.001)
    got = []
    for fc in one('bolt holes', pick(d, kind='cyl', r=BOLT_R), 6):
        c, ax, r = cyl(fc)
        i = face_info(fc)
        expect('bolt hole |axis z|', abs(ax[2]), 1, 0.001)
        expect('bolt hole z0', i['box'][2], 0, 0.001); expect('bolt hole z1', i['box'][5], 5, 0.001)
        got.append((round(math.degrees(math.atan2(c[1], c[0])) % 360, 3), round(math.hypot(c[0], c[1]), 4), round(r, 4)))
    got.sort()
    meas['bolt_holes_angle_pcr_r'] = got
    for k, g in enumerate(got):
        expect(f'bolt hole {k} angle', g[0], 60.0 * k, 0.01)
        expect(f'bolt hole {k} pitch radius', g[1], BOLT_PCR, 0.001)
    got = []
    for fc in pick(d, kind='cyl', r=DOW_R):
        c, ax, r = cyl(fc)
        i = face_info(fc)
        got.append(dict(centre=[round(v, 4) for v in c[:2]], r=round(r, 4), z=[round(i['box'][2], 3), round(i['box'][5], 3)],
                        area=round(i['area'], 2)))
    meas['dowel_hole_faces'] = got
    log('dowel faces', got)
    cs = sorted({tuple(g['centre']) for g in got})
    expect('dowel centres', len(cs), 2, 0)
    expect('dowel -Y centre y', cs[0][1], -DOW_PCR, 0.001); expect('dowel +Y centre y', cs[1][1], DOW_PCR, 0.001)
    expect('dowel centre x', cs[0][0], 0, 0.001); expect('dowel centre x', cs[1][0], 0, 0.001)
    for g in got:
        expect('dowel z0', g['z'][0], 0, 0.001); expect('dowel z1', g['z'][1], 5, 0.001)
    # the blind lune under the boss: the flat face at Z 5 inside each dowel hole (the boss underside)
    lune = [f for f in pick(d, kind='plane', normal=(0, 0, -1)) if face_info(f)['box'][2] > 4.9]
    meas['dowel_lunes_under_boss'] = [dict(area=round(face_info(f)['area'], 3), box=[round(v, 3) for v in face_info(f)['box']]) for f in lune]
    log('boss underside faces inside the dowel holes', meas['dowel_lunes_under_boss'])
    kf = one('keyway floor', pick(d, kind='plane', normal=(-1, 0, 0), at=(KEY_FLOOR, 0, 12.5)))[0]
    i = face_info(kf)
    meas['keyway_floor'] = dict(x=i['box'][0], y=[i['box'][1], i['box'][4]], z=[i['box'][2], i['box'][5]])
    expect('keyway floor x', i['box'][0], KEY_FLOOR, 0.001)
    expect('keyway y0', i['box'][1], -1.5, 0.001); expect('keyway y1', i['box'][4], 1.5, 0.001)
    expect('keyway z0', i['box'][2], 0, 0.001); expect('keyway z1', i['box'][5], 25, 0.001)
    ss = one('set-screw hole', pick(d, kind='cyl', r=SS_R))[0]
    c, ax, r = cyl(ss)
    i = face_info(ss)
    meas['setscrew'] = dict(r=r, axis_point=c, axis_dir=ax, box=i['box'])
    expect('set screw |axis y|', abs(ax[1]), 1, 0.001)
    expect('set screw axis x', c[0], 0, 0.001); expect('set screw axis z', c[2], SS_Z, 0.001)
    expect('set screw reaches the outside (y max)', i['box'][4], BO_R, 0.001)
    # GetBox on this face is not tight (4.458 against the true 4.583 = sqrt(25 - 4) where the hole meets the bore), so the
    # check is only that the face starts inside the bore radius: the hole breaks through into the bore
    expect('set screw starts at the bore (y min, loose face box)', i['box'][1], math.sqrt(BORE_R ** 2 - SS_R ** 2), 0.15)
    expect('set screw top z', i['box'][5], SS_Z + SS_R, 0.01)
    meas['wall_above_setscrew_mm'] = BO_Z1 - i['box'][5]
    save(d)

    export(j.sw, d, str(WIP / 'hub.step'))
    export(j.sw, d, str(WIP / 'hub.stl'))
    close(j.sw, d)

import trimesh
mesh = trimesh.load(WIP / 'hub.stl')
wt, shells = bool(mesh.is_watertight), len(mesh.split())
expect('STL watertight', float(wt), 1, 0)
expect('STL shells', shells, 1, 0)
expect('STL volume', float(mesh.volume), V, 0.005)
for k, want in enumerate((-30, -30, 0, 30, 30, 25)):
    expect(f'STL bounds[{k}]', float(mesh.bounds.flatten()[k]), want, 0.02)
step = (WIP / 'hub.step').read_text(errors='ignore')
step_mm = any('SI_UNIT' in ln and '.MILLI.' in ln for ln in step.splitlines())
expect('STEP in mm', float(step_mm), 1, 0)

put('b1', dict(volume_mm3=round(V, 2), hand_volume_mm3=round(HAND, 2), mass_g=round(V * DENS, 3), bbox_mm=[round(v, 3) for v in b],
               bodies=nb, stl_watertight=wt, stl_shells=shells, stl_volume_mm3=round(float(mesh.volume), 2), step_mm=step_mm,
               hand_parts=dict(flange=v_flange, boss=v_boss, bore=v_bore, bolts=v_bolts, dowels=v_dowels, keyway=v_key, setscrew=v_ss),
               measured=meas, sha256=sha(P)))
print('B1 DONE')
