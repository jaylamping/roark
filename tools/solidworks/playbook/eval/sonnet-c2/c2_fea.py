"""C2 FEA: 60 N at the pin in +X, -X, +Y, elbow ring held. One job, three studies, one mesh size."""
import math, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2common import *
import numpy as np
from swkit import *
from swfea import *
EL = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
SUP = sys.argv[2] if len(sys.argv) > 2 else 'ring'
CASES = [('PX', (60, 0, 0)), ('MX', (-60, 0, 0)), ('PY', (0, 60, 0))]
if len(sys.argv) > 3: CASES = [c for c in CASES if c[0] in sys.argv[3].split(',')]
NORMALS = {'Xup': (1, 0, 0), 'Yup': (0, 1, 0), 'Zup': (0, 0, 1)}
out = {}
with job(wait_s=1800) as j:
    j.simulation()
    for tag, F in CASES:
        d = open_doc(j.sw, OUT / 'link_organic.SLDPRT')
        d.ForceRebuild3(False)
        ring = pick(d, kind='plane', normal=(0, -1, 0), at=(20, -4, 0))
        holes = pick(d, kind='cyl', r=1.7)
        pin = pick(d, kind='cyl', r=4.0)
        tip = pick(d, kind='cyl', r=4.0, inside=[-5, -30, -205, 5, 30, -195])
        log(tag, 'ring faces', len(ring), 'hole faces', len(holes), 'pin faces', len(pin), len(tip))
        if len(ring) != 1 or len(tip) < 1: raise SystemExit('bad picks')
        fx = ring if SUP == 'ring' else holes
        vol = volume(d)
        log(f'PREDICT {tag}: nodes ~{12 * vol / EL**3 * 1.4:.0f}, tip displacement ~3 mm (F L^3/3EI, I~15000 mm4), peak at the stem root Z -32 to -50')
        r = static(j, d, f'{tag}_{SUP}_{EL}', PETG, fixtures=[('fixed', fx)],
                   loads=[('remote', tip, (0, 0, -200), F, (0, 0, 0))], el=EL,
                   ctrl=[(tip, 1.2)], loose_ok=True)
        log(r.summary())
        row = dict(nodes=r.nodes, disp=r.max_disp(), reaction=[float(v) for v in r.reaction], applied=r.applied, vm=r.peak())
        for nm, n in NORMALS.items():
            row[nm] = dict(layer=str(r.layer_stress(n)), shear=str(r.layer_shear(n)))
        out[tag] = row
        np.savez_compressed(OUT / f'c2_{tag}_{SUP}_{EL}.npz', pos=r.pos, s=r.s, disp=r.disp)
        close(j.sw, d)
(OUT / f'c2_fea_{SUP}_{EL}.json').write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))

