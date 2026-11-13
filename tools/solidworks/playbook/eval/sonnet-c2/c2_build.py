"""C2 build: organic link, stage 1 (form, passage, slot, pin) then rounds."""
import math, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2common import *
from swkit import *

SEC = [(-32, 14, 8, 2.0, 0), (-46, 14.5, 12.5, 2.2, 0), (-95, 12.5, 11.5, 2.2, 0), (-150, 13.5, 12.5, 2.4, 0),
       (-172, 14.5, 17, 2.6, 0), (-190, 14.5, 23, 3.5, 0), (-204, 13.5, 23, 3.5, 0), (-212, 10.5, 20, 3.0, 0)]

RIDGE = [(-16, 6.5, 4.5, 2.0, 0, 4.0), (-26, 7.0, 4.5, 2.0, 0, 4.0), (-36, 9.0, 4.5, 2.0, 0, 4.0), (-44, 11.0, 5.0, 2.0, 0, 3.0)]

with job(wait_s=1800) as j:
    d = new_part(j.sw, OUT / 'link_organic.SLDPRT')
    prof = [(15, -4, 0), (32.5, -4, 0)]
    for k in range(1, 9):
        a = math.radians(-90 + 90 * k / 8); prof.append((32.5 + 2.5 * math.cos(a), -1.5 + 2.5 * math.sin(a), 0))
    prof += [(35, 7.6, 0), (34.5, 8.7, 0), (33.5, 8.3, 0), (32.4, 7.1, 0), (31.3, 5.9, 0), (30.3, 5.0, 0), (29.4, 4.35, 0), (28.6, 4.0, 0), (15, 4, 0)]
    with Sk(d, plane(d, 'Z', 0.0, 'DISC_P'), 'DISC') as s:
        s.poly(prof)
        s.centerline((0, -10, 0), (0, 10, 0))
    revolve(d, s.feat, 'DISC')
    with Sk(d, plane(d, 'Y', 0.0, 'HOLES_P'), 'HOLES') as s:
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((25 * math.cos(a), 0, 25 * math.sin(a)), 1.7)
    extrude(d, s.feat, 'HOLES', 10.0, cut=True, mode=MID, expect_dv=6 * math.pi * 1.7**2 * 8)
    loft_sections(d, RIDGE, 'RIDGE', plane, Sk, loft)
    loft_sections(d, SEC, 'STEM', plane, Sk, loft)
    save(d)
    import math as _m
    junc = edges_where(d, lambda p: -42 < p[2] < -29 and abs(_m.hypot(p[0], p[2])) > 33.5)
    log('junction edges', len(junc), [tuple(round(v,1) for v in p) for p in []])
    fj = fillet(d, junc, (5.0, 4.0, 3.0, 2.0), 'JUNCTION')
    log('junction fillet', fj is not None, volume(d))
    with Sk(d, plane(d, 'Z', -100.0, 'CABLE_P'), 'CABLE') as s:
        s.circle((0, 2.0, -100.0), 3.0)
    extrude(d, s.feat, 'CABLE', 172.0, cut=True, mode=MID)       # z -14 to -186
    with Sk(d, plane(d, 'X', 0.0, 'SLOT_P'), 'SLOT') as s:
        s.poly([(0, -16, -183), (0, 16, -183), (0, 16, -240), (0, -16, -240)])
    extrude(d, s.feat, 'SLOT', 80.0, cut=True, mode=MID)
    with Sk(d, plane(d, 'Y', 0.0, 'PIN_P'), 'PIN') as s:
        s.circle((0, 0, -200), 4.0)
    extrude(d, s.feat, 'PIN', 80.0, cut=True, mode=MID, expect_dv=None)
    save(d)
    log('stage1', volume(d), bbox(d), len(bodies(d)), feature_errors(d))
    export(j.sw, d, OUT / 'link_organic.stl')
    export(j.sw, d, OUT / 'link_organic.step')
    close(j.sw, d)

















