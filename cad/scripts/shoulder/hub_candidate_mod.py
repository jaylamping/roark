"""Hub no-support candidate without the STEP import: the released hub part copied into the look folder and the candidate's
features added on top. This route exists because the hub's STEP import did not return on holly-pc on 2026-11-14 (LoadFile4
opens the part and never comes back, hidden instance, three times).

    LOOK=hubNS [NOSUP_DEG=50] python hub_candidate_mod.py

The print profile supports every face at 45 deg or flatter, so the new faces stand at NOSUP_DEG (50) from the bed.

  NOSUP_CONE_A/B   cone under the spigot's inner ledge (Y 302.3) down to the pocket floor. Between the lugs' sectors it
                   starts at the ledge's inner edge (r 23); in the lugs' sectors (+-40 deg about each lug) it starts at the
                   foot of the r 20 bore's 45 deg top (r 20, Y 299.3), so that top is covered too
  NOSUP_WIN_CLEAR  the cable window's slot cut again below the ledge, then BAND_FILL_2, the band fill put back exactly as
                   it was: together they clear the cone out of the slot and change nothing else
  NOSUP_RIB        rib under each lug's inner block (flat end at Y 300), lying on the cone
  SLIT_FILL        the six arc slits r 19.0-19.5 through the hub top (between the imported plate and the step ring) filled
"""
import os
import shutil

import numpy as np

from build_parts import NAMES, finish_part, sector, ypt, ysk, yaw_rev
from dims import DISH_R0, DISH_Y, HUB, HUB_WIN_A, HUB_WIN_CLIP, RS02_OUT, RX, YZ
from swk import *
from swk import vol_com

assert LOOK, 'look builds only: this never writes the real part'
SRC = CAD / 'shoulder' / 'left' / f"{NAMES['hub']}.SLDPRT"
DST = OUT / f"{NAMES['hub']}.SLDPRT"
K = math.tan(math.radians(float(os.environ.get('NOSUP_DEG', '50'))))
YAX, ZAX = (0, 1, 0), (0, 0, 1)


def clip(poly, keep):
    """Sutherland-Hodgman against one half-plane; keep(q) -> signed distance, >= 0 inside."""
    out = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        da, db = keep(a), keep(b)
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append(a + (b - a) * t)
    return out


def part_rev(d, ax, name, prof, a_start, sweep):
    """Partial revolve boss of an (r, Y) profile about the yaw axis from a_start over sweep degrees; the direction is checked
    by the centroid of the added volume (as hub_d2 in build_parts)."""
    ta = math.radians(a_start)
    ua = (math.cos(ta), 0.0, math.sin(ta))
    plg, _ = plane_axis_angle(d, ax, d.FeatureByName('Front Plane'), a_start % 180, ua, 'P_' + name)
    with Sk(d, plg, name) as s_:
        s_.poly([(RX + r_ * ua[0], y_, YZ + r_ * ua[2]) for r_, y_ in prof])
        s_.cline((RX, 280.0, YZ), (RX, 330.0, YZ))
    want_ = math.radians(a_start + sweep / 2)
    for rev in (False, True):
        v0, m0 = vol_com(d)
        d.ClearSelection2(True)
        s_.feat.Select2(False, 0)
        f = d.FeatureManager.FeatureRevolve2(True, True, False, False, rev, False, 0, 0, math.radians(sweep), 0, False, False, 0, 0, 0, 0, 0, True, False, True)
        d.ForceRebuild3(False)
        v1, m1 = vol_com(d)
        if f is not None and v1 - v0 > 1.0:
            cen_ = (m1 - m0) / (v1 - v0)
            ang = math.atan2(cen_[2] - YZ, cen_[0] - RX)
            if abs(((ang - want_ + math.pi) % (2 * math.pi)) - math.pi) < 0.12:
                f.Name = name
                log(f'  {name}: added {v1 - v0:.0f} mm3, centroid {math.degrees(ang):.1f} deg')
                return v1 - v0
        if f is not None:
            d.EditUndo2(1)
            d.ForceRebuild3(False)
    raise SystemExit(f'{name} failed')


