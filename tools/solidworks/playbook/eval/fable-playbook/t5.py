"""T5: T3 met the requirement (yield 2.85, layers 2.21), so no change is required. bracket_c.SLDPRT is saved as the
unchanged T1 geometry so the file the task names exists, and the one change worth having is priced from the T3 result
itself: printing the bracket on its side (layers along Y) instead of base-down. A linear study does not depend on the
print direction, only the allowable does, so the T3 nodal results (cad/_sim/sw-eval/T3_1.npz) are re-read for layers
along Y. No new geometry, no new solve.
"""
import json

import numpy as np
from scipy.spatial import cKDTree

from common import HERE, OUT, PETG_G_CM3, Clock, beat, hand_volume, put
from swkit import bodies, close, expect, job, log, open_doc, save_as, volume

ck = Clock()
with job() as j:
    beat('T5 bracket_c', j.inst.pid)
    d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
    save_as(d, OUT / 'bracket_c.SLDPRT')
    vol = volume(d)
    expect('bracket_c volume', vol, hand_volume(), 0.001)
    expect('bodies', len(bodies(d)), 1, 0)
    close(j.sw, d)

t3 = json.loads((HERE / 'T3.json').read_text())
z = np.load(OUT.parent.parent.parent / '_sim' / 'sw-eval' / 'T3_1.npz', allow_pickle=True)
pos, s = z['pos'], z['s']
mask = (cKDTree(z['fixed']).query(pos)[0] >= 2 * 3.0) & (cKDTree(z['loaded']).query(pos)[0] >= 1.5)      # as series.masks
out = {}
for name, n, shear_cols in (('Z (base on the bed, as T3)', 3, (5, 6)), ('Y (on its side)', 2, (4, 6)), ('X (upright on the bed)', 1, (4, 5))):
    i = np.flatnonzero(mask)[np.argmax(s[mask, n])]
    tau = np.hypot(s[:, shear_cols[0]], s[:, shear_cols[1]])       # shear on the layer plane
    k = np.flatnonzero(mask)[np.argmax(tau[mask])]
    out[name] = dict(layer_tension_mpa=round(float(s[i, n]), 2), at=pos[i].round(2).tolist(), sf_layer=round(22.5 / float(s[i, n]), 2),
                     interlayer_shear_mpa=round(float(tau[k]), 2), shear_at=pos[k].round(2).tolist(), sf_shear=round(13.0 / float(tau[k]), 2))
    log(name, out[name])
mass = vol / 1000 * PETG_G_CM3
put('T5', dict(change='None required: the T3 bracket already meets the requirement (yield 2.85, layers 2.21), so bracket_c is '
                      'the T1 geometry unchanged.',
               mass_g=round(mass, 2), mass_growth_pct=0.0, sf_yield=t3['sf_yield'], sf_layer=t3['sf_layer'],
               print_orientation='base on the bed, layers stacked along Z (as T3)', verdict='pass', status='done',
               orientation_options=out, notes=''), ck.s())
