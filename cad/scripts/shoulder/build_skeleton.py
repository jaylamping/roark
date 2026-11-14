"""Left shoulder skeleton: the three joint axes, the motor faces and the interface sketches, in the torso frame.

    python build_skeleton.py

Saves cad/shoulder/left/shoulder_skeleton_left.SLDPRT (no solid bodies). Every printed part is modelled in the same
frame, so the parts, the motors and this skeleton all line up at the assembly origin.
"""
import math

from dims import *
from swk import *


def cc(s, c, r):
    seg = s.circle(c, r)
    seg.ConstructionGeometry = True
    return seg


def main():
    d = new_part(OUT / 'shoulder_skeleton_left.SLDPRT')
    px, py, pzp, pzy = plane(d, 'X', RX, 'P_X_RX'), plane(d, 'Y', RY, 'P_Y_RY'), plane(d, 'Z', PZ, 'P_Z_PZ'), plane(d, 'Z', YZ, 'P_Z_YZ')
    ref_axis(d, py, pzp, 'PITCH_AXIS')
    ref_axis(d, px, py, 'ROLL_AXIS')
    ref_axis(d, px, pzy, 'YAW_AXIS')
    faces = [('X', PITCH_OUT, 'PITCH_RS03_OUTPUT'), ('X', PITCH_REAR, 'PITCH_RS03_REAR'), ('X', 75.0, 'CAGE_SIDE'),
             ('Z', ROLL_OUT, 'ROLL_RS03_OUTPUT'), ('Z', ROLL_REAR, 'ROLL_RS03_REAR'), ('Z', DRUM_Z0, 'CAP_FRONT'), ('Z', CAP_Z1, 'CAP_REAR'),
             ('Z', BRG_Z[0], 'BRG_6808_FRONT'), ('Y', RS02_SEAT, 'RS02_SEAT'), ('Y', RS02_REAR, 'RS02_REAR'), ('Y', RS02_OUT, 'RS02_OUTPUT')]
    for ax, off, name in faces:
        plane(d, ax, off, name)

    def sk(pl, name, draw):
        with Sk(d, pl, name) as s:
            draw(s)

    # pitch output -> drum pad: 6 x M4 on PCD 30.4
    def pad(s):
        cc(s, (PITCH_OUT, RY, PZ), 15.2)
        for a in PAD_HOLES:
            s.circle(pitch_pt(15.2, a, PITCH_OUT), 2.25)
        cc(s, (PITCH_OUT, RY, PZ), PAD_R)
    sk(d.FeatureByName('PITCH_RS03_OUTPUT'), 'IF_PITCH_PAD', pad)

    # roll RS03 housing -> drum lip: 8 x M4 on PCD 98, lug slots
    def lip(s):
        cc(s, (RX, RY, LIP_Z0), LIP_PCD_R)
        for a in LUG_ANGLES:
            s.circle(roll_pt(LIP_PCD_R, a, LIP_Z0), 2.25)
        cc(s, (RX, RY, LIP_Z0), DRUM_RI)
    sk(plane(d, 'Z', LIP_Z0, 'LIP_FACE'), 'IF_ROLL_LIP', lip)

    # roll output -> fork front boss: 6 x M4 on PCD 30.4; keep inside r 27 at the face (stationary ring r 28-35)
    def rout(s):
        cc(s, (RX, RY, ROLL_OUT), 15.2)
        for k in range(6):
            s.circle(roll_pt(15.2, 30 + 60 * k, ROLL_OUT), 2.25)
        cc(s, (RX, RY, ROLL_OUT), 27.0)
    sk(d.FeatureByName('ROLL_RS03_OUTPUT'), 'IF_ROLL_OUTPUT', rout)

    # cap ears 3 x M4 at r 61
    def ears(s):
        cc(s, (RX, RY, DRUM_Z0), EAR_PCD)
        for a in EAR_ANGLES:
            s.circle(roll_pt(EAR_PCD, a, DRUM_Z0), 2.25)
    sk(d.FeatureByName('CAP_FRONT'), 'IF_CAP_EARS', ears)

    # RS02 rear -> fork seat ring: 5 x M3 on PCD 73, seat ring r 33.5-45
    def seat(s):
        cc(s, (RX, RS02_SEAT, YZ), 36.5)
        for a in RS02_SCREWS:
            s.circle(yaw_pt(36.5, a, RS02_SEAT), 1.8)
        cc(s, (RX, RS02_SEAT, YZ), SEAT_RI)
        cc(s, (RX, RS02_SEAT, YZ), SEAT_RO)
    sk(d.FeatureByName('RS02_SEAT'), 'IF_RS02_SEAT', seat)

    # RS02 output -> hub: 6 x M4 on PCD 24; hub spigot r 35.8 (frozen)
    def hub(s):
        cc(s, (RX, RS02_OUT, YZ), 12.0)
        cc(s, (RX, RS02_OUT, YZ), 35.8)
        cc(s, (RX, RS02_OUT, YZ), DISH_R0)
    sk(d.FeatureByName('RS02_OUTPUT'), 'IF_HUB', hub)

    # 6808-2RS on the cap stub (sagittal section through the roll axis): stub OD 40, bore 25, bearing 40 x 52 x 7
    def brg(s):
        for sg in (1, -1):
            s.poly([(RX + sg * 20.0, RY, BRG_Z[0]), (RX + sg * 26.0, RY, BRG_Z[0]), (RX + sg * 26.0, RY, BRG_Z[1]), (RX + sg * 20.0, RY, BRG_Z[1])])
            s.line((RX + sg * STUB_BORE, RY, DRUM_Z0 + 1), (RX + sg * STUB_BORE, RY, BRG_Z[1] - 1))
        s.cline((RX, RY, 60.0), (RX, RY, -70.0))
    sk(plane(d, 'Y', RY, 'P_Y_RY'), 'IF_6808_SECTION', brg)

    # roll stops: arm centrelines at the two stops (reference only; the cap's ROLL_STOP_IN / ROLL_STOP_OUT drive the lugs)
    def stops(s):
        for phi in (ROLL_STOP_IN, 0.0, ROLL_STOP_OUT):
            s.cline((RX, RY, RZ), roll_pt(70.0, phi - 90.0, RZ))
    sk(plane(d, 'Z', RZ, 'P_Z_RZ'), 'REF_ROLL_STOPS', stops)

    # wire passage sections (power 16 x 6, signal 10 x 5) at the trunk mouth and in the fork rear arm
    def mouth(s):
        s.poly(rect_pts((NECK['x0'], TRUNK_Y, P_OFF), (0, 0, 1), (0, 1, 0), PW, PH))
        s.poly(rect_pts((NECK['x0'], TRUNK_Y, S_OFF), (0, 0, 1), (0, 1, 0), SW, SH))
    sk(plane(d, 'X', NECK['x0'], 'TRUNK_MOUTH'), 'PASS_TRUNK_MOUTH', mouth)

    def armsec(s):
        s.poly(rect_pts((RX + P_OFF, 400.0, RZ), (1, 0, 0), (0, 0, 1), PW, PH))
        s.poly(rect_pts((RX + S_OFF, 400.0, RZ), (1, 0, 0), (0, 0, 1), SW, SH))
    sk(plane(d, 'Y', 400.0, 'P_Y_400'), 'PASS_FORK_ARM', armsec)

    stamp_props(d, dict(Description='Left shoulder skeleton: axes, motor faces, interfaces (torso frame, mm)',
                        Stops=f'roll {ROLL_STOP_IN:g} / +{ROLL_STOP_OUT:g} deg, set in shoulder_roll_cap_left (ROLL_STOP_IN, ROLL_STOP_OUT)'))
    save(d)
    app().CloseDoc(d.GetTitle)


if __name__ == '__main__':
    main()
