"""T3: static study of bracket.SLDPRT, 150 N along +X on the bore, base holes fixed, printed base-down (layers along Z)."""
import numpy as np

from common import BORE, F_MOTOR, OUT, R_IN, Clock, beat, put
from series import masks, series
from swfea import PETG
from swkit import job, log, pick

YIELD, LAYER = 45.0, 22.5
# hand: the upright is a cantilever, 50 wide x 6 thick, loaded at the bore centre Z 28, built in at the base top Z 6
I = 50 * 6 ** 3 / 12
hand_root = F_MOTOR * (BORE[1] - 6) * 3 / I                      # 11.0 MPa at Z 6
hand_fillet_top = F_MOTOR * (BORE[1] - 10) * 3 / I               # 9.0 MPa at Z 10, where the fillet ends
E = PETG['EX'] / 1e6
# displacement: the upright bends (F L^3 / 3 E I) and the base between the corner and the screws (19 mm, X 6 to 25) turns
# by M L / E I under M = 150 x 25, which swings the top of the upright (40 mm above the base) forward
hand_disp = F_MOTOR * 22 ** 3 / (3 * E * I) + F_MOTOR * 25 * 19 / (E * I) * 40


def extra(d):
    fil = pick(d, kind='cyl', r=R_IN, inside=[5.9, -0.1, 5.9, 10.1, 50.1, 10.1])
    back = pick(d, kind='plane', normal=(-1, 0, 0))
    assert len(fil) == 1 and len(back) == 1, (len(fil), len(back))
    return fil + back


ck = Clock()
with job() as j:
    beat('T3 study', j.inst.pid)
    rows, conv, r, chk = series(j, OUT / 'bracket.SLDPRT', 'T3', [(4.0, 1.2), (3.0, 0.8), (2.2, 0.55), (2.2, 0.4)], extra)

last = rows[-1]
play, mine = masks(r)
log('hand: root', hand_root, 'fillet top', hand_fillet_top, 'disp', hand_disp)
for rad in (0.5, 1.0, 2.0):
    log('average vm round the peak, radius', rad, r.average(last['peak_at_mm'], rad))
# where the masked-out maxima are
for nm, m in (('within 2 el of the fixed holes', ~(mine | (~play & mine))),):
    pass
sf_y, sf_l = YIELD / last['peak_vm_mpa'], LAYER / last['layer_stress_mpa']
verdict = 'pass' if conv and sf_y >= 2.0 and sf_l >= 2.0 else 'fail'
put('T3', dict(hand_root_stress_mpa=round(hand_root, 2), el_mm=last['el_mm'], nodes=last['nodes'],
               peak_vm_mpa=last['peak_vm_mpa'], peak_at_mm=last['peak_at_mm'], layer_stress_mpa=last['layer_stress_mpa'],
               sf_yield=round(sf_y, 2), sf_layer=round(sf_l, 2), max_disp_mm=last['max_disp_mm'],
               reaction_n=chk['reaction_n'], converged=conv, convergence_rows=rows, verdict=verdict, status='done',
               hand_disp_mm=round(hand_disp, 2), layer_at_mm=last['layer_at_mm'], plain_section=chk,
               notes=''), ck.s())
