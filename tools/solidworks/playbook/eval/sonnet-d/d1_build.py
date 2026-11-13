"""D1: buck_mount. One job: build, measure, export. Board tilted TH degrees about X (see restate.md for why).

Frame: X along the rail, Y left, Z up, mm, rail top face at Z 0. Board centre (0, Y0, ZC); board axes: u = (0, cos, sin)
across the 60 side, n = (0, -sin, cos) the board normal (components side). Board bottom face is n = 0.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
from swkit import *   # noqa

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d1")
TH = 41.0
C, S = math.cos(math.radians(TH)), math.sin(math.radians(TH))
Y0, ZC = -0.5, 22.8
HX, HU = 39.0, 26.5            # hole positions: X = +-39, u = +-26.5 from the board centre
H_SO, R_SO, R_PILOT = 4.0, 3.5, 1.35
RIB_T = 7.0
BASE_X, BASE_W, BASE_T = 58.0, 20.0, 5.0
M5_X = 52.0


def bp(u, n):
    """(Y, Z) of board-frame point (u, n)."""
    return (Y0 + u * C - n * S, ZC + u * S + n * C)


def shoelace(p):
    return abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))) / 2


def build(j):
    d = new_part(j.sw, OUT / 'buck_mount.SLDPRT')
    # base plate on the rail top
    with Sk(d, plane(d, 'Z', BASE_T / 2, 'BASE_P'), 'BASE') as s:
        s.rect((-BASE_X, -BASE_W / 2, BASE_T / 2), (BASE_X, BASE_W / 2, BASE_T / 2))
    extrude(d, s.feat, 'BASE', BASE_T, mode=MID, expect_dv=2 * BASE_X * BASE_W * BASE_T)
    # key tongue into the T-slot (slot is 6 wide: 5.4 gives 0.3 each side)
    with Sk(d, plane(d, 'Z', -1.25, 'KEY_P'), 'KEY') as s:
        s.rect((-25, -2.7, -1.25), (25, 2.7, -1.25))
    extrude(d, s.feat, 'KEY', 2.5, mode=MID, expect_dv=50 * 5.4 * 2.5)
    # two ribs: polygon in the plane X = +-HX, under the line n = -H_SO of the board
    yd, zd = bp(-29.5, -H_SO)
    yc, zc_ = bp(29.5, -H_SO)
    poly = [(yd, 0.0), (10.0, 0.0), (yc + 0.5, zc_), (yc, zc_), (yd, zd)]
    # the low end is cut off at Y -17: left of that the rib would be a 0.4 mm lip under the standoff overhang
    ya_ = -17.0
    za_ = zd + (ya_ - yd) * (zc_ - zd) / (yc - yd)
    poly = [(ya_, 0.0), (10.0, 0.0), (yc, zc_), (ya_, za_)]
    area = shoelace(poly)
    log('rib polygon (Y,Z)', [(round(a, 2), round(b, 2)) for a, b in poly], 'area', round(area, 1))
    for sx, nm in ((+1, 'RIB_P'), (-1, 'RIB_M')):
        with Sk(d, plane(d, 'X', sx * HX, nm + '_PL'), nm) as s:
            s.poly([(sx * HX, y, z) for y, z in poly])
        v0 = volume(d)
        extrude(d, s.feat, nm, RIB_T, mode=MID)          # overlaps the base over Y -10..10, Z 0..5 on the base's X range? no: X differs
        log(nm, 'added', round(volume(d) - v0, 1), 'hand', round(area * RIB_T, 1))
    # standoffs: revolve a profile about the hole axis (along n), n = -H_SO .. 0
    for sx in (+1, -1):
        for su in (+1, -1):
            u = su * HU
            nm = f"SO_{'P' if sx > 0 else 'M'}{'H' if su > 0 else 'L'}"
            ya, za = bp(u, -H_SO)
            yb, zb = bp(u, 0.0)
            yc2, zc2 = bp(u + R_SO, -H_SO)
            yd2, zd2 = bp(u + R_SO, 0.0)
            with Sk(d, plane(d, 'X', sx * HX, nm + '_PL'), nm) as s:
                s.poly([(sx * HX, ya, za), (sx * HX, yc2, zc2), (sx * HX, yd2, zd2), (sx * HX, yb, zb)])
                s.centerline((sx * HX, ya, za), (sx * HX, yb, zb))
            revolve(d, s.feat, nm, expect_dv=math.pi * R_SO ** 2 * H_SO)
    save(d)
    # pilot holes for M3 thread-forming screws, depth H_SO from the board bottom face (floor on the rib)
    for sx in (+1, -1):
        for su in (+1, -1):
            u = su * HU
            nm = f"PILOT_{'P' if sx > 0 else 'M'}{'H' if su > 0 else 'L'}"
            ya, za = bp(u, -H_SO)
            yb, zb = bp(u, 0.5)
            yc2, zc2 = bp(u + R_PILOT, -H_SO)
            yd2, zd2 = bp(u + R_PILOT, 0.5)
            with Sk(d, plane(d, 'X', sx * HX, nm + '_PL'), nm) as s:
                s.poly([(sx * HX, ya, za), (sx * HX, yc2, zc2), (sx * HX, yd2, zd2), (sx * HX, yb, zb)])
                s.centerline((sx * HX, ya, za), (sx * HX, yb, zb))
            revolve(d, s.feat, nm, cut=True, expect_dv=math.pi * R_PILOT ** 2 * H_SO)
    # M5 clearance holes through the base, at both ends outside the board
    with Sk(d, plane(d, 'Z', BASE_T / 2, 'M5_P'), 'M5') as s:
        for sx in (+1, -1):
            s.circle((sx * M5_X, 0, BASE_T / 2), 2.75)
    extrude(d, s.feat, 'M5', BASE_T + 1, cut=True, mode=MID, expect_dv=2 * math.pi * 2.75 ** 2 * BASE_T)
    # zip-tie slots for the wire pairs, +X end
    with Sk(d, plane(d, 'Z', BASE_T / 2, 'ZIP_P'), 'ZIP') as s:
        for y0_, y1_ in ((-9.0, -4.5), (4.5, 9.0)):
            s.rect((43.5, y0_, BASE_T / 2), (46.5, y1_, BASE_T / 2))
    extrude(d, s.feat, 'ZIP', BASE_T + 1, cut=True, mode=MID, expect_dv=2 * 3.0 * 4.5 * BASE_T)
    save(d)
    # envelope: nothing beyond Y +-25 (clip at 24.9) and nothing above Z 45
    v1 = volume(d)
    b = bbox(d)
    log('box before clip', [round(v, 2) for v in b])
    if b[4] > 24.9:
        cut_half_space(d, 'Y', 24.9, -1, 'CLIP_YP')
    if b[1] < -24.9:
        cut_half_space(d, 'Y', -24.9, +1, 'CLIP_YM')
    if b[5] > 44.5:
        cut_half_space(d, 'Z', 44.5, -1, 'CLIP_Z')
    log('volume removed by the envelope clip mm3', round(v1 - volume(d), 2))
    save(d)
    return d


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    with job() as j:
        d = build(j)
        b = bbox(d)
        log('bbox', [round(v, 2) for v in b], 'volume', round(volume(d), 1), 'bodies', bodies(d))
        log('feature errors', feature_errors(d))
        single_body(d)
        log('mass g (PETG 1.19)', round(volume(d) * 1.19e-3, 2))
        save(d)
        for ext in ('step', 'stl'):
            export(j.sw, d, OUT / f'buck_mount.{ext}')
        close(j.sw, d)
    print('BUILD DONE')
