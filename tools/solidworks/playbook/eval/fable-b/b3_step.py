"""B3: one lightening step. python b3_step.py <name> '<json parameters>' [sizes]

The light bracket is an open triangle printed on its side (layers along Y, the profile flat on the bed, no supports):
a wall strip with the two screw holes, a top chord in tension from the top of the strip to the load pad, and a strut in
compression from under the pad to the strip above the lower screw. The window between them leaves both screws
reachable with a driver along X, which the B2 arm did not (it covers the upper hole).

Profile in X-Z, mm. Parameters:
  tp    wall strip thickness (X 0..tp)            zp0, zp1  strip from Z zp0 to zp1 (chord top meets the strip top)
  dc    chord depth (vertical)                    ds        strut depth (perpendicular)
  zs    Z where the strut's lower edge meets the strip      ht   height of the tip block under the pad (X 61..65)
  wy    width of chord and strut along Y, from Y 15 (10 = full width); the strip and the pad stay Y 15..25
  tpad  pad thickness where the members are narrower        rf   fillet radius at the profile's inside corners
  rs    radius on the edges where a narrowed member's side meets the strip (0 = leave sharp)
  y0,y1 strip width along Y
  strap 1 = only the strut (and the tip block under the pad) is narrowed: chord and pad stay one full-width strap dc thick
  rp    radius on the two inside edges where the pad overhangs the narrowed members (0 = leave sharp)
  tw, wz0, wz1  waist: the strip is thinned to tw (X 0..tw) between Z wz0 and wz1, with 45 degree run-outs (tw 0 = no waist)
"""
import json
import math
import sys

import numpy as np

from common import DENS, HERE, WIP, cyl, sha
from swkit import *
from bracket_fea import ALLOW, F, checks, factors, mask, measures, solve

DEF = dict(tp=5.0, zp0=6.0, zp1=56.0, dc=3.0, ds=4.5, zs=16.5, ht=5.0, wy=10.0, tpad=2.5, rf=2.0, rs=1.5, y0=15.0, y1=25.0, tw=0.0, wz0=26.5, wz1=43.0, rp=0.0, strap=0)
XB, XPAD, XTIP, ZTOP = 61.0, 55.0, 65.0, 52.0
HOLE_R, HOLES = 2.25, ((20, 12), (20, 48))
E = 1900.0


def geometry(p):
    tp = p['tp']
    A, B = (tp, p['zs']), (XB, ZTOP - p['ht'])
    ms = (B[1] - A[1]) / (B[0] - A[0])                     # strut slope
    cs = math.cos(math.atan(ms))
    mc = (ZTOP - p['zp1']) / (XPAD - tp)                   # chord slope (negative: it falls towards the tip)
    w1 = (tp, p['zp1'] - p['dc'])
    w2 = (tp, p['zs'] + p['ds'] / cs)
    u = (w1[1] - w2[1]) / (ms - mc)
    w3 = (tp + u, w2[1] + ms * u)
    outer = [(0, p['zp0']), (tp, p['zp0']), A, B, (XTIP, B[1]), (XTIP, ZTOP), (XPAD, ZTOP), (tp, p['zp1']), (0, p['zp1'])]
    return dict(A=A, B=B, ms=ms, cs=cs, mc=mc, w=[w1, w2, w3], outer=outer)


