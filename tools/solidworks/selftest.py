"""Prove swkit and swfea against hand answers on this machine's SolidWorks. Also the worked example for the playbook.

    python tools/solidworks/selftest.py [model] [beam] [rod] [extras] [loads] [contact] [bearing] [blend] [verdict] [picks]

All of them when none is named.

Writes to cad/_wip/sw-selftest/ (gitignored) and prints PASS or the first check that failed. Run it on a machine or a
SolidWorks version the helpers have not been used on, and after changing swkit.py or swfea.py. About two minutes, once
SolidWorks has started (a launch waits while another session's instance is solving).

  model:   a 60 x 30 x 10 plate with a through hole and four rounded corners; volume, box and both exports are checked.
  beam:    a 100 x 10 x 10 cantilever with 10 N at the tip through a remote load, against F L^3 / 3 E I.
  rod:     a 20 mm round bar, 50 long, with 100 N pressed on its end through a normal force, against F L / A E.
  extras:  chamfer, half-space cut, shell, revolve, two lofts, one-sided extrudes, an arc, a body brought in and deleted,
           a broken feature that feature_errors must name, and a STEP import, each against a hand volume or count.
  blend:   skirt(): a lofted oval stem rounded into the disc it stands on; volume against a true round, and the STL
           sampled either side of the round's surface.
  loads:   what the load and result calls mean: a normal load over two faces is the total, a remote moment is in N.m,
           a remote force acts where it is placed, which stress column is which shear, and the solver macro.
  contact: two stacked blocks with no-penetration contact between them and a soft pad to hold the upper one.
  bearing: a bearing load on a bore, against the reaction, the peak pressure and the pressure summed over the bore.
  verdict: judge() on series worked by hand (settled, moving, a growing step, the floor on small changes), expect()
           and its tolerances, stamp()'s clock file, a materials key that
           matches no body of a two-body study, and save_as before an edit leaving the original file as it was.
  picks:   side(), edges_of() and edges_along() on a plate, the measured part kept after each feature, what a refused
           round and a refused sketch say, the job's runs.log, and sheet.py's printability() and mesh_diff().
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from swfea import NO_PENETRATION, PETG, SOLVER_DIRECT, static  # noqa: E402
from swkit import Failed  # noqa: E402
from swkit import (BLIND, MID, NUL, Sk, bbox, bodies, call, chamfer, close, cut_half_space, delete_body, edges_where,  # noqa: E402
                   expect, export, extrude, feature_errors, fillet, import_step, insert_body, job, list_faces, loft, log,
                   new_part, open_doc, pick, plane, redraw_circles, revolve, save, set_dim, shell, single_body, volume)

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

    # feature_errors must see a broken feature: move a cut's circle off the body and rebuild
    d = new_part(j.sw, OUT / 'broken.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((0, 0, 5.0), (20, 20, 5.0))
    extrude(d, s.feat, 'BLOCK', 10.0, mode=MID, expect_dv=4000)
    with Sk(d, plane(d, 'Z', 5.0, 'BORE_P'), 'BORE') as s:
        s.circle((10, 10, 5.0), 3.0)
    extrude(d, s.feat, 'BORE', 10.0, cut=True, mode=MID, expect_dv=math.pi * 9 * 10)
    expect('rebuild errors before the break', len(feature_errors(d)), 0, 0)
    d.ClearSelection2(True)
    d.FeatureByName('BORE_SK').Select2(False, 0)
    d.EditSketch()
    for seg in call(d.GetActiveSketch2, 'GetSketchSegments'):
        seg.Select4(True, NUL)
    d.EditDelete()
    d.SketchManager.CreateCircleByRadius(0.2, 0.2, 0, 0.003)      # 200 mm away, in sketch metres
    d.InsertSketch2(True)
    d.ForceRebuild3(False)
    errs = feature_errors(d)
    log('broken tree reports', errs)
    if [e[0] for e in errs] != ['BORE']:
        raise SystemExit(f'FAIL: feature_errors should name the broken cut BORE, got {errs}')
    expect('volume with the cut broken', volume(d), 4000, 0.001)
    close(j.sw, d)

    # changing a saved part: open it again, change a dimension and a sketch in place, no rebuild from the script
    d = new_part(j.sw, OUT / 'edit.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((0, 0, 5.0), (20, 20, 5.0))
    extrude(d, s.feat, 'BLOCK', 10.0, mode=MID, expect_dv=4000)
    with Sk(d, plane(d, 'Z', 5.0, 'BORE_P'), 'BORE') as s:
        s.circle((10, 10, 5.0), 3.0)
    extrude(d, s.feat, 'BORE', 10.0, cut=True, mode=MID, expect_dv=math.pi * 9 * 10)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'edit.SLDPRT')
    set_dim(d, 'BLOCK', 10.0, 12.0)
    d.ForceRebuild3(False)
    expect('volume after set_dim', volume(d), 4800 - math.pi * 9 * 10, 0.001)
    redraw_circles(d, 'BORE_SK', [(6, 6, 5.0), (14, 14, 5.0)], 2.0)
    d.ForceRebuild3(False)
    expect('rebuild errors after the edit', len(feature_errors(d)), 0, 0)
    expect('volume after redraw_circles', volume(d), 4800 - 2 * math.pi * 4 * 10, 0.001)
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
    # a full cylinder comes back from STEP as two half faces: picks on imported parts find two where a native part has one
    expect('imported hole faces (two halves)', len(pick(d, kind='cyl', r=4.0)), 2, 0)
    close(j.sw, d)


def blend(j):
    """skirt(): a 60 mm disc, 6 thick, with an oval stem lofted up from it (20 x 12 at the foot, 14 x 18 and squarer at
    the top), rounded into the disc with a 4 mm skirt. Volume against the hand value of a 4 mm round along the foot's
    outline, and the STL sampled either side of where the round's surface should be."""
    from sheet import inside, read_stl
    from swkit import offset_loop, skirt

    def outline(z, k=24):
        t = (z + 1.0) / 61.0                                   # foot at z -1 (inside the disc), top at z 60
        a, b, n = 10.0 - 3.0 * t, 6.0 + 3.0 * t, 2.0 + t
        pts = []
        for i in range(k):
            c, s = math.cos(2 * math.pi * i / k), math.sin(2 * math.pi * i / k)
            pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s), z))
        return pts

    sq = offset_loop([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)], 1.0)
    expect('offset_loop moves a square corner out along its diagonal', sq[0][0], -math.sqrt(0.5), 0.001)
    d = new_part(j.sw, OUT / 'stem.SLDPRT')
    with Sk(d, plane(d, 'Z', -3.0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, -3.0), 30.0)
    extrude(d, s.feat, 'DISC', 6.0, mode=MID, expect_dv=math.pi * 900 * 6)
    secs = []
    for k, z in enumerate((-1.0, 15.0, 35.0, 60.0)):
        with Sk(d, plane(d, 'Z', z, f'STEM_P{k}'), f'STEM_S{k}') as s:
            s.spline(outline(z))
        secs.append(s.feat)
    loft(d, secs, 'STEM')
    save(d)
    v0 = volume(d)
    R = 4.0
    skirt(d, outline, 'Z', 0.0, R, 'FOOT')
    foot = np.array(outline(0.0))
    per = float(np.linalg.norm(foot - np.roll(foot, 1, axis=0), axis=1).sum())
    # a round of radius R along an outline of length P: section (1 - pi/4) R^2, its centroid 0.2234 R off the wall
    hand = (1 - math.pi / 4) * R ** 2 * (per + 2 * math.pi * 0.2234 * R)
    expect('skirt volume against a true round mm3', volume(d) - v0, hand, 0.10)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    save(d)
    export(j.sw, d, OUT / 'stem.stl')
    close(j.sw, d)
    # half way round the quarter circle the surface stands R (1 - sin 45) = 1.17 off the stem at height 1.17. A point
    # 0.35 inside that is solid, one 0.35 outside is air; a 45 degree chamfer of the same size would fill both.
    h = R * (1 - math.cos(math.pi / 4))
    edge_x, edge_y = outline(h)[0][0] + h, outline(h)[6][1] + h
    low = R * (1 - math.cos(math.pi / 8))                      # a quarter of the way round: 0.30 up, 2.47 off the stem
    low_x = outline(low)[0][0] + R * (1 - math.sin(math.pi / 8))
    pts = [(edge_x - 0.35, 0, h), (edge_x + 0.35, 0, h), (0, edge_y - 0.35, h), (0, edge_y + 0.35, h),
           (low_x - 0.3, 0, low), (low_x + 0.3, 0, low)]
    got = inside(read_stl(OUT / 'stem.stl'), np.array(pts))
    if list(got) != [True, False, True, False, True, False]:
        raise SystemExit(f'FAIL: the skirt is not where a 4 mm round would be: inside = {list(got)} at {pts}')
    log('ok skirt surface: solid just inside the quarter circle and air just outside it, on both axes and at the face')


