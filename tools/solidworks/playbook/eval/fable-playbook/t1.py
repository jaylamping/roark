"""T1: model the bracket, export STEP and STL, check both files."""
import math

import numpy as np
import trimesh

from common import (BASE_HOLES, BORE, D_BASE, D_BORE, D_UP, OUT, PETG_G_CM3, R_IN, UP_HOLES, Clock, beat, hand_volume, put)
from bracket import build
from swkit import bbox, bodies, close, expect, export, face_info, feature_errors, job, log, pick, volume

ck = Clock()
with job() as j:
    beat('T1 bracket', j.inst.pid)
    d = build(j.sw, OUT / 'bracket.SLDPRT')
    vol, box, nb = volume(d), bbox(d), len(bodies(d))

    # position checks, not only size (06-judgment.md question 3): where every hole and the fillet actually are
    def centre(f):
        b = face_info(f)['box']
        return [(b[k] + b[k + 3]) / 2 for k in range(3)]
    got = sorted((round(centre(f)[0], 3), round(centre(f)[1], 3)) for f in pick(d, kind='cyl', r=D_BASE / 2))
    log('base holes at', got)
    assert got == sorted((float(x), float(y)) for x, y in BASE_HOLES), got
    bore = pick(d, kind='cyl', r=D_BORE / 2)
    expect('bore faces', len(bore), 1, 0)
    c = centre(bore[0])
    expect('bore centre Y', c[1], BORE[0], 0.01)
    expect('bore centre Z', c[2], BORE[1], 0.01)
    got = sorted((round(centre(f)[1], 2), round(centre(f)[2], 2)) for f in pick(d, kind='cyl', r=D_UP / 2))
    want = sorted((round(y, 2), round(z, 2)) for y, z in UP_HOLES)
    log('motor holes (Y, Z) at', got, 'want', want)
    assert np.allclose(got, want, atol=0.01)
    fil = pick(d, kind='cyl', r=R_IN, inside=[5.9, -0.1, 5.9, 10.1, 50.1, 10.1])
    expect('inside fillet faces', len(fil), 1, 0)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)

    export(j.sw, d, OUT / 'bracket.step')
    export(j.sw, d, OUT / 'bracket.stl')
    close(j.sw, d)

mesh = trimesh.load(OUT / 'bracket.stl')
wt = bool(mesh.is_watertight)
shells = len(mesh.split())
expect('STL watertight', float(wt), 1.0, 0)
expect('STL shells', shells, 1, 0)
expect('STL volume against the part', float(mesh.volume), vol, 0.005)
for k, (g, w) in enumerate(zip(list(mesh.bounds[0]) + list(mesh.bounds[1]), box)):
    expect(f'STL bound[{k}] in the model frame', float(g), w, 0.02)
step = (OUT / 'bracket.step').read_text(errors='ignore')
step_mm = 'SI_UNIT(.MILLI.,.METRE.)' in step.replace(' ', '')
log('STEP in mm:', step_mm, '| AP203:', 'CONFIG_CONTROL_DESIGN' in step)
assert step_mm

put('T1', dict(volume_mm3=round(vol, 2), hand_volume_mm3=round(hand_volume(), 2), mass_g=round(vol / 1000 * PETG_G_CM3, 2),
               bbox_mm=[round(v, 3) for v in box], bodies=nb, stl_watertight=wt, stl_volume_mm3=round(float(mesh.volume), 2),
               status='done',
               notes=f'STL one shell, bounds equal the part box (model frame); STEP is mm, AP203. Hole, bore and fillet '
                     f'positions measured on the model. STL volume is {100 * (float(mesh.volume) / vol - 1):+.3f} % off the part '
                     '(faceted cylinders).'), ck.s())