def main():
    shutil.copy2(SRC, DST)
    e_, w_ = L(), L()
    d = app().OpenDoc6(str(DST), 1, 1, '', e_, w_)
    if d is None:
        raise SystemExit(f'open failed {e_.value}')
    v0 = vol(d)
    log('hub candidate from the released part', bodies(d), 'slope', os.environ.get('NOSUP_DEG', '50'))
    if os.environ.get('NOSUP', '1') != '0':
        ax = d.FeatureByName('YAW_AXIS')
        A = [(22.9, 302.2), (36.3, 302.2), (36.3, 313.1), (22.9 + (313.1 - 302.2) / K, 313.1)]
        B = [(20.05, 299.2), (23.4, 299.2), (23.4, 302.2), (36.3, 302.2), (36.3, 313.1), (20.05 + (313.1 - 299.2) / K, 313.1)]
        log('  cone A', [tuple(round(v, 2) for v in q) for q in A], ' cone B', [tuple(round(v, 2) for v in q) for q in B])
        part_rev(d, ax, 'NOSUP_CONE_A1', A, 39.5, 101.0)
        part_rev(d, ax, 'NOSUP_CONE_A2', A, 219.5, 101.0)
        part_rev(d, ax, 'NOSUP_CONE_B1', B, 140.0, 80.0)
        part_rev(d, ax, 'NOSUP_CONE_B2', B, -40.0, 80.0)
        v1 = vol(d)
        log(f'  cone added {v1 - v0:.0f} mm3')
        # the window's slot in its own plane, as build_hub draws it: (along, Y) from (31, DISH_Y + 2) to (15.5, 298), 9 wide
        t = math.radians(HUB_WIN_A)
        u = np.array((math.cos(t), 0.0, math.sin(t)))
        p0, p1 = np.array((31.0, DISH_Y + 2)), np.array((15.5, 298.0))
        ax_ = (p1 - p0) / np.linalg.norm(p1 - p0)
        nr_ = np.array((-ax_[1], ax_[0]))
        poly = [p0 + nr_ * 4.5, p1 + nr_ * 4.5, p1 - nr_ * 4.5, p0 - nr_ * 4.5]
        for keep in (lambda q: q[0] - HUB_WIN_CLIP, lambda q: q[1] - 302.35):
            poly = clip(poly, keep)
        log('  NOSUP_WIN_CLEAR outline (along, Y): ' + ' '.join('(%.2f, %.2f)' % tuple(q) for q in poly))
        if os.environ.get('NOSUP_WIN_CLEAR', '1') != '0':      # 0: the cone is left standing in the slot's roof corner
            with Sk(d, d.FeatureByName('P_HUB_WIN'), 'NOSUP_WIN_CLEAR') as s:
                s.poly([(RX + q[0] * u[0], q[1], YZ + q[0] * u[2]) for q in poly])
            extrude(d, s.feat, 'NOSUP_WIN_CLEAR', 16.0, (0, 0, 0), cut=True, mode=MID)
            v2 = vol(d)
            bf = HUB['band_fill']
            extrude(d, ysk(d, bf['y'][0], 'BAND_FILL_2', lambda s: [sector(s, lambda r, a: ypt(r, a, bf['y'][0]), bf['r'][0], bf['r'][1], a0_, a1_, 2.0)
                                                                   for a0_, a1_ in bf['sectors']]), 'BAND_FILL_2', bf['y'][1] - bf['y'][0], YAX, lo=-1.0)
            v2b = vol(d)
            log(f'  NOSUP_WIN_CLEAR cut {v1 - v2:.0f} mm3, BAND_FILL_2 put back {v2b - v2:.0f} mm3: net {v1 - v2b:.0f} mm3 out of the cone')
        else:
            v2b = v1
        pl0 = plane(d, 'Z', 6.0, 'P_Z_6')
        with Sk(d, pl0, 'NOSUP_RIB') as s_r:
            for sg in (-1, 1):
                s_r.poly([(RX + sg * 18.76, 299.8, 6.0), (RX + sg * (18.76 + 13.5 / K), 313.3, 6.0), (RX + sg * 34.5, 313.3, 6.0), (RX + sg * 21.0, 299.8, 6.0)])
        extrude(d, s_r.feat, 'NOSUP_RIB', 10.0, ZAX, mode=MID)
        v3 = vol(d)
        log(f'  NOSUP_RIB added {v3 - v2b:.0f} mm3')
    else:
        v3 = v0
    yaw_rev(d, 'SLIT_FILL', [(18.8, 312.8), (19.6, 312.8), (19.6, RS02_OUT), (18.8, RS02_OUT)])
    v4 = vol(d)
    log(f'  SLIT_FILL added {v4 - v3:.0f} mm3; total added {v4 - v0:.0f} mm3')
    h = float(os.environ.get('TOP_RAISE', '0'))
    if h:
        # taller centre: the top face (the RS02 seat) h higher in the part's own coordinates, so the arm side of the hub is
        # where it was and the hub sits h lower on the motor. Solid from just under the old face (this also fills the old
        # 0.5 mm hole chamfers), the six holes cut through again and chamfered at the new face
        top = RS02_OUT + h
        yaw_rev(d, 'TOP_RAISE', [(0.0, RS02_OUT - 0.56), (DISH_R0 + 0.01, RS02_OUT - 0.56), (DISH_R0 + 0.01, top), (0.0, top)])
        cen = [(a_, RX + 12.0 * math.cos(math.radians(a_)), YZ + 12.0 * math.sin(math.radians(a_))) for a_ in (-142.0, -82.0, -22.0, 38.0, 98.0, 158.0)]
        extrude(d, ysk(d, RS02_OUT - 1.0, 'TOP_HOLES', lambda s: [s.circle((cx, RS02_OUT - 1.0, cz), 1.9 if a_ in (-142.0, 38.0) else 2.15) for a_, cx, cz in cen]),
                'TOP_HOLES', h + 1.5, YAX, cut=True)
        for a_, cx, cz in cen:
            r0 = 1.9 if a_ in (-142.0, 38.0) else 2.15
            nm = ('TOP_CH_%+.0f' % a_).replace('+', 'p').replace('-', 'm')
            with Sk(d, plane(d, 'Z', cz, 'P_' + nm), nm) as s_:
                s_.poly([(cx + r0 - 0.05, top + 0.05, cz), (cx + r0 + 0.5, top + 0.05, cz), (cx + r0 + 0.5, top, cz), (cx + r0, top - 0.5, cz), (cx + r0 - 0.05, top - 0.5, cz)])
                s_.cline((cx, top - 5.0, cz), (cx, top + 5.0, cz))
            revolve(d, s_.feat, nm, cut=True, lo=0.05)
        # a fillet of radius RF from the step wall into the dish floor (today the 1.5 mm step is one R1.5 fillet)
        RF = float(os.environ.get('TOP_FILLET', '2.0'))
        pz = plane(d, 'Z', YZ, 'P_Z_YZ')
        for sense in (-1, 1):       # a true arc (a faceted one meshes into hundreds of thousands of extra nodes); the short quarter
            va = vol(d)
            with Sk(d, pz, 'STEP_FILLET') as s_:
                sm_ = d.SketchManager
                Pt = lambda r_, y_: s_.p((RX + r_, y_, YZ))
                A_, B_, E1, E2, C_, O_ = (Pt(DISH_R0 - 0.05, DISH_Y - 0.06), Pt(DISH_R0 + RF, DISH_Y - 0.06), Pt(DISH_R0 + RF, DISH_Y), Pt(DISH_R0, DISH_Y + RF),
                                          Pt(DISH_R0 - 0.05, DISH_Y + RF), Pt(DISH_R0 + RF, DISH_Y + RF))
                for u_, v_ in ((A_, B_), (B_, E1), (E2, C_), (C_, A_)):
                    sm_.CreateLine(u_[0], u_[1], 0, v_[0], v_[1], 0)
                sm_.CreateArc(O_[0], O_[1], 0, E1[0], E1[1], 0, E2[0], E2[1], 0, sense)
                s_.cline((RX, 280.0, YZ), (RX, 330.0, YZ))
            try:
                revolve(d, s_.feat, 'STEP_FILLET', lo=0.5)
            except SystemExit:
                d.EditUndo2(1)
                continue
            if vol(d) - va < 200.0:
                break
            log(f'  STEP_FILLET sense {sense}: added {vol(d) - va:.0f} mm3, the long way round: undone')
            d.EditUndo2(2)
            d.ForceRebuild3(False)
        log(f'  taller centre +{h}: top face Y {top:.2f}, added {vol(d) - v4:.0f} mm3')
    wr = float(os.environ.get('WIN_ROUND', '1.5'))
    if wr:
        # the cable window's mouth in the dish floor: its edges rounded where the bare wires turn down into the slot
        tw = math.radians(HUB_WIN_A)

        def _mouth(p):
            x_, z_ = p[0] - RX, p[2] - YZ
            al, w_ = x_ * math.cos(tw) + z_ * math.sin(tw), -x_ * math.sin(tw) + z_ * math.cos(tw)
            return abs(p[1] - DISH_Y) < 0.05 and 20.0 < al < 37.0 and abs(w_) < 8.6
        ed = edges_where(d, _mouth)
        log(f'  window mouth edges in the dish floor: {len(ed)}')
        vb = vol(d)
        fillet_each(d, ed, [wr, 1.0, 0.6], 'WIN_ROUND')
        log(f'  WIN_ROUND removed {vb - vol(d):.1f} mm3')
    finish_part(d, 'hub', dict(Note='Candidate: no support inside the hub; hub top slits filled'))
    finish()


if __name__ == '__main__':
    main()
