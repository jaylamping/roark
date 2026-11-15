"""Hub candidate 2 (2026-11-15): the released hub part copied into the look folder and rebuilt at the top, for strength.
Built on a copy because the hub's STEP import does not return on holly-pc (see hub_candidate_mod.py).

    LOOK=hubT30A [TOP_RAISE=3.0] [SEAT_Y=299.26] python hub_candidate2.py

Everything is in the part's own (arm) coordinates: the arm side of the hub does not move, the top face rises by TOP_RAISE.

  POCKET_FILL_*   the inner pocket under the spigot's ledge filled solid (Y 302.3 to the floor, r 23 to the wall); in the
                  lugs' sectors it also covers the r 20 bore's 45 deg top with a 50 deg face, so nothing inside needs support
  NOSUP_RIB       50 deg rib under each lug's inner block
  WIN_FILL_*      the old 9 x 16 cable slot filled where it ran through solid (floor, step ring foot, pocket)
  NEW_WIN         the new cable slot: 4.5 (in the radial plane) x 11 (tangential), a dog-leg: straight down through the dish
                  floor at r 27.0-31.5, then 50 deg inward under the step ring, out through the bore wall at Y 302.1-309.1
  WIN_MOUTH       1.5 mm round on the slot's mouth in the dish floor; the knee's inner corner is rounded 2 mm in the sketch
  SLIT_FILL       the six arc slits r 19.0-19.5 through the hub top filled
  PLATE_THICK     the centre plate 4 mm thicker downward (Y 311.9-315.9), between the boss tubes, centre hole kept
  TUBE_THICK      the six boss tubes from dia 8.8 to 10.8 (head seat ring r 2.15-5.4)
  TOP_RAISE       the top face TOP_RAISE higher; holes cut through and chamfered again
  STEP_FILLET     R 2 from the step wall into the dish floor (TOP_FILLET)
"""
import inspect
import os
import shutil

import numpy as np

from build_parts import NAMES, STEPD, STL, finish_part, ysk, yaw_rev
from dims import DISH_R0, DISH_Y, HUB_WIN_A, RS02_OUT, RX, YZ
from hub_candidate_mod import clip, part_rev
from swk import *

ADOPT = os.environ.get('HUB_ADOPT') == '1'      # only adopt_hub_revE1.sh sets this: build the REAL part from the archived rev D3c7 part
assert LOOK or ADOPT, 'look builds only, unless the adoption script runs it'
SRC = (CAD / '_archive' / 'hub_revD3c7' if ADOPT else CAD / 'shoulder' / 'left') / f"{NAMES['hub']}.SLDPRT"
DST = OUT / f"{NAMES['hub']}.SLDPRT"
K = math.tan(math.radians(50.0))
YAX, ZAX = (0, 1, 0), (0, 0, 1)
SCREWS = (-142.0, -82.0, -22.0, 38.0, 98.0, 158.0)
TW = math.radians(HUB_WIN_A)
U = np.array((math.cos(TW), 0.0, math.sin(TW)))
WIN_T, WIN_W, WIN_DEG, MOUTH = 4.5, 11.0, 50.0, (27.0, 31.5)
WIN_CLIP = 16.0
KNEE_R = float(os.environ.get('KNEE_R', '2.0'))


def win_xyz(q):
    return (RX + q[0] * U[0], q[1], YZ + q[0] * U[2])


def aw(p):
    """(along, across) of a model point in the window's frame."""
    x_, z_ = p[0] - RX, p[2] - YZ
    return x_ * math.cos(TW) + z_ * math.sin(TW), -x_ * math.sin(TW) + z_ * math.cos(TW)


