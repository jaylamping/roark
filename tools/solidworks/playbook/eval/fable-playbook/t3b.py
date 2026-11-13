"""T3 supplement: what did the fixture mask hide at the screw holes?

In T3 the four hole walls are fixed and everything within two elements of them is left out of the peak. The left-out
maximum rose with the mesh (28.7, 33.2 MPa), and the base really does carry the whole corner moment past the X 25 holes,
so a real stress concentration sits exactly where the mask is. This model holds the bracket the way a screw head does
instead: a steel washer (dia 10 x 1, hole 5.5) bonded on the base top over each hole, the washers' top faces fixed, the
hole walls free. The hole walls and the base underside can then be scored. FEA-only model in _wip; not a design change.
"""
import math

import numpy as np

from common import BASE_HOLES, BORE, D_BASE, F_MOTOR, OUT, R_IN, Clock, beat, put
from swfea import PETG, STEEL, static
from swkit import (MID, Sk, bodies, close, expect, extrude, insert_body, job, log, new_part, open_doc, pick, plane, save, save_as)

import swfea
swfea.MAX_NODES = 150_000          # this run's own ceiling (the coordinator's limit), far under static()'s 450,000

ck = Clock()
rows = []
with job() as j:
    # Load Simulation BEFORE opening and picking. The first version of this script picked faces and let static() load
    # the add-in afterwards; on a freshly launched instance and this multi-body file the first study then meshed 282,484
    # nodes instead of 53,556 and gave a different answer (9.4 mm displacement): the picked faces no longer meant the
    # same faces. See REPORT.md, "Playbook problems".
    j.simulation()
    beat('T3 supplement: screw-head support', j.inst.pid)
    for k, (x, y) in enumerate(BASE_HOLES):
        if (OUT / 'bracket_fea_washers.SLDPRT').exists():
            break
        d = new_part(j.sw, OUT / f'washer_{k}.SLDPRT')
        with Sk(d, plane(d, 'Z', 6.5, 'WASHER_P'), 'WASHER') as s:
            s.circle((x, y, 6.5), 5.0)
            s.circle((x, y, 6.5), D_BASE / 2)
        extrude(d, s.feat, 'WASHER', 1.0, mode=MID, expect_dv=math.pi * (25 - (D_BASE / 2) ** 2))
        save(d)
        close(j.sw, d)
    if not (OUT / 'bracket_fea_washers.SLDPRT').exists():
        d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
        save_as(d, OUT / 'bracket_fea_washers.SLDPRT')
        for k in range(4):
            insert_body(d, OUT / f'washer_{k}.SLDPRT')
        expect('bodies', len(bodies(d)), 5, 0)
        save(d)
        close(j.sw, d)

    for k, local in enumerate((0.8, 0.5)):
        d = open_doc(j.sw, OUT / 'bracket_fea_washers.SLDPRT')
        d.ForceRebuild3(False)
        tops = pick(d, kind='plane', normal=(0, 0, 1), inside=[15, 0, 6.9, 75, 50, 7.1])
        walls = pick(d, kind='cyl', r=D_BASE / 2, inside=[15, 0, -0.1, 75, 50, 6.1])
        bore = pick(d, kind='cyl', r=11.0)
        fil = pick(d, kind='cyl', r=R_IN, inside=[5.9, -0.1, 5.9, 10.1, 50.1, 10.1])
        for what, fs, n in (('washer tops', tops, 4), ('hole walls', walls, 4), ('bore', bore, 1), ('fillet', fil, 1)):
            expect(what, len(fs), n, 0)
        r = static(j, d, f'T3B_{k}', PETG, fixtures=[('fixed', tops)],
                   loads=[('remote', bore, (3.0, BORE[0], BORE[1]), (F_MOTOR, 0, 0), (0, 0, 0))], el=3.0,
                   ctrl=[(walls, local), (fil, 1.0), (bore, 1.0)], materials={'washer': STEEL})
        close(j.sw, d)
        expect('reaction Fx', r.reaction[0], -F_MOTOR, 0.01)
        log('fixed nodes box', r.fixed_pts.min(axis=0).round(2), r.fixed_pts.max(axis=0).round(2), len(r.fixed_pts),
            '| loaded nodes box', r.loaded_pts.min(axis=0).round(2), r.loaded_pts.max(axis=0).round(2))
        assert abs(r.fixed_pts[:, 2] - 7.0).max() < 0.01 and r.fixed_pts[:, 0].min() < 21, 'fixture is not on the four washer tops'
        p = r.pos
        bracket = p[:, 2] <= 6.0 + 1e-6                               # washers are Z 6 to 7; the upright is excluded below
        rad = np.min([np.hypot(p[:, 0] - x, p[:, 1] - y) for x, y in BASE_HOLES], axis=0)
        near_hole = bracket & (rad < 8.0) & (p[:, 0] > 12)
        # leave out the bonded washer footprint: nodes on the top 1 mm of the base under or within 1 mm of a washer
        foot = (p[:, 2] > 5.0) & (rad < 6.0)
        m = near_hole & ~foot
        i = np.flatnonzero(m)[np.argmax(r.vm[m])]
        mf = near_hole & foot
        ifo = np.flatnonzero(mf)[np.argmax(r.vm[mf])]
        sz = r.s[:, 3]
        iz = np.flatnonzero(m)[np.argmax(sz[m])]
        low = near_hole & (p[:, 2] < 4.0)                             # hole walls below the washer zone and the underside
        il = np.flatnonzero(low)[np.argmax(r.vm[low])]
        np.savez_compressed(OUT.parent.parent.parent / '_sim' / 'sw-eval' / f'T3B_{k}.npz', pos=r.pos, s=r.s, disp=r.disp)
        # cross-check against T3: the fillet peak and the back-face layer stress should not care how the screws are modelled
        fz = (p[:, 0] < 12) & (p[:, 2] < 12) & (p[:, 0] > 5.9)
        back = (p[:, 0] < 0.01) & (p[:, 2] > 6) & (p[:, 2] < 14)
        row = dict(local_mm=local, nodes=r.nodes,
                   hole_peak_vm_mpa=round(float(r.vm[i]), 2), hole_peak_at_mm=p[i].round(2).tolist(),
                   hole_peak_sx_mpa=round(float(r.s[i, 1]), 2), hole_peak_sz_mpa=round(float(r.s[i, 3]), 2),
                   hole_layer_sz_mpa=round(float(sz[iz]), 2), hole_layer_at_mm=p[iz].round(2).tolist(),
                   low_peak_vm_mpa=round(float(r.vm[il]), 2), low_peak_at_mm=p[il].round(2).tolist(),
                   low_peak_sx_mpa=round(float(r.s[il, 1]), 2), low_peak_sz_mpa=round(float(r.s[il, 3]), 2),
                   under_washer_vm_mpa=round(float(r.vm[ifo]), 2), under_washer_at_mm=p[ifo].round(2).tolist(),
                   fillet_peak_vm_mpa=round(float(r.vm[fz].max()), 2), back_face_sz_mpa=round(float(sz[back].max()), 2),
                   max_disp_mm=round(r.max_disp(), 4), reaction_n=r.reaction)
        rows.append(row)
        log('ROW', row)

put('T3B', dict(rows=rows), ck.s())
