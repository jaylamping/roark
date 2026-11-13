"""C2 two quick ideas, each a rough model + picture. A: one grown oval bone. B: twin struts."""
import math, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2common import *
from swkit import *
import sheet

def flange(d, name):
    with Sk(d, plane(d, 'Y', 0.0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), 35.0)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID)
    with Sk(d, plane(d, 'Y', 0.0, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, 0), 15.0)
    extrude(d, s.feat, 'BORE', 10.0, cut=True, mode=MID)

def wrist_slot(d):
    with Sk(d, plane(d, 'X', 0.0, 'SLOT_P'), 'SLOT') as s:
        s.poly([(0, -16, -183), (0, 16, -183), (0, 16, -240), (0, -16, -240)])
    extrude(d, s.feat, 'SLOT', 80.0, cut=True, mode=MID)
    with Sk(d, plane(d, 'Y', 0.0, 'PIN_P'), 'PIN') as s:
        s.circle((0, 0, -200), 4.0)
    extrude(d, s.feat, 'PIN', 80.0, cut=True, mode=MID)

SEC_A = [(-32, 14, 4, 2.0, 0), (-48, 14.5, 9, 2.2, 0), (-95, 12.5, 10.5, 2.2, 0), (-150, 13.5, 11.5, 2.4, 0),
         (-172, 14.5, 16, 2.6, 0), (-190, 15, 22, 3.0, 0), (-211, 11, 20, 3.0, 0)]

with job(wait_s=1800) as j:
    d = new_part(j.sw, OUT / 'idea_a.SLDPRT')
    flange(d, 'a')
    loft_sections(d, SEC_A, 'STEM', plane, Sk, loft)
    save(d)
    wrist_slot(d)
    save(d)
    log('A', volume(d), bbox(d), len(bodies(d)), feature_errors(d))
    export(j.sw, d, OUT / 'idea_a.stl')
    close(j.sw, d)

    d = new_part(j.sw, OUT / 'idea_b.SLDPRT')
    flange(d, 'b')
    for sgn, nm in ((1, 'R'), (-1, 'L')):
        secs = [(-30, 6, 5, 2.0, sgn * 12), (-60, 6.5, 8, 2.0, sgn * 11), (-120, 6, 9, 2.0, sgn * 10.5),
                (-172, 8, 12, 2.2, sgn * 11), (-190, 10, 22, 3.0, sgn * 5)]
        loft_sections(d, secs, 'STRUT' + nm, plane, Sk, loft)
    with Sk(d, plane(d, 'Z', -199.0, 'LUG_P'), 'LUG') as s:
        s.rect((-14, -22, -199.0), (14, 22, -199.0))
    extrude(d, s.feat, 'LUG', 24.0, mode=MID)
    save(d)
    wrist_slot(d)
    save(d)
    log('B', volume(d), bbox(d), len(bodies(d)), feature_errors(d))
    export(j.sw, d, OUT / 'idea_b.stl')
    close(j.sw, d)