def contact(j):
    """Two 20 x 20 x 10 PETG blocks stacked, the lower fixed underneath, no-penetration contact between them, and a
    small soft pad bonded to the side of both so the upper block is held when the contact is open."""
    pad = dict(name='Soft pad', EX=0.5e6, NUXY=0.45, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
    for name, lo, hi in (('stack_upper', (0, 0, 10), (20, 20, 20)), ('stack_pad', (20, 8, 6), (22, 12, 14)),
                         ('stack', (0, 0, 0), (20, 20, 10))):
        d = new_part(j.sw, OUT / f'{name}.SLDPRT')
        zc = (lo[2] + hi[2]) / 2
        with Sk(d, plane(d, 'Z', zc, name.upper() + '_P'), name.upper()) as s:
            s.rect((lo[0], lo[1], zc), (hi[0], hi[1], zc))
        extrude(d, s.feat, name.upper(), hi[2] - lo[2], mode=MID, expect_dv=(hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]))
        if name == 'stack':
            insert_body(d, OUT / 'stack_upper.SLDPRT')
            insert_body(d, OUT / 'stack_pad.SLDPRT')
            expect('bodies in the stack', len(bodies(d)), 3, 0)
        save(d)
        close(j.sw, d)
    d = open_doc(j.sw, OUT / 'stack.SLDPRT')
    bottom, top = pick(d, kind='plane', at=(10, 10, 0)), pick(d, kind='plane', at=(10, 10, 20))
    lower_top = pick(d, kind='plane', normal=(0, 0, 1), at=(10, 10, 10))
    upper_bottom = pick(d, kind='plane', normal=(0, 0, -1), at=(10, 10, 10))
    for what, fs in (('bottom', bottom), ('top', top), ('lower top', lower_top), ('upper bottom', upper_bottom)):
        expect(what + ' faces', len(fs), 1, 0)
    common = dict(fixtures=[('fixed', bottom)], el=2.5, contacts=[(NO_PENETRATION, lower_top, upper_bottom)],
                  materials={'stack_pad': pad}, solver=SOLVER_DIRECT)

    def top_uz(r):
        return float(r.disp[np.abs(r.pos[:, 2] - 20) < 0.01, 3].mean())

    # pressed together, the contact carries everything: both blocks shorten as one 20 mm column, the pad carries nothing
    r = static(j, d, 'STACK_PRESS', PETG, loads=[('normal', top, 100.0)], **common)
    log(r.summary())
    expect('pressed: reaction Fz N', r.reaction[2], 100.0, 0.01)
    expect('pressed: top face moves down, F L / A E mm', top_uz(r), -100 * 0.02 / (4e-4 * PETG['EX']) * 1e3, 0.08)
    low = (np.abs(r.pos[:, 2] - 5) < 2.5) & (r.pos[:, 0] < 20)
    expect('pressed: sz in the lower block MPa', float(r.s[low, 3].mean()), -100 / 400, 0.04)
    in_pad = r.pos[:, 0] > 20.01
    expect('pressed: pad stress MPa (it is the soft material, and unloaded)', float(r.vm[in_pad].max()), 0.0, 0.001)
    # pulled apart, the contact carries nothing and only the soft pad holds the block. Bonded faces would move
    # 2.6e-8 mm under this 0.001 N; on the pad alone the block moved about 0.1 mm (125 mm under 1 N, 2026-11-12).
    r = static(j, d, 'STACK_LIFT', PETG, loads=[('normal', top, -0.001)], loose_ok=True, **common)
    log(r.summary())
    expect('lifted: reaction Fz N', r.reaction[2], -0.001, 0.02)
    if not top_uz(r) > 0.01:
        raise SystemExit(f'FAIL: lifted block moved {top_uz(r)} mm: the faces are still bonded, the contact set did nothing')
    log(f'ok lifted: the block comes away {top_uz(r):.4f} mm on the pad alone (bonded would be 2.6e-8)')
    close(j.sw, d)


