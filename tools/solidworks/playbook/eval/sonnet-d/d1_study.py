"""D1 study: 9 N (10 g on 90 g) through the board centre, three directions, two ways of loading, two supports."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
from swkit import *   # noqa
from swfea import *   # noqa

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d1")
RES = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d")
TH = 41.0
C, S = math.cos(math.radians(TH)), math.sin(math.radians(TH))
CG = (0.0, -0.5 - 0.8 * S, 22.8 + 0.8 * C)        # board centre, mid thickness
F = 9.0

if __name__ == '__main__':
    rows = []
    with job() as j:
        d = open_doc(j.sw, OUT / 'buck_mount.SLDPRT')
        j.simulation()
        d.ForceRebuild3(False)
        tops = pick(d, kind='plane', normal=(0, -S, C), area=math.pi * (3.5 ** 2 - 1.35 ** 2))
        walls = pick(d, kind='cyl', r=1.35)
        m5 = pick(d, kind='cyl', r=2.75)
        bottom = pick(d, kind='plane', normal=(0, 0, -1), at=(50, 8, 0))
        log('picks: standoff tops', len(tops), 'pilot walls', len(walls), 'M5 walls', len(m5), 'base bottom', len(bottom))
        expect('standoff tops', len(tops), 4, 0)
        expect('M5 walls', len(m5), 2, 0)
        expect('base bottom', len(bottom), 1, 0)
        # predictions before any solve: ~16.7 cm3 part at 2 mm elements: about 25,000 to 40,000 nodes; peak displacement
        # under 0.05 mm (a 9 N load on a 7 mm thick rib), peak on a standoff root or the thin low rib end.
        log('PREDICTION: nodes ~30,000, displacement < 0.05 mm, peak at a standoff root (|stress| < 3 MPa)')
        cases = [('X', (F, 0, 0)), ('Y', (0, F, 0)), ('Z', (0, 0, -F))]
        for tag, f in cases:
            for how, faces_ in (('tops', tops), ('walls', walls)):
                if how == 'walls' and len(walls) == 0:
                    continue
                name = f'L_{tag}_{how}'
                ctrl = [(tops, 0.8)]
                r = static(j, d, name, PETG, fixtures=[('fixed', m5)],
                           loads=[('remote', faces_, CG, f, (0, 0, 0))], el=2.0, ctrl=ctrl, loose_ok=True)
                vm, at = r.peak()
                lay = {k: r.layer_stress(n) for k, n in (('Z', (0, 0, 1)), ('X', (1, 0, 0)), ('Y', (0, 1, 0)))}
                sh = {k: r.layer_shear(n) for k, n in (('Z', (0, 0, 1)), ('X', (1, 0, 0)), ('Y', (0, 1, 0)))}
                row = dict(name=name, nodes=r.nodes, disp=r.max_disp(), reaction=r.reaction, applied=r.applied,
                           vm=vm, at=at, vm_all=float(r.vm.max()), layer=lay, shear=sh, support='M5 walls')
                log(json.dumps(row))
                rows.append(row)
                np.savez_compressed(OUT / f'{name}.npz', pos=r.pos, s=r.s, disp=r.disp)
        # second support: the whole base bottom face (includes the rib foot overhang, so it is stiffer)
        for tag, f in cases[:2]:
            name = f'B_{tag}_tops'
            r = static(j, d, name, PETG, fixtures=[('fixed', bottom)],
                       loads=[('remote', tops, CG, f, (0, 0, 0))], el=2.0, ctrl=[(tops, 0.8)], loose_ok=True)
            vm, at = r.peak()
            row = dict(name=name, nodes=r.nodes, disp=r.max_disp(), reaction=r.reaction, vm=vm, at=at,
                       layer={k: r.layer_stress(n) for k, n in (('Z', (0, 0, 1)), ('X', (1, 0, 0)), ('Y', (0, 1, 0)))},
                       shear={k: r.layer_shear(n) for k, n in (('Z', (0, 0, 1)), ('X', (1, 0, 0)), ('Y', (0, 1, 0)))},
                       support='base bottom face')
            log(json.dumps(row))
            rows.append(row)
        close(j.sw, d)
    (RES / 'd1_study.json').write_text(json.dumps(rows, indent=1, default=float))
    print('STUDY DONE')
