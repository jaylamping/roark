"""C2: the organic forearm link. python c2_build.py ideas | final
Frame X, Y, Z in mm; joint axes along Y; elbow at the origin, wrist pin at Z -200."""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
from swkit import *          # noqa: E402,F403

OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'fable-c'
HERE = Path(__file__).resolve().parent

# fixed by TASKS_C.md
R_DISC, T_DISC, R_BORE, R_BOLT, R_PCD = 35.0, 8.0, 15.0, 1.7, 25.0
Z_PIN, R_PIN, Y_CHEEK, Z_SLOT = -200.0, 4.0, 16.0, -183.0
R_CABLE = 3.0
# mine
R_RIM = 3.5                      # bullnose on the disc rim; leaves the mounting ring flat to r 31.5 (needs 31)
NPTS = 48
LAST = {}
BY_ANGLE = True

# idea A, "bone": one shaft whose section changes all the way. Columns: z, a (half width in X), b+ (half depth to +Y),
# b- (to -Y), n (superellipse exponent: 2 is an ellipse, 5 nearly a rounded rectangle)
BONE = [(-25, 24.8, 3.9, 3.7, 2.2), (-32, 19.8, 8.6, 3.95, 2.2), (-40, 16.8, 11.0, 8.0, 2.2),
        (-50, 15.0, 12.6, 10.6, 2.2), (-65, 14.0, 13.0, 12.0, 2.2), (-85, 13.2, 12.8, 12.4, 2.2),
        (-110, 12.8, 12.4, 12.2, 2.3), (-135, 12.8, 12.4, 12.4, 2.6), (-155, 13.2, 13.8, 13.8, 3.2),
        (-170, 13.7, 17.5, 17.5, 4.0), (-182, 14.2, 21.3, 21.3, 4.6), (-192, 14.5, 23.0, 23.0, 5.0),
        (-200, 14.5, 23.0, 23.0, 5.0)]
# round 2, after the first study (+Y case failed at the neck, where the cable mouth cut the thickest fibres): a deeper
# and wider neck, a slight waist, and the cable leaves through the back of the shaft lower down
BONE2 = [(-25, 24.8, 3.9, 3.7, 2.2), (-32, 21.5, 10.4, 3.95, 2.2), (-40, 18.0, 12.6, 8.4, 2.2),
         (-50, 15.6, 13.2, 11.0, 2.2), (-65, 14.2, 13.2, 12.2, 2.2), (-85, 13.0, 12.6, 12.0, 2.2),
         (-110, 12.2, 11.8, 11.6, 2.3), (-135, 12.2, 11.9, 11.9, 2.6), (-155, 12.9, 13.6, 13.6, 3.2)] + BONE[9:]
TUNNEL1 = ((0, 7.6, -20.0), (0, -0.35, -185.0))       # round 1: mouth in the neck. Dropped.
TUNNEL = ((0, 17.0, -45.0), (0, -7.4, -186.0))        # cable passage axis: out of the +Y face under the disc, into the crotch


def section(z, a, bp, bm, n, yc=0.0, t0=0.0, t1=360.0, npts=NPTS, scale=1.0):
    """npts points of a superellipse at height z, evenly spaced along the curve, starting on +X."""
    t = np.radians(np.linspace(t0, t1, 4001))
    c, s = np.cos(t), np.sin(t)
    x = a * np.sign(c) * np.abs(c) ** (2 / n)
    y = np.where(s >= 0, bp, bm) * np.sign(s) * np.abs(s) ** (2 / n)
    L_ = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    closed = (t1 - t0) >= 360
    if BY_ANGLE:            # even in angle: points crowd at the tips of a thin lens, where an even spacing makes the spline loop
        i = np.linspace(0, 4000, npts + 1)[:-1].astype(int) if closed else np.linspace(0, 4000, npts).astype(int)
        return [(float(x[k]) * scale, float(y[k]) * scale + yc, z) for k in i]
    want = np.linspace(0, L_[-1], npts + 1)[:-1] if closed else np.linspace(0, L_[-1], npts)
    return [(float(np.interp(w, L_, x)) * scale, float(np.interp(w, L_, y)) * scale + yc, z) for w in want]


def halves(z, a, bp, bm, n, yc=0.0, npts=25):
    """The section as two open curves, +Y half and -Y half, sharing their end points on the X axis."""
    out = []
    for t0, t1, b in ((0.0, 180.0, bp), (180.0, 360.0, bm)):
        t = np.radians(np.linspace(t0, t1, npts))
        c, s = np.cos(t), np.sin(t)
        pts = [(float(a * np.sign(ci) * abs(ci) ** (2 / n)), float(b * np.sign(si) * abs(si) ** (2 / n)) + yc, z)
               for ci, si in zip(c, s)]
        pts[0] = ((a if t0 == 0 else -a), yc, z)
        pts[-1] = ((-a if t0 == 0 else a), yc, z)
        out.append(pts)
    return out


