"""D2: split housing round a 6808-2RS. Builds both halves, the steel ring, the stand-ins the study needs (soft plug,
four screws) and the multi-body model pair_fea.SLDPRT. No study here: d2_fea.py.

Frame: bearing axis Z, split plane Y 0, upper half Y > 0, mounting face Y -32. mm.
"""
import json
import math

from common import HERE, WIP, stl_check
from swkit import (MID, Sk, bbox, bodies, close, expect, export, extrude, face_info, feature_errors, insert_body, job, log,
                   new_part, open_doc, pick, plane, revolve, save, save_as, single_body, volume)

# ---- the task's numbers ------------------------------------------------------------------------------------------------
EX, EY, Z0, Z1 = 36.0, 32.0, -4.0, 11.0          # envelope of the pair
BRG_OD, BRG_ID, BRG_W = 52.0, 40.0, 7.0          # 6808-2RS
INNER_RING_OD, OUTER_RING_ID = 44.0, 48.0        # task
CBORE_D, CBORE_DEPTH, CLEAR_D, INSERT_D = 6.0, 3.5, 3.4, 4.0
M4_D, M4_DEPTH, M4_X, M4_Z = 5.6, 8.0, 24.0, 3.5
TOL = 0.15                                       # the printer, on any one dimension

# ---- what I changed, and why (REPORT.md, "spec problems") --------------------------------------------------------------
SEAT_D = 52.15        # task 52.0: with +/-0.15 a 52.0 seat can print 51.85 and pinch at its edges; 52.15 is never under 52.0
AX_CLEAR = 0.1        # task: seat exactly 7 wide for a 7 wide bearing; the halves close across it, so it needs room
OPEN_D = 49.0         # task 43.5: that is inside the inner ring (44.0) and over the seal; 49 bears on the outer ring only
GAP0 = 0.8            # task: split exactly on Y 0; each split face stands back 0.4 so the seat closes before the faces do
SCREW_X = 31.0        # task 28.2: leaves 0.2 mm between a dia 4.0 insert hole and the seat
SCREW_Z = (0.0, 7.0)  # task 1 and 6: two dia 6 counterbores 5 apart overlap by 1 mm (and dia 5.5 heads collide)
INSERT_DEPTH = 8.0    # task 6: grip is 28.5, so M3x30 enters 1.5 and M3x35 needs 6.5; 8 deep takes an M3x35
SCREW_LEN = 35.0

RS, RO, G = SEAT_D / 2, OPEN_D / 2, GAP0 / 2
SCREWS = [(sx * SCREW_X, z) for sx in (1, -1) for z in SCREW_Z]
ZC, TH = (Z0 + Z1) / 2, Z1 - Z0


def seg(r, d):
    """Area of the part of a circle of radius r beyond a chord at distance d from its centre."""
    return r * r * math.acos(d / r) - d * math.sqrt(r * r - d * d)


HAND = dict(block=2 * EX * (EY - G) * TH, opening=-seg(RO, G) * TH, seat=-(seg(RS, G) - seg(RO, G)) * (BRG_W + 2 * AX_CLEAR))
HAND_UP = dict(HAND, clear=-4 * math.pi * (CLEAR_D / 2) ** 2 * (EY - G),
               cbore=-4 * math.pi * ((CBORE_D / 2) ** 2 - (CLEAR_D / 2) ** 2) * CBORE_DEPTH)
HAND_LO = dict(HAND, inserts=-4 * math.pi * (INSERT_D / 2) ** 2 * INSERT_DEPTH, m4=-2 * math.pi * (M4_D / 2) ** 2 * M4_DEPTH)


def ycyl(d, name, centres, r, y0, y1, cut=True, expect_dv=None):
    """Cylinders along Y, centres (x, z), from y0 to y1."""
    yc = (y0 + y1) / 2
    with Sk(d, plane(d, 'Y', yc, name + '_P'), name) as s:
        for x, z in centres:
            s.circle((x, yc, z), r)
    return extrude(d, s.feat, name, abs(y1 - y0), cut=cut, mode=MID, expect_dv=expect_dv)


def zdisc(d, name, r, z0, z1, cut=True, expect_dv=None, r_in=None):
    zc = (z0 + z1) / 2
    with Sk(d, plane(d, 'Z', zc, name + '_P'), name) as s:
        s.circle((0, 0, zc), r)
        if r_in:
            s.circle((0, 0, zc), r_in)
    return extrude(d, s.feat, name, z1 - z0, cut=cut, mode=MID, expect_dv=expect_dv)


