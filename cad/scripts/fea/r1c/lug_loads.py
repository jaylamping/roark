"""Resultant load on each hub lug by face (2026-11-13, for the shoulder thread's FE). Hub-side nodal stresses, traction t = sigma.n
(n = the hub's outward normal), linearly interpolated over each face and integrated on a 0.1 mm grid:
  front Z face (Z 11.0), back Z face (Z 1.0), outer face (X offset 34.4), bolt-hole wall (r 1.7).
Force = what our side applies to the hub. Centre of pressure (X offset, Y) on the Z faces from the normal component.
Check: a Y-plane section through each lug at Y YC (stress integrated over the lug's cross-section) against the sum of the face forces
below YC; the two should cancel. Moment about X (the G90 moment axis) of the lug face forces, about (HX, Y 302, CZ) (the disc face),
against the applied moment carried to that point: the rest goes through the ring, ridge, groove and spigot.
Nodal (extrapolated) stresses at a contact face over-read; the section check shows by how much.
    python lug_loads.py NPZ POST_TXT [Fz_app_N Mx_app_Nm Y_app]      (under capped.py)"""
import re
import sys

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from shapely.geometry import Point, box
from shapely import contains_xy

HX, CZ, YC = 170.49, 5.985875, 294.5
import os
HOLR = float(os.environ.get('LUG_HOLE_R', '1.7'))      # hub lug hole radius: 1.7 (Dia 3.4), r1g5 / r1g6 1.9 (Dia 3.8)
BOLTS = {-1: 147.5, 1: 193.5}
d = np.load(sys.argv[1])
p, s = d['pos'], d['s']
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[2]).read().split('\n')[0])
body = np.full(len(p), '?', object)
for nm, a, b in runs:
    body[int(a):int(b) + 1] = nm
hub = body == 'hub'
# stress tensor per node: s columns 1..6 = sx, sy, sz, txy, txz, tyz
S = np.zeros((len(p), 3, 3))
S[:, 0, 0], S[:, 1, 1], S[:, 2, 2] = s[:, 1], s[:, 2], s[:, 3]
S[:, 0, 1] = S[:, 1, 0] = s[:, 4]
S[:, 0, 2] = S[:, 2, 0] = s[:, 5]
S[:, 1, 2] = S[:, 2, 1] = s[:, 6]
G = 0.1


def integrate(mask, coords, normal_fn, region, ymask=None):
    """coords(q) -> 2D face coordinates; normal_fn(q) -> outward normals (n x 3); region: shapely polygon in face coords"""
    q = np.flatnonzero(mask)
    if len(q) < 4:
        return None
    uv = coords(q)
    tr = np.einsum('nij,nj->ni', S[q], normal_fn(q))
    f = LinearNDInterpolator(uv, tr)
    b = region.bounds
    gu, gv = np.meshgrid(np.arange(b[0] + G / 2, b[2], G), np.arange(b[1] + G / 2, b[3], G))
    gu, gv = gu.ravel(), gv.ravel()
    inside = contains_xy(region, gu, gv)
    if ymask is not None:
        inside &= ymask(gu, gv)
    gu, gv = gu[inside], gv[inside]
    t = f(gu, gv)
    ok = ~np.isnan(t[:, 0])
    F = (t[ok] * G * G).sum(axis=0)
    pn = None
    return F, gu[ok], gv[ok], t[ok], ok.mean()