def bearing(j):
    """A 60 x 60 x 10 plate with a 20 mm bore, held on one edge face, 100 N on the bore as a bearing load; then a bore
    along X with a force across two model axes. Hand values: reaction = load, nothing on the half of the bore the
    force pulls away from, peak pressure 4 F / (pi d t), and the pressure summed over the bore (measured 2026-11-14)."""
    d = new_part(j.sw, OUT / 'lug.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'LUG_P'), 'LUG') as s:
        s.rect((-30, -30, 5.0), (30, 30, 5.0))
    extrude(d, s.feat, 'LUG', 10.0, mode=MID, expect_dv=36000)
    with Sk(d, plane(d, 'Z', 5.0, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 5.0), 10.0)
    extrude(d, s.feat, 'BORE', 10.0, cut=True, mode=MID, expect_dv=math.pi * 100 * 10)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'lug.SLDPRT')
    d.ForceRebuild3(False)
    bore, root = pick(d, kind='cyl', r=10.0), pick(d, kind='plane', normal=(-1, 0, 0))
    expect('bore faces', len(bore), 1, 0)
    expect('root faces', len(root), 1, 0)
    n_feat = d.GetFeatureCount
    p0 = 4 * 100 / (math.pi * 20 * 10)
    for name, f in (('BRG_X', (100.0, 0, 0)), ('BRG_45', (-70.7107, 70.7107, 0))):
        r = static(j, d, name, PETG, fixtures=[('fixed', root)], loads=[('bearing', bore, f)], el=2.0, ctrl=[(bore, 0.6)])
        log(r.summary())
        for k in range(3):
            expect(f'{name}: reaction {"xyz"[k]} N', r.reaction[k], -f[k], 0.01 if f[k] else 0.05)
        expect(f'{name}: reaction resultant N', r.reaction[3], r.applied, 0.01)
        # radial and along-the-force traction on the bore wall, mid-thickness (clear of the two rims)
        on = (np.abs(np.hypot(r.pos[:, 0], r.pos[:, 1]) - 10) < 0.02) & (np.abs(r.pos[:, 2] - 5) < 3.5)
        n = r.pos[on, :2] / 10
        S = r.s[on]
        tx, ty = S[:, 1] * n[:, 0] + S[:, 4] * n[:, 1], S[:, 4] * n[:, 0] + S[:, 2] * n[:, 1]      # traction the wall feels
        srr = tx * n[:, 0] + ty * n[:, 1]
        u = np.array(f[:2]) / 100
        th = np.degrees(np.arccos(np.clip(n @ u, -1, 1)))          # angle from the force direction
        expect(f'{name}: peak pressure where the force points, 4F/(pi d t) MPa', float(-srr[th < 2].mean()), p0, 0.03)
        expect(f'{name}: pressure on the half the force leaves MPa', float(np.abs(srr[th > 95]).max()), 0.0, 0.02 * p0)
        # the load is a traction ALONG THE FORCE of p0 cos^2 per wall area (p0 cos per projected area), not a normal
        # pressure of p0 cos: so the pressure alone sums to 3/4 of the force, and wall shear carries the rest
        bins = np.arange(0, 91, 3)
        press = sum(-srr[(th >= a) & (th < a + 3)].mean() * math.cos(math.radians(a + 1.5)) for a in bins[:-1])
        along = sum(-(tx * u[0] + ty * u[1])[(th >= a) & (th < a + 3)].mean() for a in bins[:-1])
        area = 2 * 10 * math.radians(3) * 10                       # both sides of the force line, 3 degrees, 10 thick
        expect(f'{name}: pressure summed over the bore N (3/4 of the load)', float(press * area), 75.0, 0.03)
        expect(f'{name}: traction along the force summed over the bore N', float(along * area), 100.0, 0.03)
        expect(f'{name}: pressure at 45 degrees MPa (cos^3, not cos)', float(-srr[np.abs(th - 45) < 2].mean()),
               p0 * math.cos(math.radians(45)) ** 3, 0.05)
    expect('features after the studies (the coordinate systems are gone)', d.GetFeatureCount, n_feat, 0)
    try:
        static(j, d, 'BRG_AXIAL', PETG, fixtures=[('fixed', root)], loads=[('bearing', bore, (100.0, 0, 10.0))], el=3.0)
    except Failed as ex:
        log('ok a force with a part along the bore axis is refused:', str(ex)[:90])
    else:
        raise SystemExit('FAIL: a bearing load with an axial part was accepted')
    close(j.sw, d)

    # a bore along X and a force across Y and Z: the coordinate system needs a general rotation
    d = new_part(j.sw, OUT / 'lug_x.SLDPRT')
    with Sk(d, plane(d, 'X', 5.0, 'LUGX_P'), 'LUGX') as s:
        s.rect((5.0, -30, -30), (5.0, 30, 30))
    extrude(d, s.feat, 'LUGX', 10.0, mode=MID, expect_dv=36000)
    with Sk(d, plane(d, 'X', 5.0, 'BOREX_P'), 'BOREX') as s:
        s.circle((5.0, 0, 0), 10.0)
    extrude(d, s.feat, 'BOREX', 10.0, cut=True, mode=MID, expect_dv=math.pi * 100 * 10)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'lug_x.SLDPRT')
    d.ForceRebuild3(False)
    bore, root = pick(d, kind='cyl', r=10.0), pick(d, kind='plane', normal=(0, 0, -1))
    r = static(j, d, 'BRG_YZ', PETG, fixtures=[('fixed', root)], loads=[('bearing', bore, (0, 60.0, -80.0))], el=2.5,
               ctrl=[(bore, 1.0)])
    log(r.summary())
    expect('bore along X: reaction x N', r.reaction[0], 0.0, 0.5)
    expect('bore along X: reaction y N', r.reaction[1], -60.0, 0.01)
    expect('bore along X: reaction z N', r.reaction[2], 80.0, 0.01)
    on = np.abs(np.hypot(r.pos[:, 1], r.pos[:, 2]) - 10) < 0.02
    n = r.pos[on, 1:] / 10
    S = r.s[on]
    srr = n[:, 0] ** 2 * S[:, 2] + n[:, 1] ** 2 * S[:, 3] + 2 * n[:, 0] * n[:, 1] * S[:, 6]
    worst = n[np.argmin(srr)]
    expect('bore along X: the pressure peak faces the force, y', float(worst[0]), 0.6, 0.1)
    expect('bore along X: the pressure peak faces the force, z', float(worst[1]), -0.8, 0.1)
    close(j.sw, d)


