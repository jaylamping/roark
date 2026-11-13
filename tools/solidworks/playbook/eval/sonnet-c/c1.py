"""C1: the boxy forearm link, as first drawn. Run name sonnet-c."""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *
WIP = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-c'
EV = Path(__file__).resolve().parent

def build(j):
    d = new_part(j.sw, WIP / 'link_boxy.SLDPRT')
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), 35.0)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID, expect_dv=math.pi * 35**2 * 8)
    with Sk(d, plane(d, 'Y', 0, 'BEAM_P'), 'BEAM') as s:
        s.rect((-20, 0, -170), (20, 0, -32))
    v0 = volume(d)
    extrude(d, s.feat, 'BEAM', 30.0, mode=MID)
    log('beam added', volume(d) - v0)
    with Sk(d, plane(d, 'Y', 0, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((-20, 0, -180), (20, 0, -170))
    extrude(d, s.feat, 'BLOCK', 44.0, mode=MID, expect_dv=40 * 44 * 10)
    for y0, nm in ((19.0, 'CHEEK_R'), (-19.0, 'CHEEK_L')):
        with Sk(d, plane(d, 'Y', y0, nm + '_P'), nm) as s:
            s.rect((-15, y0, -215), (15, y0, -170))
        extrude(d, s.feat, nm, 6.0, mode=MID)
    with Sk(d, plane(d, 'Y', 0, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 0), 15.0)
    extrude(d, s.feat, 'BORE', 20.0, cut=True, mode=MID, expect_dv=math.pi * 225 * 8)
    with Sk(d, plane(d, 'Y', 0, 'HOLES_P'), 'HOLES') as s:
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((25 * math.cos(a), 0, 25 * math.sin(a)), 1.7)
    extrude(d, s.feat, 'HOLES', 20.0, cut=True, mode=MID, expect_dv=6 * math.pi * 1.7**2 * 8)
    with Sk(d, plane(d, 'Y', 0, 'PIN_P'), 'PIN') as s:
        s.circle((0, 0, -200), 4.0)
    extrude(d, s.feat, 'PIN', 60.0, cut=True, mode=MID, expect_dv=2 * math.pi * 16 * 6)
    save(d)
    return d

def hand_volume():
    # union by sampling is avoided: analytic pieces, disc/beam overlap by integration (strip x, z in -35..-32)
    zs = np.linspace(-35, -32, 30001)
    xw = np.minimum(np.sqrt(np.maximum(35**2 - zs**2, 0)), 20) * 2
    ov = float(np.trapezoid(xw, zs)) * 8        # inside disc thickness Y +-4 (beam Y +-15 covers it)
    disc = math.pi * 35**2 * 8 - math.pi * 225 * 8 - 6 * math.pi * 1.7**2 * 8
    beam = 40 * 30 * 138
    block = 40 * 44 * 10
    cheeks = 2 * 30 * 6 * 45 - 2 * 30 * 6 * 10      # cheeks Z -215..-170, minus overlap with block Z -180..-170
    pin = 2 * math.pi * 16 * 6
    return disc + beam - ov + block + cheeks - pin

if __name__ == '__main__':
    with job() as j:
        d = build(j)
        v = volume(d)
        log('volume', v, 'bbox', bbox(d), 'bodies', bodies(d), 'errors', feature_errors(d))
        single_body(d)
        for k, want in {'bore': (15.0, 1), 'holes': (1.7, 6), 'pin': (4.0, 2)}.items():
            n = len(pick(d, kind='cyl', r=want[0]))
            log(k, 'faces', n)
        export(j.sw, d, WIP / 'link_boxy.stl')
        export(j.sw, d, WIP / 'link_boxy.step')
        save(d)
        close(j.sw, d)
    hv = hand_volume()
    import trimesh
    m_ = trimesh.load(WIP / 'link_boxy.stl')
    log('stl vol', m_.volume, 'wt', m_.is_watertight, 'bodies', len(m_.split()), 'hand', hv, 'bounds', m_.bounds.tolist())
    json.dump(dict(volume_mm3=v, stl_volume=float(m_.volume), hand_volume_mm3=hv, mass_g=v * 1.19e-3, bodies=len(m_.split())),
              open(EV / 'c1_raw.json', 'w'))