def loft_of(d, rows, name, yc=lambda z: 0.0):
    sk = []
    for k, (z, a, bp, bm, n) in enumerate(rows):
        with Sk(d, plane(d, 'Z', z, f'{name}_P{k}'), f'{name}_S{k}') as s:
            for half in halves(z, a, bp, bm, n, yc(z)):
                s.spline(half, closed=False)
        sk.append(s.feat)
    return loft(d, sk, name)


def disc(d, rim):
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), R_DISC)
    extrude(d, s.feat, 'DISC', T_DISC, mode=MID, expect_dv=math.pi * R_DISC ** 2 * T_DISC)
    if rim:
        e = edges_where(d, lambda p: abs(math.hypot(p[0], p[2]) - R_DISC) < 0.01)
        log('rim edges', len(e))
        if fillet(d, e, (R_RIM,), 'RIM') is None:
            raise Failed('rim round did not build')


def holes(d):
    v0 = volume(d)
    with Sk(d, plane(d, 'Y', 0, 'X'), 'ELBOW_HOLES') as s:
        s.circle((0, 0, 0), R_BORE)
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((R_PCD * math.cos(a), 0, R_PCD * math.sin(a)), R_BOLT)
    extrude(d, s.feat, 'ELBOW_HOLES', 40.0, cut=True, mode=MID)
    with Sk(d, plane(d, 'Y', 0, 'X'), 'PIN_HOLE') as s:
        s.circle((0, 0, Z_PIN), R_PIN)
    extrude(d, s.feat, 'PIN_HOLE', 60.0, cut=True, mode=MID)
    log('holes removed', round(v0 - volume(d), 1))


def bone(d, detail, neck=False, rows=None, tunnel=None):
    rows = rows or BONE
    disc(d, rim=detail)
    loft_of(d, rows, 'SHAFT')
    save(d)
    # the cheek ends: the last section turned about the pin axis, so the end is round from the side and matches the shaft
    z, a, bp, bm, n = rows[-1]
    half = section(z, a, bp, bm, n, t0=-90, t1=90, npts=25, scale=1.004)
    half[0], half[-1] = (0.0, half[0][1], z), (0.0, half[-1][1], z)
    with Sk(d, plane(d, 'Z', z, 'END_P'), 'END') as s:
        s.spline(half, closed=False)
        s.poly([half[-1], half[0]], closed=False)
        s.centerline((0, -40, z), (0, 40, z))
    revolve(d, s.feat, 'END', min_dv=1000)
    save(d)
    # the slot between the cheeks, with an arched root above Z -183
    arch = [(0.0, Y_CHEEK * math.cos(t), Z_SLOT + 7.0 * math.sin(t)) for t in np.linspace(0, math.pi, 17)]
    arch[0], arch[-1] = (0.0, Y_CHEEK, Z_SLOT), (0.0, -Y_CHEEK, Z_SLOT)
    with Sk(d, plane(d, 'X', 0, 'X'), 'SLOT') as s:
        s.spline(arch, closed=False)
        s.poly([arch[-1], (0, -Y_CHEEK, -235.0), (0, Y_CHEEK, -235.0), arch[0]], closed=False)
    extrude(d, s.feat, 'SLOT', 80.0, cut=True, mode=MID, min_dv=5000)
    holes(d)
    save(d)
    if not detail:
        return None
    # the cable passage: a straight round tunnel, drawn as a strip beside its axis and turned about it
    A, B = np.array((tunnel or TUNNEL)[0]), np.array((tunnel or TUNNEL)[1])
    u = (B - A) / np.linalg.norm(B - A)
    nrm = np.array([0.0, -u[2], u[1]]) * R_CABLE
    with Sk(d, plane(d, 'X', 0, 'X'), 'CABLE') as s:
        s.poly([tuple(A), tuple(B), tuple(B + nrm), tuple(A + nrm)])
        s.centerline(tuple(A), tuple(B))
    revolve(d, s.feat, 'CABLE', cut=True, min_dv=500)
    save(d)
    if neck:
        # blend the creases where the shaft comes out of the disc: every edge between Z -45 and -16 that is not a hole,
        # the cable mouth, the rim round's own tangent lines or the shaft's two seam lines
        bolt = [(R_PCD * math.cos(math.radians(60 * k)), R_PCD * math.sin(math.radians(60 * k))) for k in range(6)]

        def neck_edge(p):
            r = math.hypot(p[0], p[2])
            if not -45 < p[2] < -16:
                return False
            if min(math.hypot(p[0] - bx, p[2] - bz) for bx, bz in bolt) < 2.0:
                return False
            if abs(p[0]) < 3.3 and p[1] > 3.5:
                return False
            if abs(r - (R_DISC - R_RIM)) < 0.03 and abs(abs(p[1]) - T_DISC / 2) < 0.03:
                return False
            if abs(r - R_DISC) < 0.03 and abs(p[1]) < T_DISC / 2 - R_RIM + 0.03:
                return False
            if abs(p[1]) < 0.05 and r > R_DISC:
                return False
            return True
        # the window applies to the whole edge, the exclusions to its middle only: a crease ends ON the rim round's
        # tangent line, so testing its end points against that line threw every crease out (round 2 found 1 edge)
        e = []
        for b_ in solid_bodies(d):
            for x in (call(b_, 'GetEdges') or []):
                cp = x.GetCurveParams3
                mid = np.array(list(x.GetCurve.Evaluate2((cp.UMinValue + cp.UMaxValue) / 2, 0))[:3]) * 1e3
                ends = [np.array(cp.StartPoint[:3]) * 1e3, np.array(cp.EndPoint[:3]) * 1e3]
                if all(-45 < q[2] < -16 for q in ends + [mid]) and neck_edge(mid):
                    e.append(x)
        log('neck edges', len(e))
        rn = fillet(d, e, (3.0, 2.0, 1.2), 'NECK_BLEND') if e else None
        log('neck blend', rn)
        LAST['neck_blend'] = rn
        save(d)

    # soften the edges the slot leaves on the skin
    def slot_edge(p):
        return (p[2] < -168 and abs(p[1]) <= Y_CHEEK + 0.01 and math.hypot(p[0], p[2] - Z_PIN) > R_PIN + 0.5
                and math.hypot(p[0], p[1] + 6.0) > 3.8)
    e = edges_where(d, slot_edge)
    keep = []
    for x in e:                                   # drop the two tangent lines where the arch meets the cheek faces
        cp = x.GetCurveParams3
        a_, b_ = np.array(cp.StartPoint[:3]) * 1e3, np.array(cp.EndPoint[:3]) * 1e3
        if abs(a_[2] - Z_SLOT) < 0.01 and abs(b_[2] - Z_SLOT) < 0.01 and abs(a_[1] - b_[1]) < 0.01:
            continue
        keep.append(x)
    log('slot edges', len(e), 'kept', len(keep))
    r = fillet(d, keep, (1.5, 1.0, 0.6), 'SLOT_EDGES') if keep else None
    log('slot edge round', r)
    save(d)
    return r