def area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def build(j, path, p):
    g = geometry(p)
    if not g['w'][2][0] < XB:
        raise Failed(f'window apex at X {g["w"][2][0]:.1f} is beyond the tip block')
    d = new_part(j.sw, path)
    with Sk(d, plane(d, 'Y', 20.0, 'PROFILE_P'), 'PROFILE') as s:
        s.poly([(x, 20.0, z) for x, z in g['outer']])
    extrude(d, s.feat, 'PROFILE', 10.0, mode=MID, expect_dv=area(g['outer']) * 10)
    with Sk(d, plane(d, 'Y', 20.0, 'WINDOW_P'), 'WINDOW') as s:
        s.poly([(x, 20.0, z) for x, z in g['w']])
    extrude(d, s.feat, 'WINDOW', 10.0, cut=True, mode=MID, expect_dv=area(g['w']) * 10)
    if p['y0'] < 15.0 or p['y1'] > 25.0:                   # a wider strip: add the wings
        zc = (p['zp0'] + p['zp1']) / 2
        with Sk(d, plane(d, 'Z', zc, 'STRIP_P'), 'STRIP') as s:
            s.rect((0, p['y0'], zc), (p['tp'], p['y1'], zc))
        extrude(d, s.feat, 'STRIP', p['zp1'] - p['zp0'], mode=MID,
                expect_dv=(p['y1'] - p['y0'] - 10) * p['tp'] * (p['zp1'] - p['zp0']))
    with Sk(d, plane(d, 'X', p['tp'] / 2, 'HOLES_P'), 'SCREW_HOLES') as s:
        for y, z in HOLES:
            s.circle((p['tp'] / 2, y, z), HOLE_R)
    extrude(d, s.feat, 'SCREW_HOLES', p['tp'], cut=True, mode=MID, expect_dv=2 * math.pi * HOLE_R ** 2 * p['tp'])
    save(d)
    corners = g['w'] + [g['A']]
    ed = edges_where(d, lambda q: any(math.hypot(q[0] - c[0], q[2] - c[1]) < 0.01 for c in corners))
    expect('inside corner edges', len(ed), 4, 0)
    got = fillet(d, ed, (p['rf'], 1.5, 1.0), 'CORNERS')
    if got is None:
        raise Failed('corner fillets did not build')
    if p['wy'] < 10.0:
        ys = 15.0 + p['wy']
        yc, dep = (ys + 25.0) / 2, 25.0 - ys
        tool = [(p['tp'], -1.0), (66.0, -1.0), (66.0, ZTOP - p['tpad']), (XPAD, ZTOP - p['tpad']), (XPAD, 60.0), (p['tp'], 60.0)]
        if p['strap']:
            tool = [(p['tp'], -1.0), (66.0, -1.0), (66.0, ZTOP - p['dc']), (XPAD, ZTOP - p['dc']), (p['tp'], p['zp1'] - p['dc'])]
        v0 = volume(d)
        with Sk(d, plane(d, 'Y', yc, 'NARROW_P'), 'NARROW') as s:
            s.poly([(x, yc, z) for x, z in tool])
        extrude(d, s.feat, 'NARROW', dep, cut=True, mode=MID)
        log(f'NARROW removed {v0 - volume(d):.1f} mm3')
        if p['rs'] > 0:
            ed = edges_where(d, lambda q: abs(q[0] - p['tp']) < 0.01 and abs(q[1] - ys) < 0.01)
            log('member-side to strip edges', len(ed))
            if ed:
                got_s = fillet(d, ed, (p['rs'], 1.0, 0.6), 'FOOT_SIDES')
                log('FOOT_SIDES radius', got_s)
    if p['wy'] < 10.0 and p['rp'] > 0:
        ys = 15.0 + p['wy']
        ed = edges_where(d, lambda q: abs(q[1] - ys) < 0.01 and q[0] > XPAD - 0.01 and q[2] > ZTOP - p['tpad'] - 0.01)
        if p['strap']:       # the edges where the strap's underside meets the side of the strut and tip block
            ed = edges_where(d, lambda q: abs(q[1] - ys) < 0.01 and q[0] > 45.0 and q[2] > ZTOP - p['dc'] - 0.3)
        for e_ in ed:
            cp = e_.GetCurveParams3
            log('pad inside edge', [round(v * 1e3, 2) for v in cp.StartPoint[:3]], [round(v * 1e3, 2) for v in cp.EndPoint[:3]])
        if not ed:
            raise Failed('no pad inside edges found')
        if fillet(d, ed, (p['rp'], 1.0, 0.6), 'PAD_EDGES') is None:
            if not p['strap']:
                raise Failed('pad edge radius did not build')
            log('PAD_EDGES: no radius built; the strap-to-strut edges stay sharp')
    if p['tw'] > 0:
        k = p['tp'] - p['tw']
        tool = [(p['tp'] + 0.5, p['wz0'] - 0.5), (p['tw'], p['wz0'] + k), (p['tw'], p['wz1'] - k), (p['tp'] + 0.5, p['wz1'] + 0.5)]
        with Sk(d, plane(d, 'Y', 20.0, 'WAIST_P'), 'WAIST') as s:
            s.poly([(x, 20.0, z) for x, z in tool])
        true = [(p['tp'], p['wz0']), (p['tw'], p['wz0'] + k), (p['tw'], p['wz1'] - k), (p['tp'], p['wz1'])]
        extrude(d, s.feat, 'WAIST', 10.0, cut=True, mode=MID, expect_dv=area(true) * (p['y1'] - p['y0']))
    single_body(d)
    errs = feature_errors(d)
    if errs:
        raise Failed(f'rebuild errors {errs}')
    save(d)
    return d, g, got


def verify(d, p):
    """The fixed things, measured on the solid: both holes, the wall face, the load patch."""
    hs = pick(d, kind='cyl', r=HOLE_R)
    expect('hole faces', len(hs), 2, 0)
    got = sorted((round(cyl(f)[0][1], 3), round(cyl(f)[0][2], 3), abs(round(cyl(f)[1][0], 3))) for f in hs)
    for g_, (y, z) in zip(got, HOLES):
        expect('hole y', g_[0], y, 0.001); expect('hole z', g_[1], z, 0.001); expect('hole along X', g_[2], 1, 0.001)
    wall = pick(d, kind='plane', normal=(-1, 0, 0), inside=[-0.01, -1e3, -1e3, 0.01, 1e3, 1e3])
    expect('wall face at X 0', len(wall), 1, 0)
    patch = pick(d, kind='plane', normal=(0, 0, 1), at=(60, 20, 52))
    expect('load patch', len(patch), 1, 0)
    i = face_info(patch[0])
    expect('patch area', i['area'], 100.0, 0.001)
    for k, want in zip((0, 1, 3, 4, 5), (55, 15, 65, 25, 52)):
        expect(f'patch box[{k}]', i['box'][k], want, 0.001)
    return dict(holes=got, patch_box=i['box'], wall_area=face_info(wall[0])['area'], bbox=bbox(d), bodies=len(bodies(d)))


