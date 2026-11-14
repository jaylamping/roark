"""B2 cheapest improvement: the same bracket with the R3 root fillet carried all round the arm (sides as well).

Not the specified part: saved as wall_bracket_allround.SLDPRT to show what the sharp side edges cost.
"""
import json
import math

from common import DENS, WIP, put, sha
from swkit import *
import b2_model as M
from bracket_fea import checks, factors, measures, solve

P = WIP / 'wall_bracket_allround.SLDPRT'
rows = []
with job() as j:
    j.simulation()
    d = new_part(j.sw, P)
    with Sk(d, plane(d, 'X', 2.5, 'PLATE_P'), 'PLATE') as s:
        s.rect((2.5, 0, 0), (2.5, 40, 60))
    extrude(d, s.feat, 'PLATE', 5.0, mode=MID, expect_dv=M.v_plate)
    with Sk(d, plane(d, 'X', 2.5, 'HOLES_P'), 'SCREW_HOLES') as s:
        for y, z in M.HOLES:
            s.circle((2.5, y, z), M.HOLE_R)
    extrude(d, s.feat, 'SCREW_HOLES', 5.0, cut=True, mode=MID, expect_dv=M.v_holes)
    with Sk(d, plane(d, 'X', 35.0, 'ARM_P'), 'ARM') as s:
        s.rect((35.0, 15, 40), (35.0, 25, 52))
    extrude(d, s.feat, 'ARM', 60.0, mode=MID, expect_dv=M.v_arm)
    # the mouth of the upper screw hole is also an edge at X 5 inside this box (the arm covers it): keep the outline only
    root = edges_where(d, lambda p: abs(p[0] - 5) < 0.01 and 14.99 < p[1] < 25.01 and 39.99 < p[2] < 52.01
                       and min(abs(p[1] - 15), abs(p[1] - 25), abs(p[2] - 40), abs(p[2] - 52)) < 0.01)
    expect('root edges, all round', len(root), 4, 0)
    v0 = volume(d)
    if fillet(d, root, (3.0,), 'ROOT_R3_ALL') != 3.0:
        raise Failed('all-round fillet did not build')
    dv = volume(d) - v0
    hand = (1 - math.pi / 4) * 9 * (2 * 10 + 2 * 12)        # four straight runs; the corner blends add a little
    log(f'all-round fillet added {dv:.2f} mm3 (straight runs alone {hand:.2f})')
    if not hand < dv < 1.5 * hand:
        raise Failed('fillet volume implausible')
    M.split_face(d, 'LOAD_PATCH', plane(d, 'Z', 52.0, 'PATCH_P'), (55.0, 14, 52), (55.0, 26, 52), (40, 20, 52))
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    save(d)
    V = volume(d)
    for support in ('wall', 'holes'):
        for el in (2.5, 1.75, 1.25):
            def c(d, el=el):
                fl = [f for f in faces(d) if face_info(f)['kind'] != 'plane' and 4.9 < face_info(f)['box'][0] and face_info(f)['box'][3] < 8.1]
                log('fillet faces for control', len(fl))
                return [(fl, round(0.3 * el, 3))]
            tag = f'B2R_{support}_{str(el).replace(".", "p")}'
            r = solve(j, d, tag, support, el, c, dict(nodes='as b2_study at the same size', disp='1.51 wall / 1.88 holes',
                                                      peak='vm ~19 in the upper fillet; layer measures (Y) no longer on an edge'))
            ck = checks(r, tag=tag)
            m = measures(r)
            rows.append(dict(tag=tag, support=support, el=el, nodes=r.nodes, checks=ck, measures=m, factors_Y=factors(m, 'Y')))
            log(tag, json.dumps(m), 'factors Y', factors(m, 'Y'))
            put('b2_variant', dict(volume_mm3=V, mass_g=V * DENS, sha256=sha(P), rows=rows))
    close(j.sw, d)
print('B2 VARIANT DONE')
