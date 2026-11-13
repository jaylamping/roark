"""D2: split housing round a 6808-2RS outer ring. One job: build upper, lower, ring, pins, pads, the pair; measure; export.

Frame: bearing axis Z through the origin, split plane Y 0 (the halves' faces stand GAP/2 off it), X across.
What I built differently from the specification is in SPEC_BUILT and is explained in REPORT.md.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
from swkit import *   # noqa

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d2")
GAP = 0.6                      # split gap, total: each face stands 0.3 off the plane Y 0
H = GAP / 2
SEAT_R, OPEN_R = 26.0, 23.0    # seat Ø52; shoulder opening Ø46 (spec said Ø43.5: the inner ring is Ø44.0)
SEAT_W = 7.4                   # seat Z 0 to 7.4 (spec Z 0 to 7: the ring is 7.0 and a printer holds +-0.15)
Z0, Z1 = -4.0, 11.0
XS = 30.0                      # screw X (spec +-28.2: 0.5 mm of wall to the seat)
SCREW_Z = (1.0, 6.0)
INS_DEPTH = 7.0                # insert hole depth (spec 6: an M3 x 35 screw tip is 6.2 below the face)
RING = (24.0, 26.0, 0.2, 7.2)  # ring inner r, outer r, z0, z1
PAD_R, PAD_RAD = 1.2, 25.0     # soft pads on the ring top face, between ring and shoulder
GATHER = {}


def seg_area(r, y0):
    """Area of the circle segment on the side y >= y0 (y0 >= 0)."""
    return r * r * math.acos(y0 / r) - y0 * math.sqrt(r * r - y0 * y0)


def housing(j, name, sign):
    """sign +1 upper (Y > H), -1 lower. Last feature is named so that the body is housing_<name>-<LAST>."""
    d = new_part(j.sw, OUT / f'housing_{name}.SLDPRT')
    y_lo, y_hi = (H, 32.0) if sign > 0 else (-32.0, -H)
    ymid, thick = sign * (H + 32.0) / 2, 32.0 - H
    with Sk(d, plane(d, 'Y', ymid, 'BLOCK_P'), 'BLOCK') as s:
        s.rect((-36, ymid, Z0), (36, ymid, Z1))
    extrude(d, s.feat, 'BLOCK', thick, mode=MID, expect_dv=72 * 15 * thick)
    zm = (Z0 + Z1) / 2
    seg = seg_area(SEAT_R, H)
    with Sk(d, plane(d, 'Z', SEAT_W / 2, 'SEAT_P'), 'SEAT') as s:
        s.circle((0, 0, SEAT_W / 2), SEAT_R)
    extrude(d, s.feat, 'SEAT', SEAT_W, cut=True, mode=MID, expect_dv=seg * SEAT_W)
    with Sk(d, plane(d, 'Z', zm, 'OPEN_P'), 'OPENING') as s:
        s.circle((0, 0, zm), OPEN_R)
    extrude(d, s.feat, 'OPENING', 20.0, cut=True, mode=MID, expect_dv=seg_area(OPEN_R, H) * (SEAT_W * 0 + (Z1 - Z0 - SEAT_W)))
    if sign > 0:
        with Sk(d, plane(d, 'Y', ymid, 'CLR_P'), 'CLEAR') as s:
            for sx in (-1, 1):
                for z in SCREW_Z:
                    s.circle((sx * XS, ymid, z), 1.7)
        extrude(d, s.feat, 'CLEAR', 40.0, cut=True, mode=MID, expect_dv=4 * math.pi * 1.7 ** 2 * thick)
        k = 0
        for sx in (-1, 1):
            for z in SCREW_Z:
                k += 1
                nm = 'CBORE' if k == 4 else f'CB{k}'
                with Sk(d, plane(d, 'X', sx * XS, nm + '_PL'), nm) as s:
                    s.poly([(sx * XS, 28.5, z), (sx * XS, 28.5, z + 3.0), (sx * XS, 33.0, z + 3.0), (sx * XS, 33.0, z)])
                    s.centerline((sx * XS, 28.5, z), (sx * XS, 33.0, z))
                # the two Ø6 counterbores of a column are 5 mm apart and overlap: the second removes the lens (2.25 mm2 x 3.5) less
                lens = 2 * 9 * math.acos(5 / 6) - 2.5 * math.sqrt(36 - 25)
                revolve(d, s.feat, nm, cut=True, expect_dv=math.pi * (9 - 1.7 ** 2) * 3.5 - (lens * 3.5 if z == SCREW_Z[1] else 0.0))
    else:
        yi = -H - INS_DEPTH / 2
        with Sk(d, plane(d, 'Y', yi, 'INS_P'), 'INSERT') as s:
            for sx in (-1, 1):
                for z in SCREW_Z:
                    s.circle((sx * XS, yi, z), 2.0)
        extrude(d, s.feat, 'INSERT', INS_DEPTH, cut=True, mode=MID, expect_dv=4 * math.pi * 4 * INS_DEPTH)
        ym = -32.0 + 4.0
        with Sk(d, plane(d, 'Y', ym, 'M4_P'), 'M4HOLES') as s:
            for sx in (-1, 1):
                s.circle((sx * 24.0, ym, 3.5), 2.8)
        extrude(d, s.feat, 'M4HOLES', 8.0, cut=True, mode=MID, expect_dv=2 * math.pi * 2.8 ** 2 * 8.0)
    single_body(d)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    save(d)
    return d


def ring(j):
    d = new_part(j.sw, OUT / 'ring.SLDPRT')
    with Sk(d, plane(d, 'Y', 0.0, 'RING_P'), 'RING') as s:
        s.rect((RING[0], 0, RING[2]), (RING[1], 0, RING[3]))
        s.centerline((0, 0, 0), (0, 0, 10))
    revolve(d, s.feat, 'RING', expect_dv=math.pi * (RING[1] ** 2 - RING[0] ** 2) * (RING[3] - RING[2]))
    save(d)
    return d


def pin(j, k, xc, zc):
    d = new_part(j.sw, OUT / f'pin_{k}.SLDPRT')
    prof = [(-6.0, 0.0), (-6.0, 2.0), (-0.3, 2.0), (-0.3, 1.5), (28.5, 1.5), (28.5, 2.75), (31.5, 2.75), (31.5, 0.0)]
    with Sk(d, plane(d, 'X', xc, 'PIN_P'), 'PIN') as s:
        s.poly([(xc, y, zc + r) for y, r in prof])
        s.centerline((xc, -6.0, zc), (xc, 31.5, zc))
    dv = math.pi * (4 * 5.7 + 2.25 * 28.8 + 2.75 ** 2 * 3.0)
    revolve(d, s.feat, f'PIN{k}', expect_dv=dv)
    save(d)
    return d


def pad(j, k, ang):
    d = new_part(j.sw, OUT / f'pad_{k}.SLDPRT')
    x, y = PAD_RAD * math.cos(math.radians(ang)), PAD_RAD * math.sin(math.radians(ang))
    zc = (RING[3] + SEAT_W) / 2
    with Sk(d, plane(d, 'Z', zc, 'PAD_P'), f'PAD{k}') as s:
        s.circle((x, y, zc), PAD_R)
    extrude(d, s.feat, f'PAD{k}', SEAT_W - RING[3], mode=MID, min_dv=0.1, expect_dv=math.pi * PAD_R ** 2 * (SEAT_W - RING[3]))
    save(d)
    return d


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    with job() as j:
        for name, sign in (('upper', +1), ('lower', -1)):
            d = housing(j, name, sign)
            b = bbox(d)
            log(name, 'volume', round(volume(d), 1), 'box', [round(v, 3) for v in b])
            export(j.sw, d, OUT / f'housing_{name}.stl')
            close(j.sw, d)
        d = ring(j)
        export(j.sw, d, OUT / 'ring.stl')
        close(j.sw, d)
        k = 0
        for sx in (-1, 1):
            for z in SCREW_Z:
                k += 1
                d = pin(j, k, sx * XS, z)
                close(j.sw, d)
        for k, ang in enumerate((45, 135, 225, 315), 1):
            d = pad(j, k, ang)
            close(j.sw, d)
        # the pair, as one part with every body in place (for the study and the picture)
        d = new_part(j.sw, OUT / 'housing_pair.SLDPRT')
        for f in ('housing_upper', 'housing_lower', 'ring', 'pin_1', 'pin_2', 'pin_3', 'pin_4', 'pad_1', 'pad_2', 'pad_3', 'pad_4'):
            insert_body(d, OUT / f'{f}.SLDPRT')
        log('bodies', [(b[0], b[1]) for b in bodies(d)])
        save(d)
        log('pair box', [round(v, 3) for v in bbox(d)], 'bodies', len(bodies(d)), 'errors', feature_errors(d))
        close(j.sw, d)
    print('BUILD DONE')