def wishbone(d):
    """Idea B: two blades that leave the disc together and part, one to each cheek, open between. Crude: the V is
    drawn in the side view and extruded across X (the blade lofts failed, thin lens sections)."""
    disc(d, rim=False)
    yz = [(4, -28), (23, -185), (23, -200), (16, -200), (16, -186), (0, -62), (-16, -186), (-16, -200), (-23, -200),
          (-23, -185), (-4, -28)]
    with Sk(d, plane(d, 'X', 0, 'X'), 'VEE') as s:
        s.poly([(0.0, y, z) for y, z in yz])
    extrude(d, s.feat, 'VEE', 26.0, mode=MID)
    for sign in (1, -1):
        with Sk(d, plane(d, 'Y', sign * 19.5, f'EYE_P{sign}'), f'EYE{sign}') as s:
            s.circle((0, sign * 19.5, Z_PIN), 13.0)
        extrude(d, s.feat, f'EYE{sign}', 7.0, mode=MID)
    holes(d)
    save(d)


def finish(j, d, stem):
    single_body(d)
    errs = feature_errors(d)
    log('feature errors', errs)
    save(d)
    export(j.sw, d, OUT / f'{stem}.stl')
    r = dict(volume_mm3=round(volume(d), 1), mass_g=round(volume(d) * 1.19e-3, 1), bodies=len(bodies(d)),
             bbox=[round(v, 2) for v in bbox(d)], feature_errors=errs)
    log(stem, r)
    return r


if __name__ == '__main__':
    what = sys.argv[1]
    jobs = {'ideas': [('idea_b', wishbone), ('idea_a', lambda d: bone(d, False))],
            'idea_b': [('idea_b', wishbone)],
            'final': [('link_organic', lambda d: bone(d, True))],
            'all': [('idea_b', wishbone), ('idea_a', lambda d: bone(d, False)), ('link_organic', lambda d: bone(d, True))]}[what]
    out = {}
    with job() as j:
        for stem, fn in jobs:
            try:
                d = new_part(j.sw, OUT / f'{stem}.SLDPRT')
                extra = fn(d)
                out[stem] = finish(j, d, stem)
                out[stem]['slot_edge_round'] = extra
                if stem == 'link_organic':
                    export(j.sw, d, OUT / 'link_organic.step')
                close(j.sw, d)
            except Failed as ex:
                log('FAILED', stem, ex)
                out[stem] = dict(failed=str(ex))
    (HERE / f'c2_{what}.json').write_text(json.dumps(out, indent=1))
