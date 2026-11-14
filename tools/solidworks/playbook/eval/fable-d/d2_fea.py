"""D2 studies on pair_fea.SLDPRT: 300 N on the bearing along +Y and along +X, and the contact proof for each.

    python d2_fea.py <tag> <el> <seat ctrl> <case> [<case> ...]       cases: Y300 X300 Y1 X1

Bodies: lower half (PETG, face Y -32 fixed), upper half (PETG), ring (steel), four M3 screws (steel: head on the
counterbore floor and thread end in the insert hole, both line to line so they bond; shank clear in its hole), and a
soft plug in the ring's bore with its hub hole fixed, which holds the ring while it is not yet touching the seat.
Contact: no penetration between the ring's outside and both seats (0.075 mm radial clearance as modelled), and between
the split faces (0.8 mm apart as modelled). Load: rigid remote load on the ring's bore at the bearing centre.
At most four studies per run (05-fea.md).
"""
import json
import os
import sys
import time

import numpy as np

from common import HERE, WIP
from swfea import NO_PENETRATION, PETG, SOLVER_DIRECT, STEEL, _arr, static
from swkit import NUL, L, close, expect, face_info, job, log, open_doc, pick

PAD = dict(name='Soft plug', EX=0.2e6, NUXY=0.30, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
PRED_NODES = dict(m=100000, c=60000, f=174000, s=146000)      # written before each run; m was the first guess
LOADS = dict(Y300=(0, 300.0, 0), X300=(300.0, 0, 0), Y1=(0, 1.0, 0), X1=(1.0, 0, 0))
PRED = dict(
    Y300='ring moves 0.075 (the clearance) plus about 0.5 mm of cap bending; peak in the upper half at the crown (X 0): outer '
         'face Y 32 in tension 18 to 38 MPa, inner shoulder edge in compression; screws 75 N each',
    X300='ring moves 0.075 plus about 0.1 mm; peak in the +X wall of either half beside the split or at a screw hole; '
         'screws about 24 N tension and 37.5 N shear each',
    Y1='ring crosses the clearance: 0.075 mm or more, about 300 times what 300 N would give in proportion',
    X1='ring crosses the clearance: 0.075 mm or more')


SHANK = float(os.environ.get('D2_SHANK', '0.7'))      # element size on the screw shanks
FIX = os.environ.get('D2_FIX', 'face')                # 'face': the whole face Y -32 held (the task); 'm4': only the two M4 insert hole walls


def reactions(st, res):
    return _arr(res.GetReactionForcesAndMoments(0, NUL, 0, L()), 9)


if __name__ == '__main__':
    tag, el, cs = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    cases = sys.argv[4:]
    out = {}
    with job() as j:
        j.simulation()
        d = open_doc(j.sw, WIP / 'pair_fea.SLDPRT')
        d.ForceRebuild3(False)
        for case in cases:
            fixed_face = pick(d, kind='plane', normal=(0, -1, 0), inside=[-37, -32.05, -5, 37, -31.95, 12])
            hub = pick(d, kind='cyl', r=3.0, inside=[-3.1, -3.1, 2.4, 3.1, 3.1, 4.6])
            bore = [f for f in pick(d, kind='cyl', r=24.0) if face_info(f)['box'][2] < 0.01 and face_info(f)['box'][5] > 6.99]
            ring_od = pick(d, kind='cyl', r=26.0)
            seats = pick(d, kind='cyl', r=26.075)
            split_up = pick(d, kind='plane', normal=(0, -1, 0), inside=[-37, 0.35, -5, 37, 0.45, 12])
            split_lo = [f for f in pick(d, kind='plane', normal=(0, 1, 0), inside=[-37, -0.45, -5, 37, -0.35, 12])
                        if face_info(f)['area'] > 100]
            shanks = pick(d, kind='cyl', r=1.5)
            if FIX == 'm4':
                fixed_face = pick(d, kind='cyl', r=2.8)
                expect('M4 hole walls', len(fixed_face), 2, 0)
                fixed_face = fixed_face[:1] + fixed_face[1:]
            for what, fs, n in (('fixed face', fixed_face, 2 if FIX == 'm4' else 1), ('hub', hub, 1), ('ring bore', bore, 1), ('ring outside', ring_od, 1),
                                ('seats', seats, 2), ('upper split faces', split_up, 2), ('lower split faces', split_lo, 2),
                                ('shanks', shanks, 4)):
                expect(what, len(fs), n, 0)
            log(f'PREDICT {case} el {el} seat {cs} shank {SHANK} fix {FIX}: nodes {PRED_NODES.get(tag, 100000)}; {PRED[case]}')
            t0 = time.time()
            r = static(j, d, f'D2_{case}_{tag}', PETG,
                       fixtures=[('fixed', fixed_face), ('fixed', hub)],
                       loads=[('remote', bore, (0.0, 0.0, 3.5), LOADS[case], (0, 0, 0))],
                       el=el, ctrl=[(seats + ring_od, cs), (shanks, SHANK)],
                       contacts=[(NO_PENETRATION, ring_od, seats), (NO_PENETRATION, split_up, split_lo)],
                       materials={'ring': STEEL, 'screw': STEEL, 'plug': PAD}, solver=SOLVER_DIRECT, loose_ok=True,
                       max_nodes=195000, post=reactions)
            s = r.summary()
            log(s)
            np.savez_compressed(WIP / f'd2_{case}_{tag}.npz', pos=r.pos, s=r.s, disp=r.disp, reac=r.extra, el=el, cs=cs,
                                fixed=r.fixed_pts if r.fixed_pts is not None else np.zeros((0, 3)),
                                loaded=r.loaded_pts if r.loaded_pts is not None else np.zeros((0, 3)))
            out[case] = dict(summary=s, seconds=round(time.time() - t0, 1), excessive=bool(r.excessive))
            (HERE / f'd2_fea_{tag}.json').write_text(json.dumps(out, indent=1, default=str))
        close(j.sw, d)
    print('DONE d2_fea', tag, flush=True)
