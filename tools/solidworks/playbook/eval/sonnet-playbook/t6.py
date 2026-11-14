import json, math, sys, time
from pathlib import Path
WT = r"J:\code\roark-wt\sw-eval-sonnet"
sys.path.insert(0, WT + r"\tools\solidworks")
import numpy as np
from swkit import *
from swfea import *
OUT = Path(WT) / 'cad' / '_wip' / 'sw-eval' / 'sonnet-playbook' / 't6'
R = Path(__file__).parent
PAD = dict(name='Soft pad', EX=0.5e6, NUXY=0.45, DENS=1000.0, SIGYLD=1e6, SIGXT=1e6)
GAP = 0.1

def cyl_part(j, name, yc, length, r_out, r_in=None, zc=10.0):
    d = new_part(j.sw, OUT / f'{name}.SLDPRT')
    with Sk(d, plane(d, 'Y', yc, name.upper() + '_P'), name.upper()) as s:
        s.circle((0, yc, zc), r_out)
        if r_in:
            s.circle((0, yc, zc), r_in)
    area = math.pi * (r_out ** 2 - (r_in or 0) ** 2)
    extrude(d, s.feat, name.upper(), length, mode=MID, expect_dv=area * length)
    save(d); close(j.sw, d)

def build(j):
    for nm, yc, ln in (('ct6_pin_m', 0.0, 30.0), ('ct6_pin_l', -20.0, 10.0), ('ct6_pin_r', 20.0, 10.0)):
        cyl_part(j, nm, yc, ln, 5.0)
    for nm, yc in (('ct6_pad_l', -16.2), ('ct6_pad_r', 16.2)):
        cyl_part(j, nm, yc, 2.0, 6.5, 5.0)
    d = new_part(j.sw, OUT / 'ct6.SLDPRT')
    with Sk(d, plane(d, 'Z', 10.0, 'BLK_P'), 'BLOCK') as s:
        s.rect((-20, -15, 10.0), (20, 15, 10.0))
    extrude(d, s.feat, 'BLOCK', 20.0, mode=MID, expect_dv=40 * 30 * 20)
    with Sk(d, plane(d, 'Y', 0.0, 'HOLE_P'), 'HOLE') as s:
        s.circle((0, 0, 10.0), 5.1)
    extrude(d, s.feat, 'HOLE', 40.0, cut=True, mode=MID, expect_dv=math.pi * 5.1 ** 2 * 30)
    for nm in ('ct6_pin_m', 'ct6_pin_l', 'ct6_pin_r', 'ct6_pad_l', 'ct6_pad_r'):
        insert_body(d, OUT / f'{nm}.SLDPRT')
    bs = bodies(d)
    for b in bs:
        log('body', b)
    expect('bodies', len(bs), 6, 0)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    save(d)
    # overlap check: bodies must not interpenetrate: pin r5 in hole r5.1 (gap 0.1); pads touch block face only
    exp = math.pi * 5.1 ** 2 * 0   # (volumes listed above)
    tot = volume(d)
    want = 40 * 30 * 20 - math.pi * 5.1 ** 2 * 30 + math.pi * 25 * 50 + 2 * math.pi * (6.5 ** 2 - 25) * 2
    expect('total volume (no overlap double count)', tot, want, 0.001)
    close(j.sw, d)

def solve(j, d, tag, el, cl, contact=True, loose_ok=False, load=250.0, solver=SOLVER_DIRECT):
    blk_bot = pick(d, kind='plane', normal=(0, 0, -1), at=(0, 0, 0))
    expect(tag + ' bottom face', len(blk_bot), 1, 0)
    hole = pick(d, kind='cyl', r=5.1)
    expect(tag + ' hole face', len(hole), 1, 0)
    pm = pick(d, kind='cyl', r=5.0, inside=[-5.1, -15.01, 4.9, 5.1, 15.01, 15.1])
    expect(tag + ' pin mid face', len(pm), 1, 0)
    pl = pick(d, kind='cyl', r=5.0, inside=[-5.1, -25.01, 4.9, 5.1, -14.99, 15.1], area=math.pi * 10 * 10)
    pr = pick(d, kind='cyl', r=5.0, inside=[-5.1, 14.99, 4.9, 5.1, 25.01, 15.1], area=math.pi * 10 * 10)
    expect(tag + ' pin left face', len(pl), 1, 0)
    expect(tag + ' pin right face', len(pr), 1, 0)
    loads = [('remote', pl, (0, -20.0, 10.0), (0, 0, load), (0, 0, 0)), ('remote', pr, (0, 20.0, 10.0), (0, 0, load), (0, 0, 0))]
    pads_out = pick(d, kind='cyl', r=6.5)
    expect(tag + ' pad outer faces', len(pads_out), 2, 0)
    return static(j, d, tag, PETG, fixtures=[('fixed', blk_bot), ('fixed', pads_out)], loads=loads, el=el, ctrl=[(hole + pm, cl)],
                  contacts=[(NO_PENETRATION, hole, pm)] if contact else [],
                  materials={'ct6_pin': STEEL, 'ct6_pad': PAD}, solver=solver, loose_ok=loose_ok)

def label(r):
    """Body of each node by geometry: radial distance from the pin axis (x 0, z 10)."""
    rad = np.hypot(r.pos[:, 0], r.pos[:, 2] - 10.0)
    y = np.abs(r.pos[:, 1])
    pin = rad < 5.05
    inblock = (y <= 15.0 + 1e-3) & (np.abs(r.pos[:, 0]) <= 20.001) & (r.pos[:, 2] <= 20.001) & (r.pos[:, 2] >= -1e-3) & (rad >= 5.05)
    pad = (y > 15.0 + 1e-3) & (rad >= 5.05) | ((y >= 15 - 1e-3) & (rad >= 5.05) & (rad <= 6.5 + 1e-3) & False)
    return rad, y, pin, inblock, pad
