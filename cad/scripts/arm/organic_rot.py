"""Concept A rotating lower forearm, layout A2 (chosen 2026-11-10). Arm frame, mm; forearm (yaw) axis along Y through
X 170.49, Z 5.99; angles a about it measured from +X towards +Z (a 270 is the back).

The RS00 stays in the static belly. Below the belly rim the whole lower forearm turns on two 6808-2RS back to back on a
static stub, driven by the RS00 output through the stub bore:

  stub_ring      static. Replaces the draft 4 RS00 ring: bolted to the RS00 housing (6 x M3 on Ø50, heads in counterbores
                 underneath) and to the belly rim inserts (6 x M3 on r 32.6, heads underneath); the stub (Ø40 x 14) below it
                 carries both inner races, bonded (retaining compound) against its shoulder. A stop lug hangs under it at
                 a 30; a slot at the back takes the ribbon up to the rim's cable channel.
  hub            turns. Bore Ø52.1 for both outer races under a top shoulder; flange below with 6 axial inserts for the drive
                 plate and 2 radial inserts for the shell halves. The stop tab on its top meets the lug at +-170 deg.
  drive_shaft    turns. Flange on the RS00 output (6 x M3 on Ø27), Ø24/18 tube down the stub bore, flange under the drive
                 plate (3 x M3 from below into plate inserts). A back window lets the ribbon into its bore.
  drive_plate    turns. Closes the hub, presses a Ø52 wave washer up under the lower outer race (the preload: it pushes both
                 outer races up while the bonded inner races sit on the stub shoulder), and carries the shaft.
  wrist_plate    turns. The hand face: Ø66, 6 x M3 heat-set on Ø50, Ø35 pilot 2 deep, Ø3 clocking pin, Ø24 opening; 6 inserts
                 on its top face for a future motor pack; 2 radial inserts for the shell halves.
  shell_lower_front / _back   turn. The cone-and-cuff skin, 2 mm, split front and back (Z 5.99), one radial
                 screw at the hub and one at the wrist plate per half, a tongue down the seam. Taking one half off opens the bay.

The ribbon (48 V and CAN only) coils in the stub bore between the shaft (r 12) and the stub (r 17), Y 68-82: static end out
through the ring's back slot, turning end into the shaft through its window and down the shaft bore into the bay.

    python organic_rot.py [stub_ring hub drive_shaft drive_plate wrist_plate shell]
"""
import math
import sys
from pathlib import Path

import numpy as np

import organic_master as M
from organic_master import CZ, HX, x_holes, y_revolve, fine_stl, sw
from swg import *

CAD = M.CAD
DIR = CAD / 'forearm'
EXP = CAD / 'exports' / 'forearm'
Y_RING = (84.3, 90.3)             # stub ring (the old RS00 ring's place)
Y_BRG = ((75.0, 82.0), (68.0, 75.0))   # upper, lower 6808 (Ø40 / Ø52 x 7)
Y_SHOULDER = 82.0                  # stub shoulder under the upper inner race
Y_STUB_END = 67.5
HUB = dict(bore=26.05, top=83.5, r_out=30.0, flange=(60.0, 67.0), r_flange=33.0)
WAVE = (67.2, 68.0)               # wave washer under the lower outer race
PLATE = dict(y0=57.0, y1=60.0, hub_top=67.2, r_hole=12.2)
SHAFT = dict(r_in=9.0, r_out=12.0, top=(86.0, 89.9), bottom=(58.0, 61.0))
WRIST = dict(face=14.9, top=22.0, r=33.0, rim_in=21.0, plate_top=18.9, opening=12.0, pilot=17.5, pilot_d=2.0)
SHELL = dict(top=84.0, cone_end=24.4, r_top=36.0, r_cone=34.0, r_cuff=35.2, t=2.0)
LUG_A, TAB_A, STOP_SPAN = 30.0, 210.0, 10.0
SLOT = (258.0, 282.0)
H_SCREWS = [0.0 + 60.0 * k for k in range(6)]       # RS00 housing (r 25) and rim (r 32.6) screws, as draft 4
OUT_SCREWS = [30.0 + 60.0 * k for k in range(6)]    # RS00 output, r 13.5


def pa(r, a):
    t = math.radians(a)
    return HX + r * math.cos(t), CZ + r * math.sin(t)