rows = []
Yref = 302.0
for side in (-1, 1):
    xo = side * (p[:, 0] - HX)
    bx = BOLTS[side]
    lugzone = hub & (xo > 18.5) & (xo < 34.6) & (p[:, 1] > 287.9) & (p[:, 1] < 295.0)
    flat = box(18.76, 288.0, 34.4, 294.8).difference(Point(abs(bx - HX), 292.0).buffer(HOLR, 64))
    tot = np.zeros(3)
    for zf, nm, nz in ((11.0, 'front Z face', 1.0), (1.0, 'back Z face', -1.0)):
        m = lugzone & (np.abs(p[:, 2] - zf) < 0.03)
        r = integrate(m, lambda q: np.c_[side * (p[q, 0] - HX), p[q, 1]], lambda q: np.tile([0, 0, nz], (len(q), 1)), flat)
        if r is None:
            rows.append((side, nm, None)); continue
        F, gu, gv, t, cov = r
        pn = -t[:, 2] * nz      # compressive normal pressure (positive)
        w = np.clip(pn, 0, None)
        cop = (float((w * gu).sum() / w.sum()), float((w * gv).sum() / w.sum())) if w.sum() > 0 else (np.nan, np.nan)
        rows.append((side, nm, dict(F=F, cop=cop, cover=cov, pmax=float(pn.max()), pmean=float(pn[pn > 0].mean()) if (pn > 0).any() else 0.0)))
        tot += F
    # outer face (X offset 34.4), outward normal +side X
    m = lugzone & (np.abs(xo - 34.4) < 0.03) & (np.abs(p[:, 2] - CZ) < 5.0)
    r = integrate(m, lambda q: np.c_[p[q, 2], p[q, 1]], lambda q: np.tile([side, 0, 0], (len(q), 1)), box(1.0, 288.0, 11.0, 294.8))
    rows.append((side, 'outer face', None if r is None else dict(F=r[0], cop=(np.nan, np.nan), cover=r[4], pmax=float((-r[3][:, 0] * side).max()), pmean=0.0)))
    if r is not None:
        tot += r[0]
    # bolt-hole wall r 1.7, outward normal of the hub = toward the hole axis
    rb = np.hypot(p[:, 0] - bx, p[:, 1] - 292.0)
    m = hub & (np.abs(rb - HOLR) < 0.03) & (np.abs(p[:, 2] - CZ) < 4.99)

    def hc(q):
        return np.c_[np.degrees(np.arctan2(p[q, 1] - 292.0, p[q, 0] - bx)) * np.pi / 180 * HOLR, p[q, 2]]

    def hn(q):
        v = np.c_[bx - p[q, 0], 292.0 - p[q, 1], np.zeros(len(q))]
        return v / np.linalg.norm(v, axis=1)[:, None]
    r = integrate(m, hc, hn, box(-np.pi * HOLR, 1.0, np.pi * HOLR, 11.0))
    rows.append((side, 'bolt-hole wall', None if r is None else dict(F=r[0], cop=(np.nan, np.nan), cover=r[4], pmax=0.0, pmean=0.0)))
    if r is not None:
        tot += r[0]
    # section check at Y YC through the lug (outward normal of the lower part = +Y)
    sl = hub & (np.abs(p[:, 1] - YC) < 0.6) & (xo > 18.5) & (xo < 34.6) & (np.abs(p[:, 2] - CZ) < 5.0)
    q = np.flatnonzero(sl)
    f3 = LinearNDInterpolator(np.c_[p[q, 0], p[q, 1], p[q, 2]], np.einsum('nij,j->ni', S[q], [0, 1.0, 0]))
    reg = box(18.76, 1.0, 34.4, 11.0).difference(Point(abs(bx - HX), 292.0).buffer(0.01))
    gu, gz = np.meshgrid(np.arange(18.76 + G / 2, 34.4, G), np.arange(1.0 + G / 2, 11.0, G))
    gx = HX + side * gu.ravel()
    t = f3(gx, np.full(gx.shape, YC), gz.ravel())
    ok = ~np.isnan(t[:, 0])
    Fsec = (t[ok] * G * G).sum(axis=0)
    rows.append((side, f'section at Y {YC} (lug cross-section; should cancel the faces below it)', dict(F=Fsec, cop=(np.nan, np.nan), cover=ok.mean(), pmax=0, pmean=0)))
    rows.append((side, 'sum of the four faces', dict(F=tot, cop=(np.nan, np.nan), cover=1.0, pmax=0, pmean=0)))
# ---- whole-hub section above the disc (Y YH): everything the arm puts into the hub passes through it (the hub is fixed at its top)
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
YH = 310.0
hubm = trimesh.load(sys.argv[2].replace('post.txt', 'HUB_GROOVE_r1d.STL'))
sec = hubm.section(plane_origin=[0, YH, 0], plane_normal=[0, 1, 0])
reg = Polygon()
for e in sec.discrete:
    if len(e) >= 4:
        reg = reg.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
