"""C2: organic forearm link. Usage: python c2build.py <idea> <out_name>   idea: a (lofted bone) | b (blade) | final"""
import math, sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
import numpy as np
from swkit import *
WIP = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-c'
EV = Path(__file__).resolve().parent

def sect(a, y0, y1, n, z, N=32):
    """Superellipse |x/a|^n + |(y-yc)/b|^n = 1 resampled to even arc length, N points, starting on +x. Points (x, y, z) mm."""
    yc, b = (y0 + y1) / 2, (y1 - y0) / 2
    t = np.linspace(0, 2 * np.pi, N, endpoint=False)      # same angles in every section: point k joins point k
    c, s_ = np.cos(t), np.sin(t)
    x = a * np.sign(c) * np.abs(c) ** (2 / n)
    y = yc + b * np.sign(s_) * np.abs(s_) ** (2 / n)
    return [(float(u), float(v), z) for u, v in zip(x, y)]

from scipy.interpolate import PchipInterpolator
# keys: (z, a, y0, y1, n); sections are sampled every ~12 mm from a monotone (PCHIP) curve through them, so the loft
# does not overshoot between a few far-apart sections (measured: 37 mm wide where 34 was drawn, and a pinch).
KEYS_A = [(-17, 7.5, -4, 9, 2), (-25, 8, -4, 9.5, 2), (-35, 12.5, -4, 10, 2), (-45, 16, -5, 10, 2), (-60, 17, -7.5, 10, 2.1),
          (-100, 15, -8.5, 9.5, 2.2), (-130, 14.5, -11, 11.5, 2.4), (-155, 15.5, -15, 15, 2.9), (-176, 16.5, -20.5, 20.5, 3.8),
          (-200, 15, -22, 22, 4), (-213, 11, -20.5, 20.5, 4)]
KEYS_B = [(-17, 12, -4, 4, 2), (-37, 20, -4, 5, 2), (-80, 20, -5, 5, 2), (-130, 18, -6, 6, 2.2), (-165, 17, -12, 12, 3.2),
          (-178, 16.5, -21, 21, 4), (-200, 15, -22, 22, 4), (-213, 11, -20.5, 20.5, 4)]

def dense(keys, step=12.0):
    u = -np.array([k[0] for k in keys], float)
    fs = [PchipInterpolator(u, [k[i] for k in keys]) for i in range(1, 5)]
    zs = [-17.0, -25.0] + [-v for v in np.arange(37.0, 213.0, step)] + [keys[-1][0]]
    return [(float(z),) + tuple(float(f(-z)) for f in fs) for z in zs]

A, B = dense(KEYS_A), dense(KEYS_B)

def base(j, path, idea_sections, disc_r=33.0):
    d = new_part(j.sw, path)
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), disc_r)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID, expect_dv=math.pi * disc_r**2 * 8)
    sks = []
    for k, (z, a, y0, y1, n) in enumerate(idea_sections):
        with Sk(d, plane(d, 'Z', z, f'S{k}_P'), f'S{k}') as s:
            s.spline(sect(a, y0, y1, n, z))
        sks.append(s.feat)
    loft(d, sks, 'BONE')
    save(d)
    return d

def rim_round(d):
    # outer rim of the elbow disc: soft on the +Y face, a small break on the mating side (outside the flat ring, R > 31)
    for yy, rr in ((4.0, 2.5), (-4.0, 1.4)):
        e = edges_where(d, lambda p: abs(math.hypot(p[0], p[2]) - 33.0) < 0.05 and abs(p[1] - yy) < 0.01)
        log('rim edges', yy, len(e))
        if e:
            log('rim round', yy, fillet(d, e, (rr, rr * 0.6), f'RIM_{int(yy)}'))

def features(d, slot_roof=-176.0, passage_y=1.2):
    with Sk(d, plane(d, 'Y', 0, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 0), 15.0)
    extrude(d, s.feat, 'BORE', 40.0, cut=True, mode=MID)
    with Sk(d, plane(d, 'Y', 0, 'HOLES_P'), 'HOLES') as s:
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((25 * math.cos(a), 0, 25 * math.sin(a)), 1.7)
    extrude(d, s.feat, 'HOLES', 40.0, cut=True, mode=MID)
    # slot between the cheeks: |y| < 16, z below the roof, through all X
    with Sk(d, plane(d, 'X', 0, 'SLOT_P'), 'SLOT') as s:
        s.rect((0, -16, slot_roof), (0, 16, -240))
    extrude(d, s.feat, 'SLOT', 80.0, cut=True, mode=MID)
    save(d)
    rim_round(d)
    sel = lambda: edges_where(d, lambda p: abs(p[2] - slot_roof) < 0.01 and abs(abs(p[1]) - 16) < 0.01)
    r = fillet(d, sel(), (4.0, 3.0, 2.0), 'SLOT_ROOF_R')
    if r is None:
        for k in range(4):
            cur = sel()
            if k >= len(cur):
                break
            r = fillet(d, [cur[k]], (4.0, 3.0, 2.0, 1.5), f'SLOT_ROOF_R{k}')
            log('slot roof fillet edge', k, r)
    log('slot roof fillet', r)
    with Sk(d, plane(d, 'Y', 0, 'PIN_P'), 'PIN') as s:
        s.circle((0, 0, -200), 4.0)
    extrude(d, s.feat, 'PIN', 80.0, cut=True, mode=MID)
    # straight cable passage O6 along Z at x=0, y=passage_y, from the bore wall to the slot roof
    with Sk(d, plane(d, 'Z', -10.0, 'CABLE_P'), 'CABLE') as s:
        s.circle((0, passage_y, -10.0), 3.0)
    extrude(d, s.feat, 'CABLE', 2 * (178 - 10) / 2 * 0 + 0.0 + 168.0 + 0, cut=True, mode=BLIND, want=(2, -1, -10.0))
    save(d)

if __name__ == '__main__':
    idea, out = sys.argv[1], sys.argv[2]
    with job() as j:
        d = base(j, WIP / f'{out}.SLDPRT', {'a': A, 'b': B, 'final': A}[idea])
        features(d)
        log('volume', volume(d), 'bbox', bbox(d), 'bodies', bodies(d), 'errors', feature_errors(d))
        export(j.sw, d, WIP / f'{out}.stl')
        save(d)
        close(j.sw, d)