def arc_y(d, name, r0, r1, a0, a1, y0, y1, cut, n=40):
    ym = (y0 + y1) / 2
    pts = [pa(r1, a) for a in np.linspace(a0, a1, n)] + [pa(r0, a) for a in np.linspace(a1, a0, n)]
    with Sk(d, plane(d, 'Y', ym, name + '_P'), name) as s:
        s.poly([(x, ym, z) for x, z in pts])
    return feat(d, s.feat, name, abs(y1 - y0), cut, mode=MID, lo=0.01)


def holes_y(d, name, pts, rad, y0, y1, cut=True):
    ym = (y0 + y1) / 2
    with Sk(d, plane(d, 'Y', ym, name + '_P'), name) as s:
        for r, a in pts:
            x, z = pa(r, a)
            s.circle((x, ym, z), rad)
    return feat(d, s.feat, name, abs(y1 - y0), cut, mode=MID, lo=0.01)


def z_holes(d, name, pts, rad, z0, z1, cut=True):
    """Holes along Z through (X, Y) points, between Z z0 and z1."""
    zm = (z0 + z1) / 2
    with Sk(d, plane(d, 'Z', zm, name + '_P'), name) as s:
        for x, y in pts:
            s.circle((x, y, zm), rad)
    return feat(d, s.feat, name, abs(z1 - z0), cut, mode=MID, lo=0.01)


def save(d, name):
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    if len(bodies(d)) != 1:
        raise SystemExit(f'{name}: expected one body')
    e, w = L(), L()
    d.Save3(1, e, w)
    for ext in ('.stl', '.step'):
        d.Extension.SaveAs(str(EXP / (name + ext)), 0, 1, NUL, e, w)
    fine_stl(d, M.WIP / f'{name}.stl')
    sw.CloseDoc(d.GetTitle)


def stub_ring():
    name = 'forearm_organic_stub_ring_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    y_revolve(d, 'RING', [(20.0, Y_RING[0]), (36.0, Y_RING[0]), (36.0, Y_RING[1]), (20.0, Y_RING[1])])
    y_revolve(d, 'SHOULDER', [(17.0, Y_SHOULDER), (20.5, Y_SHOULDER), (23.0, Y_SHOULDER + 0.6), (23.0, Y_RING[0] + 0.2), (17.0, Y_RING[0] + 0.2)])
    y_revolve(d, 'STUB', [(17.0, Y_STUB_END), (20.0, Y_STUB_END), (20.0, Y_SHOULDER + 0.1), (17.0, Y_SHOULDER + 0.1)])
    holes_y(d, 'HOUSING_SCREWS', [(25.0, a) for a in H_SCREWS], 1.7, Y_RING[0] - 1, Y_RING[1] + 1)
    holes_y(d, 'HOUSING_CBORES', [(25.0, a) for a in H_SCREWS], 2.85, Y_RING[0] - 1, Y_RING[0] + 1.8)
    holes_y(d, 'RIM_SCREWS', [(32.6, a) for a in H_SCREWS], 1.7, Y_RING[0] - 1, Y_RING[1] + 1)
    arc_y(d, 'RIBBON_SLOT', 16.5, 33.5, SLOT[0], SLOT[1], Y_SHOULDER + 0.2, Y_RING[1] + 1, True)
    arc_y(d, 'STOP_LUG', 30.5, 33.0, LUG_A - STOP_SPAN / 2, LUG_A + STOP_SPAN / 2, 80.5, Y_RING[0] + 0.05, False)
    save(d, name)


def hub():
    name = 'forearm_organic_hub_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    f0, f1 = HUB['flange']
    y_revolve(d, 'HUB', [(HUB['bore'], f0), (HUB['r_flange'], f0), (HUB['r_flange'], f1), (HUB['r_out'], f1), (HUB['r_out'], HUB['top']),
                         (23.5, HUB['top']), (23.5, Y_BRG[0][1]), (HUB['bore'], Y_BRG[0][1])])
    arc_y(d, 'STOP_TAB', 29.9, 33.0, TAB_A - STOP_SPAN / 2, TAB_A + STOP_SPAN / 2, 80.5, HUB['top'], False)
    holes_y(d, 'PLATE_INSERTS', [(28.5, a) for a in H_SCREWS], 2.0, f0 - 0.01, f0 + 6.0)
    z_holes(d, 'SHELL_INSERTS', [(HX, (f0 + f1) / 2)], 2.0, CZ - HUB['r_flange'] - 0.5, CZ - HUB['r_flange'] + 6.0)
    z_holes(d, 'SHELL_INSERTS2', [(HX, (f0 + f1) / 2)], 2.0, CZ + HUB['r_flange'] - 6.0, CZ + HUB['r_flange'] + 0.5)
    save(d, name)