def hand(p, g):
    """Member forces by a cut at X 30, and the strut's Euler load (pinned ends: the low bound)."""
    x = 30.0
    zc = p['zp1'] + g['mc'] * (x - p['tp']) - p['dc'] / 2
    zs_ = p['zs'] + g['ms'] * (x - p['tp']) + p['ds'] / g['cs'] / 2
    T = F * (60.0 - x) / (zc - zs_)                        # horizontal force in each member
    N = T / g['cs']                                        # along the strut
    L = math.hypot(g['w'][2][0] - p['tp'], g['w'][2][1] - g['w'][1][1])
    wy = p['wy']
    pin, pout = (math.pi ** 2 * E * I / L ** 2 for I in (wy * p['ds'] ** 3 / 12, p['ds'] * wy ** 3 / 12))
    return dict(chord_tension_n=round(T, 1), chord_stress_mpa=round(T / (p['dc'] * wy), 2), strut_force_n=round(N, 1),
                strut_stress_mpa=round(N / (p['ds'] * wy), 2), strut_len_mm=round(L, 1),
                euler_in_plane_n=round(pin), euler_out_of_plane_n=round(pout), buckling_factor_pinned=round(min(pin, pout) / N, 2),
                zc=zc)


if __name__ == '__main__':
    name = sys.argv[1]
    p = dict(DEF, **json.loads(sys.argv[2]))
    sizes = [float(v) for v in sys.argv[3].split(',')] if len(sys.argv) > 3 else [1.5]
    path = WIP / f'{name}.SLDPRT'
    rows = []
    with job() as j:
        j.simulation()
        d, g, rf = build(j, path, p)
        V = volume(d)
        fixed = verify(d, p)
        h = hand(p, g)
        log('HAND', h, 'mass g', round(V * DENS, 3))
        for support in ('wall', 'holes'):
            for el in sizes:
                def c(d, el=el):
                    fl = [f for f in faces(d) if face_info(f)['kind'] == 'cyl' and abs(face_info(f)['r'] - HOLE_R) > 0.02]
                    log('fillet faces for mesh control', len(fl))
                    return [(fl, round(0.3 * el, 3))]
                tag = f'{name}_{support}_{str(el).replace(".", "p")}'[:24]
                r = solve(j, d, tag, support, el, c, dict(nodes=int(1.6 * V / (el ** 3 / 8.5) * 1.6), disp='0.3 to 1.0',
                          peak='in a window corner fillet or the strut foot fillet at the strip; members at '
                               f'{h["chord_stress_mpa"]} / {h["strut_stress_mpa"]} MPa'))
                ck = checks(r, x=30.0, tag=tag)
                band = (np.abs(r.pos[:, 0] - 30) < 2) & (np.abs(r.pos[:, 2] - h['zc']) < p['dc'] / 2 + 0.3)
                sx = float(r.s[band, 1].mean())
                m = measures(r)
                ex = ~mask(r)
                # the pad and its junction with the members sit inside the load mask: read them with the fixture mask only
                from scipy.spatial import cKDTree
                padz = r.in_box([52.0, 14.9, 45.0, 65.1, 25.1, 52.1]) & (cKDTree(r.fixed_pts).query(r.pos)[0] >= 2.0)
                mp = measures(r, padz)
                log(tag, 'PAD ZONE (load mask off) vm', mp['vm'], 'Y', json.dumps(mp['Y']))
                row = dict(tag=tag, support=support, el=el, nodes=r.nodes, reaction=r.reaction, max_disp=round(r.max_disp(), 4),
                           chord_sx=round(sx, 2), chord_sx_hand=h['chord_stress_mpa'], measures=m, factors_Y=factors(m, 'Y'),
                           factors_X=factors(m, 'X'), factors_Z=factors(m, 'Z'), pad_zone=mp, pad_factors_Y=factors(mp, 'Y'),
                           excluded=dict(vm=round(float(r.vm[ex].max()), 2), at=r.pos[np.flatnonzero(ex)[np.argmax(r.vm[ex])]].round(2).tolist()))
                log(tag, 'chord sx', round(sx, 2), 'hand', h['chord_stress_mpa'], '| Y factors', row['factors_Y'], '| vm', m['vm'],
                    '| Y', json.dumps(m['Y']), '| excluded', row['excluded'])
                rows.append(row)
        close(j.sw, d)
    out = dict(name=name, params=p, fillet_r=rf, volume_mm3=round(V, 1), mass_g=round(V * DENS, 3), fixed=fixed, hand=h, sha256=sha(path),
               rows=rows, worst_Y=[min(r['factors_Y'][k] for r in rows) for k in range(4)])
    f = HERE / 'b3_steps.json'
    allsteps = json.loads(f.read_text()) if f.exists() else []
    allsteps.append(out)
    f.write_text(json.dumps(allsteps, indent=1, default=float))
    print('STEP', name, 'mass', out['mass_g'], 'worst Y factors (yield, layer, shear, min)', out['worst_Y'], 'buckling', h['buckling_factor_pinned'])