q = np.flatnonzero(hub & (np.abs(p[:, 1] - YH) < 2.5))
f3 = LinearNDInterpolator(np.c_[p[q, 0], p[q, 1], p[q, 2]], np.einsum('nij,j->ni', S[q], [0, 1.0, 0]))
b = reg.bounds
gx, gz = np.meshgrid(np.arange(b[0] + G, b[2], G * 2), np.arange(b[1] + G, b[3], G * 2))
gx, gz = gx.ravel(), gz.ravel()
ins = contains_xy(reg, gx, gz)
gx, gz = gx[ins], gz[ins]
tt = f3(gx, np.full(gx.shape, YH), gz)
ok = ~np.isnan(tt[:, 0])
dA = (G * 2) ** 2
Fcut = (tt[ok] * dA).sum(axis=0)
rr = np.c_[gx[ok] - HX, np.full(ok.sum(), YH - Yref), gz[ok] - CZ]
Mcut = (np.cross(rr, tt[ok]) * dA).sum(axis=0) / 1000.0
# what the arm puts into the hub = minus what the upper hub puts on the lower hub through the cut (outward normal +Y); Mcut is about
# (HX, Yref, CZ) already
print(f'result: {sys.argv[1]}')
print(f'{"lug":4s} {"face":62s} {"Fx":>8s} {"Fy":>8s} {"Fz":>8s}  {"CoP X off":>9s} {"CoP Y":>7s}  {"p mean":>6s} {"p max":>6s} {"cover":>5s}')
for side, nm, r in rows:
    lab = '-X' if side < 0 else '+X'
    if r is None:
        print(f'{lab:4s} {nm:62s} no nodes'); continue
    F = r['F']
    print(f'{lab:4s} {nm:62s} {F[0]:8.1f} {F[1]:8.1f} {F[2]:8.1f}  {r["cop"][0]:9.2f} {r["cop"][1]:7.2f}  {r["pmean"]:6.2f} {r["pmax"]:6.2f} {r["cover"]:5.2f}')

# lug totals (faces and, better, from each lug section) and moments about (HX, Yref, CZ)
def lugsum(kind):
    F, M = np.zeros(3), np.zeros(3)
    for side, nm, r in rows:
        if r is None:
            continue
        if kind == 'faces' and nm in ('front Z face', 'back Z face', 'outer face', 'bolt-hole wall'):
            F += r['F']
            cop = r['cop']
            if not np.isnan(cop[0]):
                arm_ = np.array([side * cop[0], cop[1] - Yref, (11.0 if nm.startswith('front') else 1.0) - CZ])
            else:
                arm_ = np.array([side * 30.0, 291.5 - Yref, 0.0])
            M += np.cross(arm_, r['F']) / 1000.0
        if kind == 'section' and nm.startswith('section'):
            # lever: the lug's normal-force centre from its Z faces (Fz-weighted centre of pressure)
            fz = [(abs(r2['F'][2]), r2['cop']) for s2, n2, r2 in rows if s2 == side and r2 is not None and n2.endswith('Z face') and not np.isnan(r2['cop'][0])]
            w = sum(a for a, _ in fz)
            xc = sum(a * c[0] for a, c in fz) / w if w else 27.0
            yc = sum(a * c[1] for a, c in fz) / w if w else 291.5
            F += -r['F']
            M += np.cross([side * xc, yc - Yref, 0.0], -r['F']) / 1000.0
    return F, M


if len(sys.argv) > 8:
    Fa = np.array([float(v) for v in sys.argv[3:6]])
    Ma = np.array([float(v) for v in sys.argv[6:9]])
    Ya = 209.861
    Ma_ref = Ma + np.cross([0, Ya - Yref, 0], Fa) / 1000.0
    Fl, Ml = lugsum('faces')
    Fs, Ms = lugsum('section')
    print(f'applied (on the arm, at the RS02 centre X {HX} Y {Ya} Z {CZ:.3f}): F {np.round(Fa, 1).tolist()} N, M {np.round(Ma, 2).tolist()} N.m; '
          f'carried to (X {HX}, Y {Yref}, Z {CZ:.3f}): M {np.round(Ma_ref, 2).tolist()} N.m')
    print(f'whole-hub section at Y {YH} (everything the arm puts into the hub): F {np.round(-Fcut, 1).tolist()} N, M about the same point '
          f'{np.round(-Mcut, 2).tolist()} N.m (cover {ok.mean():.2f})')
    print(f'both lugs, from the faces:    F {np.round(Fl, 1).tolist()} N, M {np.round(Ml, 2).tolist()} N.m')
    print(f'both lugs, from the sections: F {np.round(Fs, 1).tolist()} N, M {np.round(Ms, 2).tolist()} N.m (lever at each lug Z-face centre of pressure)')
    print(f'ring, ridge, groove and spigot (applied minus lugs from the sections): F {np.round(Fa - Fs, 1).tolist()} N, M {np.round(Ma_ref - Ms, 2).tolist()} N.m')
    print(f'balance: applied F {np.round(Fa, 1).tolist()} N, M {np.round(Ma_ref, 2).tolist()} N.m against the whole-hub section F {np.round(-Fcut, 1).tolist()} N, M {np.round(-Mcut, 2).tolist()} N.m')