def drive_shaft():
    name = 'forearm_organic_drive_shaft_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    t0, t1 = SHAFT['top']
    b0, b1 = SHAFT['bottom']
    y_revolve(d, 'SHAFT', [(SHAFT['r_in'], b0), (16.5, b0), (16.5, b1), (SHAFT['r_out'], b1), (SHAFT['r_out'], t0),
                           (19.4, t0), (19.4, t1), (SHAFT['r_in'], t1)])
    holes_y(d, 'OUTPUT_SCREWS', [(13.5, a) for a in OUT_SCREWS], 1.7, t0 - 1, t1 + 1)
    holes_y(d, 'PLATE_SCREWS', [(14.25, a) for a in (90.0, 210.0, 330.0)], 1.7, b0 - 1, b1 + 1)
    arc_y(d, 'RIBBON_WINDOW', 8.5, 12.5, 255.0, 285.0, 70.0, 81.0, True)
    save(d, name)


def drive_plate():
    name = 'forearm_organic_drive_plate_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    y_revolve(d, 'PLATE', [(PLATE['r_hole'], SHAFT['bottom'][1]), (22.0, SHAFT['bottom'][1]), (22.0, PLATE['y0']), (HUB['r_flange'], PLATE['y0']),
                           (HUB['r_flange'], PLATE['y1']), (HUB['bore'] - 0.1, PLATE['y1']), (HUB['bore'] - 0.1, PLATE['hub_top']),
                           (PLATE['r_hole'], PLATE['hub_top'])])
    holes_y(d, 'HUB_SCREWS', [(28.5, a) for a in H_SCREWS], 1.7, PLATE['y0'] - 1, PLATE['y1'] + 1)
    holes_y(d, 'SHAFT_INSERTS', [(14.25, a) for a in (90.0, 210.0, 330.0)], 2.0, SHAFT['bottom'][1] - 0.01, SHAFT['bottom'][1] + 5.9)
    save(d, name)


def wrist_plate():
    name = 'forearm_organic_wrist_plate_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    w = WRIST
    y_revolve(d, 'PLATE', [(w['opening'], w['face']), (w['r'], w['face']), (w['r'], w['top']), (w['rim_in'], w['top']),
                           (w['rim_in'], w['plate_top']), (w['opening'], w['plate_top'])])
    y_revolve(d, 'PILOT', [(w['opening'] - 0.1, w['face'] - 1), (w['pilot'], w['face'] - 1), (w['pilot'], w['face'] + w['pilot_d']),
                           (w['opening'] - 0.1, w['face'] + w['pilot_d'])], cut=True)
    holes_y(d, 'HAND_INSERTS', [(25.0, a) for a in H_SCREWS], 2.0, w['face'] - 0.01, w['face'] + 6.0)
    holes_y(d, 'CLOCK_PIN', [(25.0, 30.0)], 1.55, w['face'] - 0.01, w['face'] + 4.0)
    holes_y(d, 'PACK_INSERTS', [(24.0, a + 15.0) for a in H_SCREWS], 2.0, w['top'] - 6.0, w['top'] + 0.01)
    yr = 18.4                                    # in the plate (Y 14.9-22 at r 21-33)
    z_holes(d, 'SHELL_INSERTS', [(HX, yr)], 2.0, CZ - w['r'] - 0.5, CZ - w['r'] + 6.0)
    z_holes(d, 'SHELL_INSERTS2', [(HX, yr)], 2.0, CZ + w['r'] - 6.0, CZ + w['r'] + 0.5)
    save(d, name)


