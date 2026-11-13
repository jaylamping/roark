"""T4: the bracket without the inside-corner fillet, same load case. The corner is a re-entrant edge: expect a singularity.

Also builds bracket_r05.SLDPRT, the same part with a 0.5 mm inside radius, as a stand-in for what a printer actually leaves
in a "sharp" corner, because a radius is the only thing that gives the corner a stress that converges (05-fea.md).
"""
import numpy as np

from common import BORE, F_MOTOR, OUT, Clock, beat, put
from bracket import build, near
from case import checks, run
from series import masks, score
from swkit import close, edges_where, expect, job, log, open_doc, pick

YIELD, LAYER = 45.0, 22.5
CORNER = (6.0, 25.0, 6.0)
hand_root = F_MOTOR * (BORE[1] - 6) * 3 / (50 * 6 ** 3 / 12)      # 11.0 MPa nominal bending at the root section


def sharp_series(j):
    rows = []
    for k, loc in enumerate((1.0, 0.5, 0.25, 0.125)):
        d = open_doc(j.sw, OUT / 'bracket_sharp.SLDPRT')
        edge = edges_where(d, lambda p: near(p[0], 6) and near(p[2], 6))
        expect('corner edge', len(edge), 1, 0)
        r = run(j, d, f'T4_{k}', 3.0, 1.2, [(edge, loc)])
        checks(r, f'T4_{k} ')
        close(j.sw, d)
        row = score(r, (0, 0, 1))
        row['corner_edge_local_mm'] = loc
        # the corner itself: the worst node within 1 mm of the edge, its sz sign, and averages round the mid-point
        nearc = (np.hypot(r.pos[:, 0] - 6, r.pos[:, 2] - 6) < 1.0)
        i = np.flatnonzero(nearc)[np.argmax(r.vm[nearc])]
        row['corner_peak_vm_mpa'] = round(float(r.vm[i]), 2)
        row['corner_peak_at_mm'] = r.pos[i].round(2).tolist()
        row['corner_peak_sz_mpa'] = round(float(r.s[i, 3]), 2)
        row['corner_avg_vm'] = {str(rad): [round(v, 2), n] for rad in (0.5, 1.0, 2.0) for v, n in [r.average(CORNER, rad)]}
        # the layer stress away from the corner (the tension side is the back face X 0)
        rows.append(row)
        log('ROW', row)
    return rows, r


def r05_series(j):
    rows, conv = [], False
    for k, loc in enumerate((0.25, 0.15, 0.1)):
        d = open_doc(j.sw, OUT / 'bracket_r05.SLDPRT')
        fil = pick(d, kind='cyl', r=0.5, inside=[5.9, -0.1, 5.9, 6.6, 50.1, 6.6])
        expect('R0.5 fillet face', len(fil), 1, 0)
        r = run(j, d, f'T4R05_{k}', 3.0, 1.2, [(fil, loc)])
        checks(r, f'T4R05_{k} ')
        close(j.sw, d)
        row = score(r, (0, 0, 1))
        row['fillet_local_mm'] = loc
        i = int(np.argmax(np.where(masks(r)[1], r.vm, -1)))
        row['peak_sz_mpa'] = round(float(r.s[i, 3]), 2)
        rows.append(row)
        log('ROW R0.5', row)
        if len(rows) > 1 and abs(rows[-1]['peak_vm_mpa'] - rows[-2]['peak_vm_mpa']) <= 0.05 * rows[-2]['peak_vm_mpa']:
            conv = True
            break
    return rows, conv


ck = Clock()
with job() as j:
    beat('T4 sharp variant', j.inst.pid)
    close(j.sw, build(j.sw, OUT / 'bracket_sharp.SLDPRT', inside_fillet=0))
    close(j.sw, build(j.sw, OUT / 'bracket_r05.SLDPRT', inside_fillet=0.5))
    rows, r = sharp_series(j)
    beat('T4 R0.5 stand-in')
    rows05, conv05 = r05_series(j)

peaks = [x['corner_peak_vm_mpa'] for x in rows]
steps = [abs(b - a) / a for a, b in zip(peaks, peaks[1:])]
converged = bool(steps[-1] <= 0.05)
log('corner peaks', peaks, 'steps', [round(100 * s, 1) for s in steps], 'converged', converged)
put('T4', dict(convergence_rows=rows, converged=converged, r05_rows=rows05, r05_converged=conv05,
               hand_root_stress_mpa=round(hand_root, 2), status='partial', notes='numbers only; verdict in merge.py'), ck.s())