def main():
    h = float(os.environ.get('TOP_RAISE', '3.0'))
    shutil.copy2(SRC, DST)
    e_, w_ = L(), L()
    d = app().OpenDoc6(str(DST), 1, 1, '', e_, w_)
    if d is None:
        raise SystemExit(f'open failed {e_.value}')
    v0 = vol(d)
    log('hub candidate 2 from the released part', bodies(d), 'top raise', h)
    ax = d.FeatureByName('YAW_AXIS')
    pwin = d.FeatureByName('P_HUB_WIN')
    # ---- the pocket, solid
    A = [(23.0, 302.2), (36.3, 302.2), (36.3, 313.1), (23.0, 313.1)]
    B = [(20.05, 299.2), (23.4, 299.2), (23.4, 302.2), (36.3, 302.2), (36.3, 313.1), (23.0, 313.1), (23.0, 299.2 + (23.0 - 20.05) * K)]
    part_rev(d, ax, 'POCKET_FILL_A1', A, 39.5, 101.0)
    part_rev(d, ax, 'POCKET_FILL_A2', A, 219.5, 101.0)
    part_rev(d, ax, 'POCKET_FILL_B1', B, 140.0, 80.0)
    part_rev(d, ax, 'POCKET_FILL_B2', B, -40.0, 80.0)
    v1 = vol(d)
    log(f'  pocket fill added {v1 - v0:.0f} mm3')
    pl0 = plane(d, 'Z', 6.0, 'P_Z_6')
    with Sk(d, pl0, 'NOSUP_RIB') as s_r:
        for sg in (-1, 1):
            s_r.poly([(RX + sg * 18.76, 299.8, 6.0), (RX + sg * 23.3, 299.8 + (23.3 - 18.76) * K, 6.0), (RX + sg * 23.3, 299.8, 6.0)])
    extrude(d, s_r.feat, 'NOSUP_RIB', 10.0, ZAX, mode=MID)
    # ---- the old slot filled where it ran through solid
    p0, p1 = np.array((31.0, DISH_Y + 2)), np.array((15.5, 298.0))
    ax_ = (p1 - p0) / np.linalg.norm(p1 - p0)
    nr_ = np.array((-ax_[1], ax_[0]))
    old = [p0 + nr_ * 4.5, p1 + nr_ * 4.5, p1 - nr_ * 4.5, p0 - nr_ * 4.5]
    for nm, keeps in (('WIN_FILL_1', (lambda q: q[0] - 23.0, lambda q: DISH_Y - q[1])),
                      ('WIN_FILL_2', (lambda q: q[0] - 18.85, lambda q: 23.05 - q[0], lambda q: q[1] - 312.8, lambda q: DISH_Y - q[1]))):
        poly = old
        for keep in keeps:
            poly = clip(poly, keep)
        with Sk(d, pwin, nm) as s:
            s.poly([win_xyz(q) for q in poly])
        extrude(d, s.feat, nm, 16.1, (0, 0, 0), mode=MID, lo=-1.0)
    v2 = vol(d)
    log(f'  old slot filled: {v2 - v1:.0f} mm3 with the rib')
    # ---- the new slot
    c_, s_ = math.cos(math.radians(WIN_DEG)), math.sin(math.radians(WIN_DEG))
    y_s, y_l = 302.1, 302.1 + WIN_T / c_                      # the two faces' heights at the bore wall (r 23)
    k1 = (MOUTH[1], y_s + (MOUTH[1] - 23.0) / c_ * s_)
    k2 = (MOUTH[0], y_l + (MOUTH[0] - 23.0) / c_ * s_)
    e1 = (WIN_CLIP, y_s - (23.0 - WIN_CLIP) / c_ * s_)
    e2 = (WIN_CLIP, y_l - (23.0 - WIN_CLIP) / c_ * s_)
    # the lip between the slant's lower face and the bore wall would run out to a feather edge (arm thread, 2026-11-15):
    # it is cut square 1.5 mm up from the exit, which leaves a flat about 1.3 mm wide
    yb = y_l + 1.5
    b2 = (23.0 + (yb - y_l) / s_ * c_, yb)
    new = [(MOUTH[0], DISH_Y + 4.0), (MOUTH[1], DISH_Y + 4.0), k1, e1, (WIN_CLIP, yb), b2, k2]
    log('  NEW_WIN outline (along, Y): ' + ' '.join('(%.2f, %.2f)' % q for q in new) + f'; at the bore wall Y {y_s:.2f} to {y_l:.2f}')
    with Sk(d, pwin, 'NEW_WIN') as s:
        s.rpoly([win_xyz(q) for q in new], [0, 0, 1.0, 0, 0, 0, KNEE_R])      # the knee's inner corner rounded, so the wires slide round it
    extrude(d, s.feat, 'NEW_WIN', WIN_W, (0, 0, 0), cut=True, mode=MID)
    v3 = vol(d)
    log(f'  NEW_WIN cut {v2 - v3:.0f} mm3')
    hw = WIN_W / 2

    def corner(p):
        a_, w__ = aw(p)
        return abs(abs(w__) - hw) < 0.05 and 21.5 < a_ < MOUTH[1] + 0.1 and 300.0 < p[1] < DISH_Y + 0.05
    ed = [e for e in edges_where(d, corner)]
    log(f'  slot long edges: {len(ed)}')
    if os.environ.get('WIN_CORNER') == '1':      # off: filleting these edges took SolidWorks down (2026-11-15); the corners stay square
        fillet_each(d, ed, [1.5, 1.0], 'WIN_CORNER')

    def mouth(p):
        a_, w__ = aw(p)
        return abs(p[1] - DISH_Y) < 0.05 and MOUTH[0] - 0.2 < a_ < MOUTH[1] + 0.2 and abs(w__) < hw + 0.2
    ed = edges_where(d, mouth)
    log(f'  slot mouth edges in the dish floor: {len(ed)}')
    v3b = vol(d)
    fillet(d, ed, [1.5, 1.0, 0.6], 'WIN_MOUTH') or fillet_each(d, ed, [1.5, 1.0, 0.6], 'WIN_MOUTH')
    log(f'  rounds removed {v3 - vol(d):.1f} mm3 in all ({v3b - vol(d):.1f} at the mouth)')
    # ---- the top
    yaw_rev(d, 'SLIT_FILL', [(18.8, 312.8), (19.6, 312.8), (19.6, RS02_OUT), (18.8, RS02_OUT)])
    cen = [(a_, RX + 12.0 * math.cos(math.radians(a_)), YZ + 12.0 * math.sin(math.radians(a_))) for a_ in SCREWS]
    v4 = vol(d)
    extrude(d, ysk(d, 311.9, 'PLATE_THICK', lambda s: [s.circle((RX, 311.9, YZ), 18.9), s.circle((RX, 311.9, YZ), 1.7)] + [s.circle((cx, 311.9, cz), 4.3) for _, cx, cz in cen]),
            'PLATE_THICK', 4.1, YAX)
    extrude(d, ysk(d, 298.06, 'TUBE_THICK', lambda s: [c for _, cx, cz in cen for c in (s.circle((cx, 298.06, cz), 5.4), s.circle((cx, 298.06, cz), 4.3))]),
            'TUBE_THICK', 311.95 - 298.06, YAX)
    # the six head seats (the tubes' ends; Y 298.06 as imported). SEAT_Y sets the grip for the screw length in use:
    # higher = the tube ends cut back, lower = the tubes carried on down at dia 10.8 with a dia 4.3 hole
    seat = float(os.environ.get('SEAT_Y', '298.06'))
    if seat > 298.07:
        extrude(d, ysk(d, 297.5, 'SEAT_CUT', lambda s: [s.circle((cx, 297.5, cz), 5.6) for _, cx, cz in cen]), 'SEAT_CUT', seat - 297.5, YAX, cut=True)
    elif seat < 298.05:
        extrude(d, ysk(d, seat, 'SEAT_EXT', lambda s: [c for _, cx, cz in cen for c in (s.circle((cx, seat, cz), 5.4), s.circle((cx, seat, cz), 2.15))]),
                'SEAT_EXT', 298.1 - seat, YAX)
    log(f'  head seats at Y {seat:.2f} (arm coordinates); grip to the top face {RS02_OUT + h - seat:.2f}')
    log(f'  plate and tubes added {vol(d) - v4:.0f} mm3')
    if h:
        top = RS02_OUT + h
        v5 = vol(d)
        yaw_rev(d, 'TOP_RAISE', [(1.7, RS02_OUT - 0.56), (DISH_R0 + 0.01, RS02_OUT - 0.56), (DISH_R0 + 0.01, top), (1.7, top)])
        extrude(d, ysk(d, RS02_OUT - 1.0, 'TOP_HOLES', lambda s: [s.circle((cx, RS02_OUT - 1.0, cz), 1.9 if a_ in (-142.0, 38.0) else 2.15) for a_, cx, cz in cen]),
                'TOP_HOLES', h + 1.5, YAX, cut=True)
        # the hole edges on the seat face. TOP_EDGE: 'none' (default: square, as on the released hub; a chamfer puts a low
        # spot at its foot, hub_hole_post.py), 'ch0.5',
        # 'ch1.0', or 'relief' (the 0.5 chamfer plus a ring 0.2 deep and 1.0 wide round it, so the flange bears on the broad
        # face away from the hole wall)
        edge = os.environ.get('TOP_EDGE', 'none')
        ch = 0.0 if edge == 'none' else 1.0 if edge == 'ch1.0' else 0.5
        for a_, cx, cz in cen:
            r0 = 1.9 if a_ in (-142.0, 38.0) else 2.15
            nm = ('TOP_CH_%+.0f' % a_).replace('+', 'p').replace('-', 'm')
            if ch:
                with Sk(d, plane(d, 'Z', cz, 'P_' + nm), nm) as s_c:
                    s_c.poly([(cx + r0 - 0.05, top + 0.05, cz), (cx + r0 + ch, top + 0.05, cz), (cx + r0 + ch, top, cz), (cx + r0, top - ch, cz), (cx + r0 - 0.05, top - ch, cz)])
                    s_c.cline((cx, top - 5.0, cz), (cx, top + 5.0, cz))
                revolve(d, s_c.feat, nm, cut=True, lo=0.05)
            if edge == 'relief':
                with Sk(d, plane(d, 'Z', cz, 'P_' + nm), nm.replace('TOP_CH', 'TOP_REL')) as s_c:
                    s_c.poly([(cx + r0 + ch - 0.05, top + 0.05, cz), (cx + r0 + ch + 1.0, top + 0.05, cz), (cx + r0 + ch + 1.0, top - 0.2, cz), (cx + r0 + ch - 0.05, top - 0.2, cz)])
                    s_c.cline((cx, top - 5.0, cz), (cx, top + 5.0, cz))
                revolve(d, s_c.feat, nm.replace('TOP_CH', 'TOP_REL'), cut=True, lo=0.05)
        log(f'  seat-face hole edges: {edge}')
        RF = float(os.environ.get('TOP_FILLET', '2.0'))      # R 3 costs about 13 deg of cable travel against R 2 (the innermost wire nests in it)
        pz = plane(d, 'Z', YZ, 'P_Z_YZ')
        for sense in (-1, 1):
            va = vol(d)
            with Sk(d, pz, 'STEP_FILLET') as s_f:
                sm_ = d.SketchManager
                Pt = lambda r_, y_: s_f.p((RX + r_, y_, YZ))
                A_, B_, E1, E2, C_, O_ = (Pt(DISH_R0 - 0.05, DISH_Y - 0.06), Pt(DISH_R0 + RF, DISH_Y - 0.06), Pt(DISH_R0 + RF, DISH_Y), Pt(DISH_R0, DISH_Y + RF),
                                          Pt(DISH_R0 - 0.05, DISH_Y + RF), Pt(DISH_R0 + RF, DISH_Y + RF))
                for u_, v_ in ((A_, B_), (B_, E1), (E2, C_), (C_, A_)):
                    sm_.CreateLine(u_[0], u_[1], 0, v_[0], v_[1], 0)
                sm_.CreateArc(O_[0], O_[1], 0, E1[0], E1[1], 0, E2[0], E2[1], 0, sense)
                s_f.cline((RX, 280.0, YZ), (RX, 330.0, YZ))
            try:
                revolve(d, s_f.feat, 'STEP_FILLET', lo=0.5)
            except SystemExit:
                d.EditUndo2(1)
                continue
            if vol(d) - va < 400.0:
                break
            log(f'  STEP_FILLET sense {sense}: added {vol(d) - va:.0f} mm3, the long way round: undone')
            d.EditUndo2(2)
            d.ForceRebuild3(False)
        log(f'  taller centre +{h}: top face Y {top:.2f}, added {vol(d) - v5:.0f} mm3')
    log(f'  total added {vol(d) - v0:.0f} mm3')
    if h and os.environ.get('NO_MOVE') != '1':      # NO_MOVE=1: an FE copy, left in the arm's coordinates
        # the same solid twice: first as built, in the arm's present coordinates (for the arm thread's comparison with
        # the released hub), then moved down the yaw axis by h, where it sits in the assembly (top face back on the RS02's
        # output face at Y 319.86); the part file and the exports of record are the moved one
        d.ForceRebuild3(False)
        export(d, STL / 'hub_armframe.stl')
        export(d, STEPD / 'hub_armframe.step', stl_fine=False)
        bd = d.GetBodies2(0, True)[0]
        d.ClearSelection2(True)
        sd_ = d.SelectionManager.CreateSelectData
        sd_.Mark = 1
        ok_ = bd.Select2(False, sd_)
        f_mv = d.FeatureManager.InsertMoveCopyBody2(0.0, -h * m, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 1)
        d.ForceRebuild3(False)
        bx_ = d.GetBodies2(0, True)[0].GetBodyBox
        bx_ = bx_() if inspect.ismethod(bx_) else bx_
        log(f'  moved {-h} in Y: selected {ok_}, feature {f_mv is not None}, body Y {bx_[1] * 1e3:.2f} to {bx_[4] * 1e3:.2f}')
        if f_mv is None or abs(bx_[4] * 1e3 - RS02_OUT) > 0.01:
            raise SystemExit('move to the assembly frame failed')
        f_mv.Name = 'TO_ASSEMBLY_FRAME'
    finish_part(d, 'hub', dict(Note='Candidate 2: solid pocket, small dog-leg cable slot, thicker top'))
    finish()


if __name__ == '__main__':
    main()
