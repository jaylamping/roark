"""D1 convergence: the governing case (9 N along -Z as an even force on the four post tops) at three element sizes.

All three measures are followed (von Mises, tension across Z layers, shear between Z layers), outside one fixed
distance (4 mm, two of the coarsest elements) from the fixture and load faces at every size.
"""
import json

import numpy as np

from common import HERE, WIP
from swfea import PETG, static
from swkit import close, expect, job, log, open_doc, pick

POSTS = [(sx * 39.0, sy * 26.5) for sx in (1, -1) for sy in (1, -1)]
SIZES = (2.0, 1.4, 1.0)
DIST = 4.0
rows = []
with job() as j:
    j.simulation()
    d = open_doc(j.sw, WIP / 'buck_mount.SLDPRT')
    d.ForceRebuild3(False)
    for el in SIZES:
        tops = [f for px, py in POSTS for f in pick(d, kind='plane', at=(px + 2.75, py, 8.0))]
        rings = [f for sx in (1, -1) for f in pick(d, kind='plane', at=(sx * 54.5, 0, 3.5))]
        expect('post top faces', len(tops), 4, 0)
        expect('spot faces', len(rings), 2, 0)
        log(f'PREDICT el {el}: nodes {int(78212 * (1.2 / el) ** 3)}, displacement and peak as the 1.2 mm solve of d1_build.py')
        r = static(j, d, f'D1_CONV_{int(el * 10)}', PETG, fixtures=[('fixed', rings)], loads=[('normal', tops, 9.0)], el=el)
        keep = r.away(dist=DIST)
        row = dict(el=el, nodes=r.nodes, vm=round(r.peak(keep)[0], 3), vm_at=r.peak(keep)[1],
                   layer=round(r.layer_stress((0, 0, 1), keep)[0], 3), layer_at=r.layer_stress((0, 0, 1), keep)[1],
                   shear=round(r.layer_shear((0, 0, 1), keep)[0], 3), shear_at=r.layer_shear((0, 0, 1), keep)[1],
                   max_disp=round(r.max_disp(), 4), reaction=r.reaction, vm_all=round(float(r.vm.max()), 3))
        rows.append(row)
        log('converge', row)
    close(j.sw, d)
last = {k: round(abs(rows[-1][k] - rows[-2][k]) / rows[-2][k], 4) for k in ('vm', 'layer', 'shear')}
out = dict(rows=rows, last_step_change=last, converged={k: v <= 0.05 for k, v in last.items()}, excluded_within_mm=DIST)
(HERE / 'd1_conv.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
