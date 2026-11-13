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
from swfea import PETG, static  # noqa: E402
from swkit import (MID, Sk, bbox, close, edges_where, expect, export, extrude, feature_errors, fillet, job, log,  # noqa: E402
                   new_part, open_doc, pick, plane, save, single_body, volume)

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
    if r.reaction is not None:
        expect('reaction resultant N', abs(r.reaction[3]), 10.0, 0.02)
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
    expect('axial stress MPa', r.peak()[0], 100 / (math.pi * 100), 0.05)
    close(j.sw, d)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or ['model', 'beam', 'rod']
    with job() as j:
        for name in todo:
            log('----', name)
            {'model': model, 'beam': beam, 'rod': rod}[name](j)
    print('PASS', ' '.join(todo), flush=True)