def shell():
    """Both halves from one revolved skin, cut on the seam plane X 170.49."""
    s = SHELL
    t = s['t']
    yh = sum(HUB['flange']) / 2
    yw = 18.4
    prof = [(s['r_top'], s['top']), (s['r_cone'], s['cone_end']), (s['r_cuff'], s['cone_end']), (s['r_cuff'], WRIST['face']),
            (WRIST['r'] + 0.2, WRIST['face']), (WRIST['r'] + 0.2, WRIST['top']), (s['r_cone'] - t, WRIST['top'] + 1.0),
            (s['r_cone'] - t + 0.0, s['cone_end'] + 2.0), (HUB['r_flange'] + 0.2, HUB['flange'][0]), (HUB['r_flange'] + 0.2, HUB['flange'][1]),
            (s['r_top'] - t, s['top'])]
    for side, keep in (('back', -1), ('front', 1)):
        name = f'forearm_organic_shell_lower_{side}_left'
        d = M.new_part(DIR / (name + '.SLDPRT'))
        y_revolve(d, 'SKIN', prof)
        # keep one half: cut away the other side of X 170.49
        c = CZ - keep * 75.0
        with Sk(d, plane(d, 'Z', c, 'OTHER_P'), 'OTHER') as sk:
            sk.poly([(HX - 200.0, 0.0, c), (HX + 200.0, 0.0, c), (HX + 200.0, 120.0, c), (HX - 200.0, 120.0, c)])
        feat(d, sk.feat, 'OTHER', 150.0, True, mode=MID)
        # radial screws: one into the hub flange, one into the wrist plate (button heads sit on the 2 mm skin)
        for nm, yy, r_in in (('TOP', yh, HUB['r_flange'] + 0.2), ('BOT', yw, WRIST['r'] + 0.2)):
            z_in, z_out = CZ + keep * (r_in - 0.5), CZ + keep * (r_in + 4.0)
            z_holes(d, f'{nm}_HOLE', [(HX, yy)], 1.7, min(z_in, z_out), max(z_in, z_out))
        save(d, name)


def fea_rot():
    """FEA model of the turning section as one body: hub, drive plate, both shell halves (gaps closed) and the wrist plate."""
    sim = CAD / '_sim' / 'forearm'
    sim.mkdir(parents=True, exist_ok=True)
    d = M.new_part(sim / 'ROT_A2_v1.SLDPRT')
    s_, t = SHELL, SHELL['t']
    f0, f1 = HUB['flange']
    y_revolve(d, 'SKIN', [(s_['r_top'], s_['top']), (s_['r_cone'], s_['cone_end']), (s_['r_cuff'], s_['cone_end']), (s_['r_cuff'], WRIST['face']),
                          (WRIST['r'], WRIST['face']), (WRIST['r'], WRIST['top']), (s_['r_cone'] - t, WRIST['top'] + 1.0), (s_['r_cone'] - t, s_['cone_end'] + 2.0),
                          (HUB['r_flange'], f0), (HUB['r_flange'], f1), (s_['r_top'] - t, s_['top'])])
    y_revolve(d, 'HUB', [(HUB['bore'], f0), (HUB['r_flange'], f0), (HUB['r_flange'], f1), (HUB['r_out'], f1), (HUB['r_out'], HUB['top']),
                         (23.5, HUB['top']), (23.5, Y_BRG[0][1]), (HUB['bore'], Y_BRG[0][1])])
    y_revolve(d, 'PLATE', [(PLATE['r_hole'], SHAFT['bottom'][1]), (22.0, SHAFT['bottom'][1]), (22.0, PLATE['y0']), (HUB['r_flange'], PLATE['y0']),
                           (HUB['r_flange'], PLATE['y1']), (HUB['bore'] - 0.1, PLATE['y1']), (HUB['bore'] - 0.1, PLATE['hub_top']), (PLATE['r_hole'], PLATE['hub_top'])])
    w = WRIST
    y_revolve(d, 'WRIST', [(w['opening'], w['face']), (w['r'], w['face']), (w['r'], w['top']), (w['rim_in'], w['top']),
                           (w['rim_in'], w['plate_top']), (w['opening'], w['plate_top'])])
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    e, w_ = L(), L()
    d.Save3(1, e, w_)
    sw.CloseDoc(d.GetTitle)


if __name__ == '__main__':
    for k in sys.argv[1:] or ('stub_ring', 'hub', 'drive_shaft', 'drive_plate', 'wrist_plate', 'shell'):
        print('==', k, flush=True)
        globals()[k]()
