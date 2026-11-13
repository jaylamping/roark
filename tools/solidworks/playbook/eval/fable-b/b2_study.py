"""B2: static study of the wall bracket. Two supports x three mesh sizes; every print direction read from each result."""
import json

from common import HERE, WIP, put, sha
from swkit import *
from bracket_fea import DFIX, F, checks, factors, measures, mask, solve

import numpy as np

# ---- the case, written down before SolidWorks (05-fea.md) -------------------------------------------------------------
# Load: 60 N down, even pressure on the top patch X 55..65, centre X 60: 55 mm from the plate face, 52 from the fillet end.
# Support: two screws through the plate into the wall. Real support is between "hole walls fixed" and "wall face fixed".
# Arm section 10 wide x 12 deep: I = 10 * 12^3 / 12 = 1440 mm4, c = 6.
I, C = 10 * 12 ** 3 / 12, 6.0
HAND_ROOT = F * 55 * C / I                     # 13.75 MPa at the plate face, no fillet
HAND_FILLET_END = F * 52 * C / I               # 13.0 MPa where the R3 fillet runs out (X 8)
KT = 1.35                                      # stepped flat bar in bending, r/d = 0.25, D/d large (Peterson): about 1.3 to 1.4
HAND_PEAK = KT * HAND_FILLET_END               # about 17.6 MPa in the fillet
E = 1900.0
HAND_DISP = F * 55 ** 3 / (3 * E * I) + F * 55 ** 2 / (2 * E * I) * 5      # beam only, tip at X 65: 1.38 mm; plate adds to it
HAND_SHEAR = 1.5 * F / 120                     # 0.75 MPa transverse shear in the arm
SIZES = (2.5, 1.75, 1.25)
VOL = 19079.5


def ctrl_for(el):
    def c(d):
        fl = pick(d, kind='cyl', r=3.0)
        expect('fillet faces for mesh control', len(fl), 2, 0)
        return [(fl, round(0.3 * el, 3))]
    return c


log(f'HAND root {HAND_ROOT:.2f} MPa, fillet end {HAND_FILLET_END:.2f}, fillet peak ~{HAND_PEAK:.1f}, tip {HAND_DISP:.2f} mm (beam only), '
    f'shear {HAND_SHEAR:.2f} MPa')
P = WIP / 'wall_bracket.SLDPRT'
out = dict(hand=dict(root=HAND_ROOT, fillet_end=HAND_FILLET_END, kt=KT, fillet_peak=HAND_PEAK, tip_disp_beam=HAND_DISP, shear=HAND_SHEAR),
           sha256=sha(P), dfix_mm=DFIX, runs=[])
with job() as j:
    j.simulation()
    d = open_doc(j.sw, P)
    for support in ('holes', 'wall'):
        for el in SIZES:
            tag = f'B2_{support}_{str(el).replace(".", "p")}'
            pred = dict(nodes=int(1.6 * VOL / (el ** 3 / 8.5) * 1.3), disp='1.4 to 2.5' if support == 'holes' else '1.4 to 1.8',
                        peak=f'~{HAND_PEAK:.0f} MPa (16 to 20) in the upper (tension) or lower root fillet, X 5..8')
            r = solve(j, d, tag, support, el, ctrl_for(el), pred)
            ck = checks(r, tag=tag)
            m = measures(r)
            # the two root fillets read on their own, whatever the mask does
            fil = {}
            for name, box in (('upper', [4.99, 14.9, 51.9, 9.0, 25.1, 55.5]), ('lower', [4.99, 14.9, 36.5, 9.0, 25.1, 40.1])):
                fil[name] = measures(r, r.in_box(box) & mask(r, 1.0))
            # what the mask left out
            ex = ~mask(r)
            hidden = dict(vm=round(float(r.vm[ex].max()), 2), at=r.pos[np.flatnonzero(ex)[np.argmax(r.vm[ex])]].round(2).tolist())
            row = dict(tag=tag, support=support, el=el, fillet_el=round(0.3 * el, 3), predicted=pred, checks=ck, measures=m, fillets=fil,
                       excluded_within_dfix=hidden, seconds=round(r.seconds, 1))
            log(tag, json.dumps(dict(measures=m, hidden=hidden), default=float))
            out['runs'].append(row)
            put('b2_study', out)
    close(j.sw, d)
print('B2 STUDY DONE')
