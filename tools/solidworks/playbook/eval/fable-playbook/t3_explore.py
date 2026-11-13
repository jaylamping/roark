"""T3 first look: one coarse solve to see where the peaks sit before choosing the mesh controls."""
import numpy as np

from common import OUT, R_IN, beat
from case import checks, run
from swkit import close, job, log, open_doc, pick

(OUT.parent.parent.parent / '_sim' / 'sw-eval').mkdir(parents=True, exist_ok=True)
with job() as j:
    beat('T3 explore', j.inst.pid)
    d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
    fil = pick(d, kind='cyl', r=R_IN, inside=[5.9, -0.1, 5.9, 10.1, 50.1, 10.1])
    r = run(j, d, 'T3_EXPLORE', 3.0, 1.0, [(fil, 1.0)])
    checks(r)
    close(j.sw, d)

away = r.away()
log('nodes away', int(away.sum()), 'of', len(away))
order = np.argsort(-r.vm * away)[:8]
for i in order:
    log('vm', round(float(r.vm[i]), 2), r.pos[i].round(2).tolist())
for n, nm in (((0, 0, 1), 'Z'), ((0, 1, 0), 'Y'), ((1, 0, 0), 'X')):
    log('layer', nm, r.layer_stress(n), 'unmasked', r.layer_stress(n, np.ones(len(r.pos), bool)))
log('vm max all', float(r.vm.max()), r.pos[np.argmax(r.vm)].round(2).tolist())
# top sz tension nodes away
sz = r.s[:, 3]
for i in np.argsort(-sz * away)[:10]:
    log('sz', round(float(sz[i]), 2), r.pos[i].round(2).tolist())
