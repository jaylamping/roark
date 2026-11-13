"""T6: a steel pin, dia 10, free in a dia 10.2 hole through a PETG block; 250 N up on each pin end; block bottom fixed.

    python t6.py build | main0 | lift | main1        (one job each; results go to cad/_sim/sw-eval/T6_*.npz)

How the pin is held (05-fea.md, contact rule 2): the real 0.1 mm radial gap is modelled, and the pin is kept from floating
by two small soft pads (modulus 0.5 MPa), one outside each end of the hole, UNDER the pin (the side the pin moves away
from): each pad is bonded to the block's side face below the hole and to the underside of the pin. Under the pin and
outside the hole they touch nothing that carries the bearing load.
"""
import math
import sys

import numpy as np

from common import OUT, Clock, beat
import swfea
from swfea import BONDED, NO_PENETRATION, PETG, SOLVER_DIRECT, STEEL, static
from swkit import (MID, Sk, bodies, close, expect, extrude, face_info, insert_body, job, log, new_part, open_doc, pick, plane,
                   save)

swfea.MAX_NODES = 150_000
SIM = OUT.parent.parent.parent / '_sim' / 'sw-eval'
R_PIN, R_HOLE, AXIS_Z = 5.0, 5.1, 10.0
HALF_Y, PIN_HALF = 15.0, 25.0
PAD = dict(name='Soft pad', EX=0.5e6, NUXY=0.45, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
PAD_W, PAD_Z0, PAD_T = 1.5, 2.0, 2.0          # pad: X -1.5 to 1.5, Z 2 up to the pin, 2 mm thick outside each block side


def build(j):
    d = new_part(j.sw, OUT / 'pin.SLDPRT')
    with Sk(d, plane(d, 'Y', 0.0, 'PIN_P'), 'PIN') as s:
        s.circle((0, 0, AXIS_Z), R_PIN)
    extrude(d, s.feat, 'PIN', 2 * PIN_HALF, mode=MID, expect_dv=math.pi * R_PIN ** 2 * 2 * PIN_HALF)
    save(d)
    close(j.sw, d)
    # area under the pin between X +/-1.5 and Z 2: 2 * integral of (10 - sqrt(25 - x^2) - 2)
    a = PAD_W
    area = 2 * a * (AXIS_Z - PAD_Z0) - 2 * (a / 2 * math.sqrt(R_PIN ** 2 - a ** 2) + R_PIN ** 2 / 2 * math.asin(a / R_PIN))
    for name, yc in (('softpad_p', HALF_Y + PAD_T / 2), ('softpad_n', -HALF_Y - PAD_T / 2)):
        d = new_part(j.sw, OUT / f'{name}.SLDPRT')
        with Sk(d, plane(d, 'Y', yc, 'PAD_P'), 'PAD') as s:
            s.rect((-a, yc, PAD_Z0), (a, yc, 7.0))
        extrude(d, s.feat, 'PAD', PAD_T, mode=MID, expect_dv=2 * a * 5.0 * PAD_T)
        with Sk(d, plane(d, 'Y', yc, 'PAD_TRIM_P'), 'PAD_TRIM') as s:        # the pin's own cylinder trims the pad top
            s.circle((0, yc, AXIS_Z), R_PIN)
        extrude(d, s.feat, 'PAD_TRIM', PAD_T + 1.0, cut=True, mode=MID, expect_dv=2 * a * 5.0 * PAD_T - area * PAD_T)
        expect(name + ' volume', sum(b[1] for b in bodies(d)), area * PAD_T, 0.01)
        save(d)
        close(j.sw, d)
    d = new_part(j.sw, OUT / 'pinjoint.SLDPRT')
    with Sk(d, plane(d, 'Z', 10.0, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((-20, -HALF_Y, 10.0), (20, HALF_Y, 10.0))
    extrude(d, s.feat, 'BLOCK', 20.0, mode=MID, expect_dv=40 * 30 * 20)
    with Sk(d, plane(d, 'Y', 0.0, 'BLOCK_BORE_P'), 'BLOCK_BORE') as s:
        s.circle((0, 0, AXIS_Z), R_HOLE)
    extrude(d, s.feat, 'BLOCK_BORE', 2 * HALF_Y + 2.0, cut=True, mode=MID, expect_dv=math.pi * R_HOLE ** 2 * 2 * HALF_Y)
    save(d)
    for f in ('pin', 'softpad_p', 'softpad_n'):
        insert_body(d, OUT / f'{f}.SLDPRT')
    bs = bodies(d)
    for b in bs:
        log('body', b)
    expect('bodies', len(bs), 4, 0)
    expect('total volume', sum(b[1] for b in bs),
           40 * 30 * 20 - math.pi * R_HOLE ** 2 * 30 + math.pi * R_PIN ** 2 * 50 + 2 * area * PAD_T, 0.001)
    save(d)
    close(j.sw, d)


def faces(d):
    def box(f):
        return face_info(f)['box']
    f = {}
    f['bottom'] = pick(d, kind='plane', normal=(0, 0, -1), at=(10, 0, 0))
    f['hole'] = pick(d, kind='cyl', r=R_HOLE)
    r5 = pick(d, kind='cyl', r=R_PIN)
    f['pin'] = [x for x in r5 if box(x)[4] - box(x)[1] > 40]
    f['pad_top_p'] = [x for x in r5 if box(x)[1] > HALF_Y - 0.01 and box(x)[4] < HALF_Y + PAD_T + 0.01]
    f['pad_top_n'] = [x for x in r5 if box(x)[4] < -HALF_Y + 0.01 and box(x)[1] > -HALF_Y - PAD_T - 0.01]
    f['end_p'] = pick(d, kind='plane', normal=(0, 1, 0), at=(0, PIN_HALF, AXIS_Z))
    f['end_n'] = pick(d, kind='plane', normal=(0, -1, 0), at=(0, -PIN_HALF, AXIS_Z))
    f['side_p'] = pick(d, kind='plane', normal=(0, 1, 0), at=(15, HALF_Y, 10))
    f['side_n'] = pick(d, kind='plane', normal=(0, -1, 0), at=(15, -HALF_Y, 10))
    f['pad_face_p'] = pick(d, kind='plane', normal=(0, -1, 0), at=(0, HALF_Y, 3.0))
    f['pad_face_n'] = pick(d, kind='plane', normal=(0, 1, 0), at=(0, -HALF_Y, 3.0))
    for k, v in f.items():
        expect('faces ' + k, len(v), 1, 0)
    return f


def solve(j, name, total_n, hole_local, loose_ok=False, pin_local=None):
    j.simulation()                       # before opening and picking: see t3b.py and REPORT.md, "Playbook problems"
    d = open_doc(j.sw, OUT / 'pinjoint.SLDPRT')
    d.ForceRebuild3(False)
    f = faces(d)
    half = total_n / 2
    r = static(j, d, name, PETG, fixtures=[('fixed', f['bottom'])],
               loads=[('remote', f['end_p'], (0, PIN_HALF, AXIS_Z), (0, 0, half), (0, 0, 0)),
                      ('remote', f['end_n'], (0, -PIN_HALF, AXIS_Z), (0, 0, half), (0, 0, 0))],
               el=3.0, ctrl=[(f['hole'], hole_local), (f['pin'], pin_local or hole_local * 1.25),
                             (f['pad_top_p'] + f['pad_top_n'] + f['pad_face_p'] + f['pad_face_n'], 0.6)],
               contacts=[(NO_PENETRATION, f['hole'], f['pin']),
                         (BONDED, f['pad_top_p'], f['pin']), (BONDED, f['pad_top_n'], f['pin']),
                         (BONDED, f['pad_face_p'], f['side_p']), (BONDED, f['pad_face_n'], f['side_n'])],
               materials={'pin': STEEL, 'softpad': PAD}, solver=SOLVER_DIRECT, loose_ok=loose_ok)
    close(j.sw, d)
    log(name, 'nodes', r.nodes, 'reaction', r.reaction, 'applied', r.applied, 'max disp', r.max_disp(), 'solve s', round(r.seconds),
        'excessive', r.excessive)
    log(name, 'fixed nodes', None if r.fixed_pts is None else (r.fixed_pts.min(axis=0).round(2), r.fixed_pts.max(axis=0).round(2)),
        'loaded nodes', None if r.loaded_pts is None else (r.loaded_pts.min(axis=0).round(2), r.loaded_pts.max(axis=0).round(2)))
    np.savez_compressed(SIM / f'{name}.npz', pos=r.pos, s=r.s, disp=r.disp, reaction=np.array(r.reaction, float), nodes=r.nodes,
                        total_n=total_n, hole_local=hole_local, seconds=r.seconds)
    return r


if __name__ == '__main__':
    what = sys.argv[1]
    SIM.mkdir(parents=True, exist_ok=True)
    ck = Clock()
    with job() as j:
        beat('T6 ' + what, j.inst.pid)
        if what == 'build':
            build(j)
        elif what == 'main0':
            solve(j, 'T6_MAIN0', 500.0, 0.8)
        elif what == 'lift':
            solve(j, 'T6_LIFT', 0.02, 0.8, loose_ok=True)
        elif what == 'main1':
            # 0.5 on the hole with 0.625 on the pin meshed 227,182 nodes and was stopped by the 150,000 ceiling before
            # solving; the pin (steel, 110 times stiffer) keeps its 1.0 mm and only the hole wall is refined
            solve(j, 'T6_MAIN1', 500.0, 0.6, pin_local=1.0)
        elif what == 'main2':
            solve(j, 'T6_MAIN2', 500.0, 0.5, pin_local=1.0)
    log('T6', what, 'done in', round(ck.s()), 's')
