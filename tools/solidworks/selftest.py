"""Prove swkit and swfea against hand answers on this machine's SolidWorks. Also the worked example for the playbook.

    python tools/solidworks/selftest.py [model] [beam] [rod]        # all three when none is named

Writes to cad/_wip/sw-selftest/ (gitignored) and prints PASS or the first check that failed. Run it on a machine or a
SolidWorks version the helpers have not been used on, and after changing swkit.py or swfea.py. About two minutes.

  model: a 60 x 30 x 10 plate with a through hole and four rounded corners; volume, box and both exports are checked.
  beam:  a 100 x 10 x 10 cantilever with 10 N at the tip through a remote load, against F L^3 / 3 E I.
  rod:   a 20 mm round bar, 50 long, with 100 N pressed on its end through a normal force, against F L / A E.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from swfea import PETG, SOLVER_DIRECT, static  # noqa: E402
from swkit import (BLIND, MID, Sk, bbox, bodies, chamfer, close, cut_half_space, delete_body, edges_where,  # noqa: E402
                   expect, export, extrude, feature_errors, fillet, import_step, insert_body, job, list_faces, loft, log,
                   new_part, open_doc, pick, plane, revolve, save, shell, single_body, volume)

OUT = Path(__file__).resolve().parents[2] / 'cad' / '_wip' / 'sw-selftest'


def model(j):
    d = new_part(j.sw, OUT / 'plate.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'PLATE_P'), 'PLATE') as s:
        s.rect((0, 0, 5.0), (60, 30, 5.0))
    extrude(d, s.feat, 'PLATE', 10.0, mode=MID, expect_dv=60 * 30 * 10)
    with Sk(d, plane(d, 'Z', 5.0, 'HOLE_P'), 'HOLE') as s:
        s.circle((15, 15, 5.0), 4.0)
    extrude(d, s.feat, 'HOLE', 10.0, cut=True, mode=MID, expect_dv=math.pi * 16 * 10)
    save(d)
    # the four corner edges run along Z: both end points sit on a corner of the outline
    corners = edges_where(d, lambda p: min(abs(p[0]), abs(p[0] - 60)) < 0.01 and min(abs(p[1]), abs(p[1] - 30)) < 0.01)
    expect('corner edges found', len(corners), 4, 0)
    if fillet(d, corners, (3.0,), 'CORNERS') is None:
        raise SystemExit('FAIL: corner round did not build')
    expect('plate volume', volume(d), 60 * 30 * 10 - math.pi * 160 - (4 - math.pi) * 9 * 10, 0.001)
    b = bbox(d)
    for k, want in enumerate((0, 0, 0, 60, 30, 10)):
        expect(f'box[{k}]', b[k], want, 0.01)
    expect('hole faces', len(pick(d, kind='cyl', r=4.0)), 1, 0)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    save(d)
    export(j.sw, d, OUT / 'plate.step')
    export(j.sw, d, OUT / 'plate.stl')
    close(j.sw, d)
    try:
        import trimesh
        mesh = trimesh.load(OUT / 'plate.stl')
        expect('STL watertight', float(mesh.is_watertight), 1.0, 0)
        expect('STL volume (mm, model frame)', float(mesh.volume), 60 * 30 * 10 - math.pi * 160 - (4 - math.pi) * 90, 0.005)
        expect('STL min x (not shifted)', float(mesh.bounds[0][0]), 0.0, 0.01)
    except ImportError:
        log('trimesh not installed: STL not checked')


def beam(j):
    d = new_part(j.sw, OUT / 'beam.SLDPRT')
    with Sk(d, plane(d, 'X', 50.0, 'BEAM_P'), 'BEAM') as s:
        s.rect((50.0, 0, 0), (50.0, 10, 10))
    extrude(d, s.feat, 'BEAM', 100.0, mode=MID, expect_dv=100 * 10 * 10)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'beam.SLDPRT')
    root = pick(d, kind='plane', normal=(-1, 0, 0))
    tip = pick(d, kind='plane', normal=(1, 0, 0))
    expect('root faces', len(root), 1, 0)
    expect('tip faces', len(tip), 1, 0)
    r = static(j, d, 'BEAM_TIP_10N', PETG, fixtures=[('fixed', root)],
               loads=[('remote', tip, (100.0, 5.0, 5.0), (0, 0, -10.0), (0, 0, 0))], el=2.0)
    log(r.summary())
    inertia = 0.01 ** 4 / 12
    bend = 10 * 0.1 ** 3 / (3 * PETG['EX'] * inertia) * 1e3
    shear = 6 * 10 * 0.1 / (5 * PETG['EX'] / (2 * (1 + PETG['NUXY'])) * 1e-4) * 1e3
    expect('tip deflection mm', r.max_disp(), bend + shear, 0.03)
    # bending stress on the top and bottom faces, 4 mm from the root (two elements clear of the fixture): M c / I
    expect('peak stress away from the root MPa', r.peak()[0], 10 * (0.1 - 0.004) * 0.005 / inertia / 1e6, 0.08)
    expect('reaction Fz N (opposes the 10 N down)', r.reaction[2], 10.0, 0.01)
    expect('reaction resultant N', r.reaction[3], r.applied, 0.01)
    close(j.sw, d)


def rod(j):
    d = new_part(j.sw, OUT / 'rod.SLDPRT')
    with Sk(d, plane(d, 'Z', 25.0, 'ROD_P'), 'ROD') as s:
        s.circle((0, 0, 25.0), 10.0)
    extrude(d, s.feat, 'ROD', 50.0, mode=MID, expect_dv=math.pi * 100 * 50)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'rod.SLDPRT')
    r = static(j, d, 'ROD_100N', PETG, fixtures=[('fixed', pick(d, kind='plane', normal=(0, 0, -1)))],
               loads=[('normal', pick(d, kind='plane', normal=(0, 0, 1)), 100.0)], el=2.5)
    log(r.summary())
    expect('end shortening mm', r.max_disp(), 100 * 0.05 / (math.pi * 1e-4 * PETG['EX']) * 1e3, 0.03)
    # F / A holds a diameter away from the clamped end: the clamp stops the bar widening, which raises the stress near
    # it (0.336 MPa, 5.5 % over, 11 mm up on 2026-11-12). So the peak is taken in the middle, not "away from the fixture".
    mid = np.abs(r.pos[:, 2] - 30) < 8
    expect('axial stress in the middle MPa', r.peak(mid)[0], 100 / (math.pi * 100), 0.03)
    expect('sz in the middle MPa (a positive normal load pushes in)', float(r.s[mid, 3].mean()), -100 / (math.pi * 100), 0.02)
    expect('reaction Fz N', r.reaction[2], 100.0, 0.01)
    close(j.sw, d)


def loads(j):
    """What the load, result and solver calls mean, each against a hand value (measured 2026-11-12)."""
    # a normal load on two faces is the total: a 20 x 20 block with a step, 100 N over both top faces
    d = new_part(j.sw, OUT / 'steps.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'BASE_P'), 'BASE') as s:
        s.rect((0, 0, 5.0), (20, 20, 5.0))
    extrude(d, s.feat, 'BASE', 10.0, mode=MID, expect_dv=4000)
    with Sk(d, plane(d, 'Z', 12.5, 'STEP_P'), 'STEP') as s:
        s.rect((0, 0, 12.5), (10, 20, 12.5))
    extrude(d, s.feat, 'STEP', 5.0, mode=MID, expect_dv=1000)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'steps.SLDPRT')
    tops = pick(d, kind='plane', normal=(0, 0, 1))
    expect('top faces', len(tops), 2, 0)
    r = static(j, d, 'STEPS_100N', PETG, fixtures=[('fixed', pick(d, kind='plane', normal=(0, 0, -1)))],
               loads=[('normal', tops, 100.0)], el=2.5)
    log(r.summary())
    expect('two-face normal load: reaction Fz N', r.reaction[2], 100.0, 0.01)
    low = np.abs(r.pos[:, 2] - 4) < 2
    expect('two-face normal load: sz in the base MPa', float(r.s[low, 3].mean()), -100 / 400, 0.03)
    close(j.sw, d)

    # a remote moment is in N.m, a remote force placed beyond the tip adds F x arm (location in mm), and the shear
    # columns are txy, txz, tyz: the beam of beam(), bent three ways
    if not (OUT / 'beam.SLDPRT').exists():
        beam(j)
    d = open_doc(j.sw, OUT / 'beam.SLDPRT')
    root, tip = pick(d, kind='plane', normal=(-1, 0, 0)), pick(d, kind='plane', normal=(1, 0, 0))
    ei = PETG['EX'] * 0.01 ** 4 / 12
    at_tip = lambda r: np.abs(r.pos[:, 0] - 100) < 0.01      # noqa: E731

    def uz(r):
        return float(r.disp[at_tip(r), 3].mean())
    r = static(j, d, 'BEAM_MY_1NM', PETG, fixtures=[('fixed', root)],
               loads=[('remote', tip, (100.0, 5.0, 5.0), (0, 0, 0), (0, 1.0, 0))], el=2.0)
    expect('1 N.m about +Y: tip moves down, M L^2 / 2 E I mm', uz(r), -1.0 * 0.1 ** 2 / (2 * ei) * 1e3, 0.03)
    r = static(j, d, 'BEAM_FAR', PETG, fixtures=[('fixed', root)],
               loads=[('remote', tip, (150.0, 5.0, 5.0), (0, 0, -10.0), (0, 0, 0))], el=2.0)
    shear = 6 * 10 * 0.1 / (5 * PETG['EX'] / (2 * (1 + PETG['NUXY'])) * 1e-4) * 1e3
    expect('10 N placed 50 mm beyond the tip mm', uz(r), -(10 * 0.1 ** 3 / (3 * ei) + 10 * 0.05 * 0.1 ** 2 / (2 * ei)) * 1e3 - shear, 0.03)
    mid = np.abs(r.pos[:, 0] - 50) < 10
    expect('txz (column 5) for a -Z load MPa', float(r.s[mid, 5].mean()), -10 / 100, 0.08)
    expect('txy (column 4) for a -Z load MPa', float(r.s[mid, 4].mean()), 0.0, 0.005)
    r = static(j, d, 'BEAM_SIDE', PETG, fixtures=[('fixed', root)],
               loads=[('remote', tip, (100.0, 5.0, 5.0), (0, -10.0, 0), (0, 0, 0))], el=2.0)
    expect('txy (column 4) for a -Y load MPa', float(r.s[mid, 4].mean()), -10 / 100, 0.08)
    expect('txz (column 5) for a -Y load MPa', float(r.s[mid, 5].mean()), 0.0, 0.005)
    expect('reaction Fy N', r.reaction[1], 10.0, 0.01)
    close(j.sw, d)

    # the solver macro: the study still solves, and the fixture and load faces can still be read afterwards
    if not (OUT / 'rod.SLDPRT').exists():
        rod(j)
    d = open_doc(j.sw, OUT / 'rod.SLDPRT')
    r = static(j, d, 'ROD_DIRECT', PETG, fixtures=[('fixed', pick(d, kind='plane', normal=(0, 0, -1)))],
               loads=[('normal', pick(d, kind='plane', normal=(0, 0, 1)), 100.0)], el=2.5, solver=SOLVER_DIRECT)
    text = (OUT / 'solver_ROD_DIRECT.log').read_text()
    if 'after  7' not in text:
        raise SystemExit(f'FAIL: solver macro log does not show the direct solver: {text!r}')
    if r.fixed_pts is None or r.loaded_pts is None:
        raise SystemExit('FAIL: fixture and load faces could not be read after the solver macro')
    expect('direct solver: end shortening mm', r.max_disp(), 100 * 0.05 / (math.pi * 1e-4 * PETG['EX']) * 1e3, 0.03)
    expect('direct solver: axial stress in the middle MPa', r.peak(np.abs(r.pos[:, 2] - 30) < 8)[0], 100 / (math.pi * 100), 0.03)
    expect('direct solver: reaction Fz N', r.reaction[2], 100.0, 0.01)
    close(j.sw, d)


def extras(j):
    # chamfer, half-space cut, shell: a 40 x 20 x 10 block, its four upright edges chamfered 2 mm, cut back to x <= 30,
    # then shelled to a 2 mm wall with the top open
    d = new_part(j.sw, OUT / 'tray.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'TRAY_P'), 'TRAY') as s:
        s.rect((0, 0, 5.0), (40, 20, 5.0))
    extrude(d, s.feat, 'TRAY', 10.0, mode=MID, expect_dv=8000)
    up = edges_where(d, lambda p: min(abs(p[0]), abs(p[0] - 40)) < 0.01 and min(abs(p[1]), abs(p[1] - 20)) < 0.01)
    expect('upright edges found', len(up), 4, 0)
    chamfer(d, up, 2.0, 'CORNER_CH')
    expect('volume after chamfer', volume(d), 8000 - 4 * 2 * 10, 0.001)
    cut_half_space(d, 'X', 30.0, -1, 'TRIM')
    expect('volume after half-space cut', volume(d), 30 * 20 * 10 - 2 * 2 * 10, 0.001)
    expect('box x max after cut', bbox(d)[3], 30.0, 0.01)
    expect('top face picked by a point on it', len(pick(d, kind='plane', at=(15, 10, 10))), 1, 0)
    save(d)
    shell(d, [(15, 10, 10)], 2.0, 'WALL')
    # cavity = the outline moved in by t, 8 deep. For a convex outline: A - P t + t^2 * sum(tan(turn / 2))
    area, per = 30 * 20 - 2 * 2, 28 + 28 + 20 + 16 + 2 * 2 * math.sqrt(2)
    inner = area - per * 2 + 4 * (2 * math.tan(math.pi / 4) + 4 * math.tan(math.pi / 8))
    expect('volume after shell', volume(d), 5960 - inner * 8, 0.002)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    save(d)
    close(j.sw, d)

    # revolve: a ring, 10 to 15 radius, 4 high, about Z; and a half disc drawn with an arc
    d = new_part(j.sw, OUT / 'ring.SLDPRT')
    with Sk(d, plane(d, 'Y', 0.0, 'RING_P'), 'RING') as s:
        s.rect((10, 0, 0), (15, 0, 4))
        s.centerline((0, 0, 0), (0, 0, 10))
    revolve(d, s.feat, 'RING', expect_dv=math.pi * (15 ** 2 - 10 ** 2) * 4)
    b = bbox(d)
    for k, want in enumerate((-15, -15, 0, 15, 15, 4)):
        expect(f'ring box[{k}]', b[k], want, 0.01)
    save(d)
    close(j.sw, d)

    # loft: square 20 to square 10 over 30 (a frustum, h / 3 * (A1 + A2 + sqrt(A1 A2))), then three spline circles
    d = new_part(j.sw, OUT / 'loft.SLDPRT')
    secs = []
    for z, a in ((0.0, 10.0), (30.0, 5.0)):
        with Sk(d, plane(d, 'Z', z, f'SQ{z:.0f}_P'), f'SQ{z:.0f}') as s:
            s.poly([(-a, -a, z), (a, -a, z), (a, a, z), (-a, a, z)])
        secs.append(s.feat)
    loft(d, secs, 'FRUSTUM')
    expect('frustum volume', volume(d), 30 / 3 * (400 + 100 + 200), 0.005)
    save(d)
    close(j.sw, d)
    d = new_part(j.sw, OUT / 'loft3.SLDPRT')
    secs = []
    for z in (0.0, 15.0, 30.0):
        with Sk(d, plane(d, 'Z', z, f'C{z:.0f}_P'), f'C{z:.0f}') as s:
            s.spline([(10 * math.cos(math.radians(t)), 10 * math.sin(math.radians(t)), z) for t in range(0, 360, 30)])
        secs.append(s.feat)
    loft(d, secs, 'TUBE')
    expect('three-section spline loft volume', volume(d), math.pi * 100 * 30, 0.01)
    save(d)
    close(j.sw, d)

    # one-sided extrudes with want, an arc, a second body brought in and deleted again
    d = new_part(j.sw, OUT / 'upper.SLDPRT')
    with Sk(d, plane(d, 'Z', 15.0, 'UPPER_P'), 'UPPER') as s:
        s.rect((0, 0, 15.0), (20, 20, 15.0))
    extrude(d, s.feat, 'UPPER', 10.0, mode=MID, expect_dv=4000)
    save(d)
    close(j.sw, d)
    d = new_part(j.sw, OUT / 'lower.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'LOWER_P'), 'LOWER') as s:
        s.rect((0, 0, 5.0), (20, 20, 5.0))
    extrude(d, s.feat, 'LOWER', 10.0, mode=MID, expect_dv=4000)
    with Sk(d, plane(d, 'Z', 10.0, 'TOP_P'), 'PIN') as s:
        s.circle((5, 5, 10.0), 3.0)
    extrude(d, s.feat, 'PIN', 5.0, mode=BLIND, want=(2, +1, 10.0), expect_dv=math.pi * 9 * 5)
    expect('pin goes up', bbox(d)[5], 15.0, 0.01)
    with Sk(d, plane(d, 'Z', 10.0, 'TOP_P2'), 'POCKET') as s:
        s.circle((15, 15, 10.0), 2.0)
    extrude(d, s.feat, 'POCKET', 4.0, cut=True, mode=BLIND, want=(2, -1, 10.0), expect_dv=math.pi * 4 * 4)
    with Sk(d, plane(d, 'Z', 5.0, 'D_P'), 'DSHAPE') as s:
        s.arc((30, 10, 5.0), (35, 10, 5.0), (25, 10, 5.0), +1)
        s.poly([(25, 10, 5.0), (35, 10, 5.0)], closed=False)
    extrude(d, s.feat, 'DSHAPE', 10.0, mode=MID, expect_dv=math.pi * 25 / 2 * 10)
    expect('bodies before insert', len(bodies(d)), 2, 0)
    save(d)
    list_faces(d, limit=6)
    v0 = volume(d)
    insert_body(d, OUT / 'ring.SLDPRT')          # sits at z 0 to 4 round the origin: overlaps the block's corner
    insert_body(d, OUT / 'upper.SLDPRT')         # sits on top of the block, cut by nothing
    expect('bodies after two inserts', len(bodies(d)), 4, 0)
    expect('volume with the inserted bodies', volume(d), v0 + 4000 + math.pi * 125 * 4, 0.001)
    name = [b[0] for b in bodies(d) if abs(b[1] - 4000) < 1 and b[2][2] > 9.9][0]
    delete_body(d, name)
    expect('bodies after delete', len(bodies(d)), 3, 0)
    expect('volume after delete', volume(d), v0 + math.pi * 125 * 4, 0.001)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    save(d)
    close(j.sw, d)

    # STEP in: the plate that model() exported
    if not (OUT / 'plate.step').exists():
        model(j)
    d, target = import_step(j.sw, OUT / 'plate.step', OUT / 'plate_in')
    expect('imported bodies', len(bodies(d)), 1, 0)
    expect('imported volume', volume(d), 60 * 30 * 10 - math.pi * 160 - (4 - math.pi) * 90, 0.001)
    b = bbox(d)
    for k, want in enumerate((0, 0, 0, 60, 30, 10)):
        expect(f'imported box[{k}]', b[k], want, 0.01)
    expect('imported hole faces', len(pick(d, kind='cyl', r=4.0)), 1, 0)
    close(j.sw, d)


TESTS = {'model': model, 'beam': beam, 'rod': rod, 'extras': extras, 'loads': loads}

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or list(TESTS)
    with job() as j:
        for name in todo:
            log('----', name)
            TESTS[name](j)
    print('PASS', ' '.join(todo), flush=True)