def refused(what, fn, *needles):
    """fn() must raise Failed, with every needle in the message."""
    try:
        fn()
    except Failed as ex:
        missing = [n for n in needles if n not in str(ex)]
        if missing:
            raise SystemExit(f'FAIL: {what}: the refusal does not say {missing}: {ex}')
        log(f'ok {what} is refused:', str(ex) if '\n  try: ' in str(ex) else str(ex)[:110])
    else:
        raise SystemExit(f'FAIL: {what} was accepted')


def verdict(j):
    """judge(), expect() and stamp() against cases worked by hand; the materials refusal on a two-body study; and
    save_as: the open document becomes the new file and the one it came from is not touched."""
    import hashlib
    import json
    import re
    import time

    from swfea import judge
    from swkit import save_as, stamp

    def state(what, series, limits, want, lowest, entry=None, **kw):
        r = judge(series, limits, **kw)
        if r['verdict'] != want or (entry is not None and r['lowest_entry'] != entry):
            raise SystemExit(f'FAIL: judge, {what}: {r["verdict"]} at "{r["lowest_entry"]}", expected {want} at "{entry}"')
        expect(f'judge, {what}: {want}, lowest factor', r['lowest_factor'], lowest, 0, abs_tol=0.005)
        json.dumps(r)                                          # it goes into results.json as it is
        return r

    # limit 45 MPa, factor 2 needed, steps of up to 5 % count as settled
    state('three sizes within 5 %, factor 4.37', {'vm': [10.0, 10.2, 10.3]}, {'vm': 45.0}, 'pass', 4.37)
    state('settled at factor 1.83', {'vm': [24.0, 24.5, 24.6]}, {'vm': 45.0}, 'fail', 1.83)
    state('still moving and already at 1.8', {'vm': [18.0, 21.0, 25.0]}, {'vm': 45.0}, 'fail', 1.8)
    # moving by about the same share each time (13.3 %, then 12.7 %): two more such steps read 14.62 MPa, 3.08
    r = state('moving 13 % a step at factor 3.91', {'vm': [9.0, 10.2, 11.5]}, {'vm': 45.0}, 'margin, not converged', 3.91)
    expect('judge: the last step is measured against the value before it, %', r['rows'][0]['last_step_pct'], 12.7, 0)
    expect('judge: the step before it, %', r['rows'][0]['step_before_pct'], 13.3, 0)
    expect('judge: factor after two more steps', r['rows'][0]['factor_after_two_more_steps'], 3.08, 0, abs_tol=0.005)
    if r['rows'][0]['step_growing']:
        raise SystemExit('FAIL: judge: steps of 13.3 % then 12.7 % are not growing')
    # the ribbed bracket of 2026-11-14: von Mises up 3.6 % and then 13.1 % at a sharp rib toe. The step is growing, so
    # it is not a margin however the factor reads (3.6 now, 2.81 after two steps of the last size). With the toe
    # rounded it settled at 13.54 MPa and passed
    r = state('a growing step at factor 3.6', {'vm': [10.68, 11.06, 12.51]}, {'vm': 45.0}, 'not shown', 3.6)
    expect('judge: its last step, %', r['rows'][0]['last_step_pct'], 13.1, 0)
    expect('judge: its factor after two more steps is still given', r['rows'][0]['factor_after_two_more_steps'], 2.81, 0,
           abs_tol=0.005)
    if not r['rows'][0]['step_growing']:
        raise SystemExit('FAIL: judge: steps of 3.6 % then 13.1 % are growing and the row does not say so')
    # the split housing of 2026-11-14: the corner of a steel ring on the rim of its seat, 20.3 % then 28.4 %
    r = state('a contact edge at factor 4.17', {'shear': [2.02, 2.43, 3.12]}, {'shear': 13.0}, 'not shown', 4.17)
    if not r['rows'][0]['step_growing']:
        raise SystemExit('FAIL: judge: steps of 20.3 % then 28.4 % are growing and the row does not say so')
    state('level, then up 20 %', {'vm': [10.0, 10.0, 12.0]}, {'vm': 45.0}, 'not shown', 3.75)
    state('up 1 %, then down 21 %', {'vm': [10.0, 10.1, 8.0]}, {'vm': 45.0}, 'not shown', 5.62)
    # the floor: a last change of at most 5 % of limit / need counts as settled (0.5625 MPa of layer tension at need 2)
    r = state('a small stress moving 21 % of itself', {'layer': [0.89, 0.9, 0.71]}, {'layer': 22.5}, 'pass', 31.69)
    expect('judge: the floor in MPa', r['rows'][0]['settled_under_mpa'], 0.5625, 0, abs_tol=0.001)
    expect('judge: the last change in MPa', r['rows'][0]['last_change_mpa'], 0.19, 0, abs_tol=0.001)
    state('0.5 MPa up, under the floor', {'layer': [1.0, 1.2, 1.7]}, {'layer': 22.5}, 'pass', 13.24)
    state('0.6 MPa up, over the floor, step growing', {'layer': [1.0, 1.2, 1.8]}, {'layer': 22.5}, 'not shown', 12.5)
    state('the floor follows need: 0.6 MPa is under it at need 1.5', {'layer': [1.0, 1.2, 1.8]}, {'layer': 22.5}, 'pass',
          12.5, need=1.5)
    # shear between layers, same part printed the other way: 2.13 now, 1.78 after two more steps of 9.3 %
    r = state('moving 9 % at factor 2.13', {'shear': [4.86, 5.59, 6.11]}, {'shear': 12.99}, 'not shown', 2.13)
    expect('judge: its factor after two more steps', r['rows'][0]['factor_after_two_more_steps'], 1.78, 0, abs_tol=0.005)
    state('two sizes that agree', {'vm': [10.0, 10.1]}, {'vm': 45.0}, 'not shown', 4.46)
    state('one size', {'vm': [10.0]}, {'vm': 45.0}, 'not shown', 4.5)
    # falling at every step is taken at the finest value, growing steps or not; a series that has gone both ways is
    # not, even ending on a fall
    state('falling 20 % a step at factor 3.75', {'vm': [20.0, 15.0, 12.0]}, {'vm': 45.0}, 'margin, not converged', 3.75)
    state('falling 5 % and then 37 %', {'vm': [20.0, 19.0, 12.0]}, {'vm': 45.0}, 'margin, not converged', 3.75)
    r = state('up 30 % then down 15 % at factor 2.36', {'shear': [5.0, 6.5, 5.5]}, {'shear': 13.0}, 'not shown', 2.36)
    expect('judge: it is taken as coming back up', r['rows'][0]['factor_after_two_more_steps'], 1.78, 0, abs_tol=0.005)
    state('a wider tolerance settles it', {'vm': [10.68, 11.06, 12.51]}, {'vm': 45.0}, 'pass', 3.6, tol=0.15)
    state('a higher need fails it', {'vm': [10.0, 10.2, 10.3]}, {'vm': 45.0}, 'fail', 4.37, need=5.0)
    # two bodies, two load cases, three measures: the lowest factor is the lower half's shear in +X, not the first row,
    # the highest stress (the 6.13 MPa von Mises is 7.34) or the last row
    lim = dict(vm=45.0, layer=22.5, shear=13.0)
    series = {'upper, +Y, vm': [4.5, 4.55, 4.57], 'upper, +Y, layer': [0.85, 0.86, 0.87], 'upper, +Y, shear': [1.16, 1.17, 1.18],
              'upper, +X, vm': [6.0, 6.1, 6.13], 'upper, +X, layer': [0.75, 0.76, 0.76], 'upper, +X, shear': [1.4, 1.41, 1.41],
              'lower, +Y, vm': [2.6, 2.61, 2.62], 'lower, +Y, layer': [0.65, 0.66, 0.66], 'lower, +Y, shear': [0.6, 0.61, 0.61],
              'lower, +X, vm': [5.1, 5.12, 5.13], 'lower, +X, shear': [2.2, 2.22, 2.23], 'lower, +X, layer': [1.05, 1.06, 1.07]}
    limits = {k: lim[k.split(', ')[2]] for k in series}
    r = state('twelve entries over two bodies and two cases', series, limits, 'pass', 5.83, 'lower, +X, shear')
    expect('judge: a row for every entry', len(r['rows']), 12, 0)
    # one entry of the twelve decides the verdict, and the lowest factor is still reported from the right row
    series['upper, +Y, layer'] = [0.5, 0.7, 0.87]
    state('one of twelve moving 24 % but only 0.17 MPa', series, limits, 'pass', 5.83, 'lower, +X, shear')
    series['upper, +Y, vm'] = [3.0, 4.5, 6.2]
    state('one of twelve still moving, steps 50 % then 38 %', series, limits, 'margin, not converged', 5.83, 'lower, +X, shear')
    series['upper, +Y, vm'] = [3.0, 3.5, 5.0]
    r = state('one of twelve with a growing step', series, limits, 'not shown', 5.83, 'lower, +X, shear')
    expect('judge: one row of the twelve is marked as growing', sum(q['step_growing'] for q in r['rows']), 1, 0)
    series['upper, +Y, vm'] = [4.5, 4.55, 4.57]
    series['upper, +Y, layer'] = [0.87]
    state('one of twelve with one size', series, limits, 'not shown', 5.83, 'lower, +X, shear')
    series['lower, +Y, vm'] = [23.0, 23.1, 23.2]
    state('one of twelve under the factor', series, limits, 'fail', 1.94, 'lower, +Y, vm')
    r = judge({'pad': [0.0, 0.0, 0.0], 'vm': [10.0, 10.2, 10.3]}, {'pad': 1.0, 'vm': 45.0})
    if r['verdict'] != 'pass' or r['lowest_entry'] != 'vm' or r['rows'][0]['factor'] is not None or 'Infinity' in json.dumps(r):
        raise SystemExit(f'FAIL: judge with an unstressed entry: {r}')
    log('ok judge: an entry with no stress has no factor and does not hide the lowest')
    refused('judge with a limit for another entry', lambda: judge({'vm': [1.0]}, {'layer': 22.5}), 'layer', 'vm')
    refused('judge with a limit missing', lambda: judge({'vm': [1.0], 'layer': [1.0]}, {'vm': 45.0}), 'layer')
    refused('judge with nothing', lambda: judge({}, {}), 'same keys')
    refused('judge with a negative value', lambda: judge({'sz': [-3.0, -3.1, -3.1]}, {'sz': 45.0}), 'sz', 'negative')
    refused('judge with no values', lambda: judge({'vm': []}, {'vm': 45.0}), 'vm')

    # expect(): which tolerance applies
    expect('a zero that comes back as 6e-17, tol 0.01', 6e-17, 0.0, 0.01)
    expect('a target of 6e-17 counts as zero too', 0.004, 6e-17, 0.01)
    expect('relative: 1 % of 100', 100.9, 100.0, 0.01)
    expect('absolute: tol of 1 or more', 103.0, 100.0, 3)
    expect('absolute: tol 0 is exact', 4, 4, 0)
    expect('abs_tol is a floor under 5 % of 0.02', 0.028, 0.02, 0.05, abs_tol=0.01)
    expect('abs_tol does not narrow a wider relative tolerance', 104.0, 100.0, 0.05, abs_tol=0.01)
    refused('expect: 1.1 % off with 1 % allowed', lambda: expect('x', 101.1, 100.0, 0.01), 'allowed 1')
    refused('expect: 0.02 from zero with 0.01 allowed', lambda: expect('x', 0.02, 0.0, 0.01), 'allowed 0.01')
    refused('expect: outside the abs_tol floor', lambda: expect('x', 0.031, 0.02, 0.05, abs_tol=0.01), 'allowed 0.01')
    refused('expect: without the floor', lambda: expect('x', 0.028, 0.02, 0.05), 'allowed 0.001')
    refused('expect: not a number', lambda: expect('x', float('nan'), 1.0, 0.5), 'nan')

    # stamp(): a clock in a file. Its own folder, emptied first, so the clock starts here
    clock = OUT / 'clock'
    (clock / 'times.log').unlink(missing_ok=True)
    expect('stamp: the first call is minute 0', stamp(clock, 'start'), 0.0, 0)
    time.sleep(1.3)
    again = stamp(clock, 'a label\twith a tab\nand a line break')
    if not 1.3 / 60 <= again < 0.5:
        raise SystemExit(f'FAIL: stamp: 1.3 s later the clock reads {again} min')
    time.sleep(0.2)
    if not stamp(clock, 'end') > again:
        raise SystemExit('FAIL: stamp: the clock did not move on')
    lines = (clock / 'times.log').read_text(encoding='utf-8').splitlines()
    expect('stamp: one line per call', len(lines), 3, 0)
    for line, label in zip(lines, ('start', 'a label with a tab and a line break', 'end')):
        f = line.split('\t')
        if len(f) != 4 or f[3] != label or not re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}', f[1]) \
                or not re.fullmatch(r'\d+\.\d min', f[2]) or abs(float(f[0]) - time.time()) > 60:
            raise SystemExit(f'FAIL: stamp: line is not "seconds, local time, minutes, label" with tabs: {line!r}')
    expect('stamp: the minutes column is what it returned', float(lines[1].split('\t')[2].split()[0]), again, 0, abs_tol=0.05)
    log('ok stamp: three lines of seconds, local time with its offset, minutes and label')

    # the materials refusal names the bodies: two 10 mm cubes side by side, the second brought in from its own file
    d = new_part(j.sw, OUT / 'pair_b.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'PAIR_B_P'), 'PAIR_B') as s:
        s.rect((10, 0, 5.0), (20, 10, 5.0))
    extrude(d, s.feat, 'PAIR_B', 10.0, mode=MID, expect_dv=1000)
    save(d)
    close(j.sw, d)
    d = new_part(j.sw, OUT / 'pair.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'PAIR_A_P'), 'PAIR_A') as s:
        s.rect((0, 0, 5.0), (10, 10, 5.0))
    extrude(d, s.feat, 'PAIR_A', 10.0, mode=MID, expect_dv=1000)
    insert_body(d, OUT / 'pair_b.SLDPRT')
    expect('bodies in the pair', len(bodies(d)), 2, 0)
    save(d)
    close(j.sw, d)
    d = open_doc(j.sw, OUT / 'pair.SLDPRT')
    hard = dict(PETG, name='PETG with no Poisson ratio', NUXY=0.0)      # so that F L / A E is exact for a short block
    soft = dict(hard, name='Soft half', EX=0.19e9)
    study = dict(fixtures=[('fixed', pick(d, kind='plane', normal=(-1, 0, 0), at=(0, 5, 5)))],
                 loads=[('normal', pick(d, kind='plane', normal=(1, 0, 0), at=(20, 5, 5)), 100.0)], el=2.5)
    refused('a materials key that matches no body', lambda: static(j, d, 'PAIR', hard, materials={'pear': soft}, **study),
            "'pear'", 'The bodies are', 'PAIR_A', 'pair_b')
    refused('a body matched by two keys', lambda: static(j, d, 'PAIR', hard, materials={'pair_b': soft, 'PAIR_B': soft},
                                                         **study), 'more than one')
    # the refusal leaves no study behind: the same name works with the key put right. Two 10 mm lengths in series,
    # the second ten times softer: F L / A E for each
    r = static(j, d, 'PAIR', hard, materials={'pair_b': soft}, **study)
    log(r.summary())
    expect('pair: reaction Fx N', r.reaction[0], 100.0, 0.01)
    expect('pair: end face moves in, sum of both halves mm', float(r.disp[np.abs(r.pos[:, 0] - 20) < 0.01, 1].mean()),
           -100 * 0.01 / 1e-4 * (1 / hard['EX'] + 1 / soft['EX']) * 1e3, 0.02)
    close(j.sw, d)

    # save_as first, then edit (02-com.md): the open document is the new file, the old one is not written to
    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    old, new = OUT / 'keep.SLDPRT', OUT / 'keep_changed.SLDPRT'
    new.unlink(missing_ok=True)
    d = new_part(j.sw, old)
    with Sk(d, plane(d, 'Z', 5.0, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((0, 0, 5.0), (20, 20, 5.0))
    extrude(d, s.feat, 'BLOCK', 10.0, mode=MID, expect_dv=4000)
    save(d)
    close(j.sw, d)
    before, stat = sha(old), old.stat()
    d = open_doc(j.sw, old)
    save_as(d, new)
    if Path(d.GetPathName).name.lower() != new.name.lower():
        raise SystemExit(f'FAIL: after save_as the open document is {d.GetPathName}, not {new}')
    log('ok after save_as the open document is', Path(d.GetPathName).name)
    set_dim(d, 'BLOCK', 10.0, 12.0)
    save(d)
    expect('the new file has the change mm3', volume(d), 4800, 0.001)
    close(j.sw, d)
    if sha(old) != before or (old.stat().st_mtime, old.stat().st_size) != (stat.st_mtime, stat.st_size):
        raise SystemExit('FAIL: the original file changed on disk after save_as, edit, save')
    log('ok the original file is byte for byte what it was (sha256, size, time)')
    for path, want in ((old, 4000), (new, 4800)):
        d = open_doc(j.sw, path)
        d.ForceRebuild3(False)
        expect(f'{path.name} opened again: volume mm3', volume(d), want, 0.001)
        close(j.sw, d)


TESTS = {'model': model, 'beam': beam, 'rod': rod, 'extras': extras, 'loads': loads, 'contact': contact, 'bearing': bearing}

def picks(j):
    """side(), edges_of(), edges_along(), edge_info(), the state line after a feature, what a refused fillet says,
    Failed's try and stop lines, the job's runs.log, and sheet.py's printability() and mesh_diff()."""
    import swkit
    from sheet import mesh_diff, printability, read_stl
    from swkit import edge_info, edges_along, edges_of, side, state
    d = new_part(j.sw, OUT / 'picks.SLDPRT')
    with Sk(d, plane(d, 'Z', 5.0, 'PK_P'), 'PK') as s:
        s.rect((0, 0, 5.0), (60, 30, 5.0))
    extrude(d, s.feat, 'PK', 10.0, mode=MID, expect_dv=18000)
    expect('state after the block: volume', swkit.last['volume_mm3'], 18000, 0.001)
    if swkit.last['feature'] != 'PK' or swkit.last['bodies'] != 1 or swkit.last['errors']:
        raise SystemExit(f'FAIL: swkit.last after the block is {swkit.last}')
    for k, want in enumerate((0, 0, 0, 60, 30, 10)):
        expect(f'state box[{k}]', swkit.last['box'][k], want, 0.01, abs_tol=0.01)
    for where, area in (('+z', 1800), ('-z', 1800), ('+x', 300), ('-x', 300), ('+y', 600), ('-y', 600)):
        fs = side(d, where)
        expect(f'side {where}: faces', len(fs), 1, 0)
        expect(f'side {where}: area', call(fs[0], 'GetArea') * 1e6, area, 0.001)
    top = side(d, '+z')[0]
    expect('side +z lies at z 10', [v * 1e3 for v in call(top, 'GetBox')][2], 10.0, 0.01, abs_tol=0.01)
    rim = edges_of(side(d, '+z'))
    expect('edges of the top face', len(rim), 4, 0)
    expect('their total length', sum(edge_info(e)['length'] for e in rim), 180.0, 0.001)
    expect('edges of top and front together (one shared)', len(edges_of(side(d, '+z') + side(d, '-y'))), 7, 0)
    expect('edges along Z', len(edges_along(d, 'Z')), 4, 0)
    expect('edges along X', len(edges_along(d, 'X')), 4, 0)
    expect('edges along Z in the left half', len(edges_along(d, 'Z', inside=[-1, -1, -1, 30, 31, 11])), 2, 0)
    i = edge_info(edges_along(d, 'Z')[0])
    expect('a Z edge: length', i['length'], 10.0, 0.001)
    if not i['straight']:
        raise SystemExit('FAIL: a straight edge is not reported straight')
    refused('side with a bad word', lambda: side(d, 'top'), '+x -x')
    # a round larger than the 10 mm edges it is asked for is refused: fillet returns None and says why
    said, keep = [], swkit.log
    swkit.log = lambda *a: (said.append(' '.join(str(v) for v in a)), keep(*a))[1]
    try:
        if fillet(d, edges_along(d, 'Z'), (40.0,), 'TOO_BIG') is not None:
            raise SystemExit('FAIL: an R40 round on a 30 mm wide plate built')
    finally:
        swkit.log = keep
    if not any('4 of them are shorter than the smallest radius tried' in s for s in said):
        raise SystemExit(f'FAIL: the refused round does not say its edges are shorter than the radius: {said}')
    expect('nothing changed after the refused round', volume(d), 18000, 0.001)
    r = fillet(d, edges_along(d, 'Z'), (40.0, 3.0), 'CORNERS')
    expect('the second radius builds', r, 3.0, 0)
    expect('state after the round: volume', swkit.last['volume_mm3'], 18000 - (4 - math.pi) * 9 * 10, 0.001)
    expect('side +z after the round is still one face', len(side(d, '+z')), 1, 0)
    with Sk(d, plane(d, 'Z', 5.0, 'PKH_P'), 'PKH') as s:
        s.circle((30, 15, 5.0), 5.0)
    extrude(d, s.feat, 'PKH', 10.0, cut=True, mode=MID, expect_dv=math.pi * 25 * 10)
    hole_rim = [e for e in edges_of(side(d, '+z')) if not edge_info(e)['straight'] and edge_info(e)['length'] > 25]
    expect('the hole rim on the top face', len(hole_rim), 1, 0)
    expect('its length (16 chords read 0.6 % short)', edge_info(hole_rim[0])['length'], 2 * math.pi * 5, 0.01)
    st = state(d)
    expect('state(): volume', st['volume_mm3'], volume(d), 0.0001)
    # an open sketch is refused, and the refusal says what to try and when to stop
    with Sk(d, plane(d, 'Z', 5.0, 'OPEN_P'), 'OPEN') as s:
        s.poly([(5, 5, 5.0), (10, 5, 5.0), (10, 10, 5.0)], closed=False)
    refused('an open sketch as a cut', lambda: extrude(d, s.feat, 'OPEN', 10.0, cut=True, mode=MID),
            'try:', 'stop when:', 'closed loop')
    save(d)
    export(j.sw, d, OUT / 'picks.stl')
    close(j.sw, d)
    tris = read_stl(OUT / 'picks.stl')
    pr = printability(tris, '+z')
    want_v = 18000 - (4 - math.pi) * 90 - math.pi * 250
    expect('printability: volume', pr['volume_mm3'], want_v, 0.005)
    expect('printability: area on the bed', pr['bed_contact_mm2'], 1800 - (4 - math.pi) * 9 - math.pi * 25, 0.01)
    expect('printability: overhang lying flat', pr['overhang_mm2'], 0.0, 0.5)
    if not pr['ok'] or pr['shells'] != 1 or pr['open_edges'] != 0 or pr['height_mm'] != 10.0:
        raise SystemExit(f'FAIL: printability of the plate lying flat: {pr}')
    if printability(tris, '+z', bed=50)['ok'] or printability(tris, '+z', bed=50)['fits_bed']:
        raise SystemExit('FAIL: a 60 mm plate fits a 50 mm bed')
    up = printability(tris, '+x')                      # standing on its end: the upper half of the bore overhangs
    if not up['ok'] or not 20 < up['overhang_mm2'] < 200:      # a quarter of the bore and two corner rounds
        raise SystemExit(f'FAIL: printability standing on end: {up}')
    same = mesh_diff(tris, tris)
    if same['volume_diff_pct'] != 0 or same['box_diff_mm'] != 0 or same['a_to_b']['max_mm'] > 3 * same['resolution_mm']:
        raise SystemExit(f'FAIL: a mesh against itself: {same}')
    other = mesh_diff(tris, read_stl(OUT / 'plate.stl')) if (OUT / 'plate.stl').exists() else None
    if other is not None:                              # plate.stl has its hole at x 15, this one at x 30
        if not (other['box_diff_mm'] < 0.01 and abs(other['volume_diff_pct']) > 1 and other['a_to_b']['max_mm'] > 3):
            raise SystemExit(f'FAIL: mesh_diff against the plate with its hole elsewhere: {other}')
        log('ok mesh_diff finds the moved hole:', other['a_to_b'])


TESTS['picks'] = picks      # side(), edges_of(), edges_along(), the state line, refusals, printability(), mesh_diff()
TESTS['blend'] = blend      # skirt(): a lofted stem rounded into the face it stands on
TESTS['verdict'] = verdict  # judge(), expect(), stamp(), the materials refusal, save_as before an edit

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or list(TESTS)
    with job() as j:
        for name in todo:
            log('----', name)
            TESTS[name](j)
    # the job wrote its own line as it closed: one line per job, so that pc/run_metrics.py counts jobs and not lines
    runs = Path(sys.argv[0]).resolve().parent / 'runs.log'
    last = runs.read_text(encoding='utf-8').splitlines()[-1].split('\t')
    if len(last) < 5 or last[4] != 'ok' or last[2] != ' '.join(Path(a).name for a in sys.argv):
        raise SystemExit(f'FAIL: {runs} does not end with this job\'s "ok" line: {last}')
    print('PASS', ' '.join(todo), flush=True)