def holes_along_y(d, r, **kw):
    out = []
    for f in pick(d, kind='cyl', r=r, **kw):
        b = face_info(f)['box']
        out.append([round((b[0] + b[3]) / 2, 3), round((b[2] + b[5]) / 2, 3), round(2 * face_info(f)['r'], 3), round(b[1], 3), round(b[4], 3)])
    return sorted(out)


def half(j, upper):
    name = 'housing_upper' if upper else 'housing_lower'
    sgn = 1 if upper else -1
    hand = HAND_UP if upper else HAND_LO
    d = new_part(j.sw, WIP / f'{name}.SLDPRT')
    y0, y1 = sorted((sgn * G, sgn * EY))
    with Sk(d, plane(d, 'Z', ZC, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((-EX, y0, ZC), (EX, y1, ZC))
    extrude(d, s.feat, 'BLOCK', TH, mode=MID, expect_dv=hand['block'])
    zdisc(d, 'OPENING', RO, Z0, Z1, expect_dv=-hand['opening'])
    zdisc(d, 'SEAT', RS, -AX_CLEAR, BRG_W + AX_CLEAR, expect_dv=-hand['seat'])
    save(d)
    if upper:
        ycyl(d, 'CLEAR_HOLES', SCREWS, CLEAR_D / 2, G, EY, expect_dv=-hand['clear'])
        ycyl(d, 'CBORES', SCREWS, CBORE_D / 2, EY - CBORE_DEPTH, EY, expect_dv=-hand['cbore'])
    else:
        ycyl(d, 'INSERT_HOLES', SCREWS, INSERT_D / 2, -G - INSERT_DEPTH, -G, expect_dv=-hand['inserts'])
        ycyl(d, 'M4_HOLES', [(M4_X, M4_Z), (-M4_X, M4_Z)], M4_D / 2, -EY, -EY + M4_DEPTH, expect_dv=-hand['m4'])
    single_body(d)
    save(d)
    hv = sum(hand.values())
    expect(name + ' volume', volume(d), hv, 0.001)
    want = [-EX, y0, Z0, EX, y1, Z1]
    for k, w in enumerate(want):
        expect(f'{name} box[{k}]', bbox(d)[k], w, 0.01)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    # every dimension measured on the solid
    m = {}
    seat = [face_info(f) for f in pick(d, kind='cyl', r=RS)]
    opening = [face_info(f) for f in pick(d, kind='cyl', r=RO)]
    expect('seat faces', len(seat), 1, 0)
    expect('opening faces (one per shoulder)', len(opening), 2, 0)
    m['seat'] = dict(dia=round(2 * seat[0]['r'], 3), z=[round(seat[0]['box'][2], 3), round(seat[0]['box'][5], 3)],
                     y_crown=round(seat[0]['box'][4 if upper else 1], 3))
    m['opening'] = [dict(dia=round(2 * o['r'], 3), z=[round(o['box'][2], 3), round(o['box'][5], 3)]) for o in opening]
    split = [face_info(f) for f in pick(d, kind='plane', normal=(0, -sgn, 0), inside=[-EX - 1, sgn * G - 0.05, Z0 - 1, EX + 1, sgn * G + 0.05, Z1 + 1])]
    m['split_faces'] = dict(count=len(split), y=sgn * G, area_each=[round(f['area'], 2) for f in split])
    if upper:
        m['clear_holes'] = holes_along_y(d, CLEAR_D / 2)
        m['cbores'] = holes_along_y(d, CBORE_D / 2)
        expect('clearance hole faces', len(m['clear_holes']), 4, 0)
        expect('counterbore faces', len(m['cbores']), 4, 0)
        for h in m['clear_holes'] + m['cbores']:
            if min(math.dist(h[:2], c) for c in SCREWS) > 0.01:
                raise SystemExit(f'screw hole in the wrong place {h}')
    else:
        m['insert_holes'] = holes_along_y(d, INSERT_D / 2)
        m['m4_holes'] = holes_along_y(d, M4_D / 2)
        expect('insert hole faces', len(m['insert_holes']), 4, 0)
        expect('M4 hole faces', len(m['m4_holes']), 2, 0)
        for h in m['insert_holes']:
            if min(math.dist(h[:2], c) for c in SCREWS) > 0.01:
                raise SystemExit(f'insert hole in the wrong place {h}')
        for h in m['m4_holes']:
            if abs(abs(h[0]) - M4_X) > 0.01 or abs(h[1] - M4_Z) > 0.01:
                raise SystemExit(f'M4 hole in the wrong place {h}')
    log(name, 'measured', json.dumps(m))
    v, bx = volume(d), bbox(d)
    export(j.sw, d, WIP / f'{name}.stl')
    export(j.sw, d, WIP / f'{name}.step')
    save(d)
    close(j.sw, d)
    chk = stl_check(WIP / f'{name}.stl', v, bx)
    log(name, 'STL', chk)
    return dict(volume_mm3=round(v, 2), hand_volume_mm3=round(hv, 2), mass_g=round(v * 1.19e-3, 2), bbox=bx, measured=m, stl=chk)


def ring(j):
    d = new_part(j.sw, WIP / 'ring.SLDPRT')
    zdisc(d, 'OUTER_RACE', BRG_OD / 2, 0, BRG_W, cut=False, r_in=OUTER_RING_ID / 2,
          expect_dv=math.pi * ((BRG_OD / 2) ** 2 - (OUTER_RING_ID / 2) ** 2) * BRG_W)
    save(d)
    v, bx = volume(d), bbox(d)
    export(j.sw, d, WIP / 'ring.stl')
    close(j.sw, d)
    return dict(volume_mm3=round(v, 2), bbox=bx, stl=stl_check(WIP / 'ring.stl', v, bx))


def plug(j):
    """Soft disc bonded in the ring's bore, its dia 6 hub hole fixed: holds the ring while the contact is open."""
    d = new_part(j.sw, WIP / 'plug.SLDPRT')
    zdisc(d, 'SOFTPLUG', OUTER_RING_ID / 2, 2.5, 4.5, cut=False, r_in=3.0, expect_dv=math.pi * (24.0 ** 2 - 9.0) * 2.0)
    save(d)
    close(j.sw, d)


def screw(j, k, x, z):
    """Steel M3 stand-in: dia 5.5 x 3 head on the counterbore floor, dia 3.0 shank, dia 4.0 x 6 end standing for the
    thread in its insert (line to line in the dia 4.0 hole, so it bonds)."""
    d = new_part(j.sw, WIP / f'screw_{k}.SLDPRT')
    yh = EY - CBORE_DEPTH
    prof = [(x, -G - 6.0), (x + 2.0, -G - 6.0), (x + 2.0, -G), (x + 1.5, -G), (x + 1.5, yh), (x + 2.75, yh), (x + 2.75, yh + 3.0), (x, yh + 3.0)]
    with Sk(d, plane(d, 'Z', z, 'SCREW_P'), 'SCREW') as s:
        s.poly([(px, py, z) for px, py in prof])
        s.centerline((x, -G - 6.0, z), (x, yh + 3.0, z))
    revolve(d, s.feat, 'M3SCREW', expect_dv=math.pi * (4.0 * 6.0 + 2.25 * (yh + G) + 2.75 ** 2 * 3.0))
    save(d)
    close(j.sw, d)


def pair(j):
    d = open_doc(j.sw, WIP / 'housing_lower.SLDPRT')
    save_as(d, WIP / 'pair_fea.SLDPRT')
    for name in ['housing_upper', 'ring', 'plug'] + [f'screw_{k}' for k in range(4)]:
        insert_body(d, WIP / f'{name}.SLDPRT')
    save(d)
    bs = bodies(d)
    for b in bs:
        log('pair body', b)
    expect('bodies in the pair', len(bs), 8, 0)
    close(j.sw, d)
    return [dict(name=b[0], volume=b[1], box=b[2]) for b in bs]


if __name__ == '__main__':
    res = dict(changed=dict(SEAT_D=SEAT_D, AX_CLEAR=AX_CLEAR, OPEN_D=OPEN_D, GAP0=GAP0, SCREW_X=SCREW_X, SCREW_Z=SCREW_Z,
                            INSERT_DEPTH=INSERT_DEPTH))
    with job() as j:
        res['upper'] = half(j, True)
        res['lower'] = half(j, False)
        res['ring'] = ring(j)
        (HERE / 'd2_model.json').write_text(json.dumps(res, indent=1))
        plug(j)
        for k, (x, z) in enumerate(SCREWS):
            screw(j, k, x, z)
        res['pair_bodies'] = pair(j)
        (HERE / 'd2_model.json').write_text(json.dumps(res, indent=1))
    print('DONE d2_build', flush=True)
