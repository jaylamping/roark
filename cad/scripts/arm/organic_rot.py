"""Concept A rotating lower forearm, layout A2 (chosen 2026-11-10). Arm frame, mm; forearm (yaw) axis along Y through
X 170.49, Z 5.99; angles a about it measured from +X towards +Z (a 270 is the back). The static/turning boundary sits at
Y 92.3, 8 mm above the old rim, so the bay has room for a ring of 12 N20-class gearmotors.

The RS00 stays in the static belly. Below the belly the whole lower forearm turns on two 6808-2RS back to back on a static
stub, driven by the RS00 output through the stub bore. No adhesive anywhere; everything comes apart.

  stub_ring    static. Bolted to the RS00 housing (6 x M3 on Ø50, heads in counterbores underneath) and to the belly rim
               inserts (6 x M3 on r 32.6); the Ø40 stub below it carries both inner races, clamped by the nut against its
               shoulder. Its lower end (Y 70-76) carries the M40 x 1.5 thread for the nut (modelled as Ø40; thread cut at print
               prep). A stop lug hangs under it at a 30; a slot at the back takes the ribbon up to the belly's cable channel.
  stub_nut     static. Printed M40 x 1.5 nut, clamps both inner races up against the stub shoulder.
  drive_shaft  turns. Flange on the RS00 output (6 x M3 on Ø27, fitted on the bench before the stub ring goes on), Ø21/15
               tube down the stub bore, three dogs at its foot into the drive plate. A back window lets the ribbon into its bore.
  hub          turns. Bore Ø52.1 for both outer races under a top shoulder; flange below with 6 axial inserts for the drive
               plate and 2 radial inserts for the shell halves. The stop tab on its top meets the lug at +-170 deg.
  drive_plate  turns. Closes the hub, presses a Ø52 wave washer up under the lower outer race (the preload: both outer races
               pushed up while the clamped inner races sit on the stub shoulder), and takes the shaft's dogs.
  wrist_plate  turns. The hand face: Ø66, 6 x M3 heat-set on Ø50, Ø35 pilot 2 deep, Ø3 clocking pin, Ø24 opening; 6 inserts
               on its top face for a future motor pack; 2 radial inserts for the shell halves.
  shell_lower_front / _back   turn. The cone-and-cuff skin, 2 mm, split front and back (Z 5.99), one radial screw at the hub
               and one at the wrist plate per half. Taking one half off opens the bay.

The ribbon (48 V and CAN) coils in the stub bore between the shaft (r 10.5) and the stub (r 17), Y 77-89: static end out
through the ring's back slot, turning end into the shaft through its window and down the shaft bore into the bay.

    python organic_rot.py [stub_ring stub_nut drive_shaft hub drive_plate wrist_plate shell fea_rot]
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
Y_RING = (92.3, 98.3)
Y_BRG = ((83.0, 90.0), (76.0, 83.0))   # upper, lower 6808 (Ø40 / Ø52 x 7)
Y_SHOULDER = 90.0
THREAD = (70.0, 76.0)                  # stub end: M40 x 1.5 for the nut, bore r 15.5 there
HUB = dict(bore=26.05, top=91.5, r_out=30.0, flange=(68.0, 75.0), r_flange=33.0)
WAVE = (75.2, 76.0)
PLATE = dict(y0=65.0, y1=68.0, boss_top=75.2, r_hole=10.6)
SHAFT = dict(r_in=7.5, r_out=10.5, top=(94.0, 97.9), foot=65.0, dogs=(65.0, 68.0))
WRIST = dict(face=14.9, top=22.0, r=33.0, rim_in=21.0, plate_top=18.9, opening=12.0, pilot=17.5, pilot_d=2.0)
SHELL = dict(top=92.0, cone_end=24.4, r_top=36.0, r_cone=34.0, r_cuff=35.2, t=2.0)
LUG_A, TAB_A, STOP_SPAN = 30.0, 210.0, 10.0
SLOT = (258.0, 282.0)
H_SCREWS = [0.0 + 60.0 * k for k in range(6)]       # RS00 housing (r 25) and rim (r 32.6) screws, as draft 4
OUT_SCREWS = [30.0 + 60.0 * k for k in range(6)]    # RS00 output, r 13.5
DOGS = [90.0, 210.0, 330.0]


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


def save(d, name, exports=True):
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    if len(bodies(d)) != 1:
        raise SystemExit(f'{name}: expected one body')
    e, w = L(), L()
    d.Save3(1, e, w)
    if exports:
        for ext in ('.stl', '.step'):
            d.Extension.SaveAs(str(EXP / (name + ext)), 0, 1, NUL, e, w)
        fine_stl(d, M.WIP / f'{name}.stl')
    sw.CloseDoc(d.GetTitle)


def stub_ring():
    name = 'forearm_organic_stub_ring_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    y_revolve(d, 'RING', [(20.0, Y_RING[0]), (36.0, Y_RING[0]), (36.0, Y_RING[1]), (20.0, Y_RING[1])])
    y_revolve(d, 'SHOULDER', [(17.0, Y_SHOULDER), (22.2, Y_SHOULDER), (22.2, Y_RING[0] + 0.2), (17.0, Y_RING[0] + 0.2)])
    y_revolve(d, 'STUB', [(17.0, THREAD[1] - 0.1), (20.0, THREAD[1] - 0.1), (20.0, Y_SHOULDER + 0.1), (17.0, Y_SHOULDER + 0.1)])
    y_revolve(d, 'THREAD_END', [(15.5, THREAD[0]), (20.0, THREAD[0]), (20.0, THREAD[1]), (15.5, THREAD[1])])
    holes_y(d, 'HOUSING_SCREWS', [(25.0, a) for a in H_SCREWS], 1.7, Y_RING[0] - 1, Y_RING[1] + 1)
    holes_y(d, 'HOUSING_CBORES', [(25.0, a) for a in H_SCREWS], 2.85, Y_RING[0] - 1, Y_RING[0] + 1.8)
    holes_y(d, 'RIM_SCREWS', [(32.6, a) for a in H_SCREWS], 1.7, Y_RING[0] - 1, Y_RING[1] + 1)
    arc_y(d, 'RIBBON_SLOT', 16.5, 33.5, SLOT[0], SLOT[1], Y_SHOULDER - 0.2, Y_RING[1] + 1, True)   # right through the shoulder
    arc_y(d, 'STOP_LUG', 30.5, 33.0, LUG_A - STOP_SPAN / 2, LUG_A + STOP_SPAN / 2, 88.5, Y_RING[0] + 0.05, False)
    # lighten the ring between its screw circles from below (hidden under the turning shell's top)
    for k, a in enumerate(H_SCREWS):
        arc_y(d, f'RING_POCKET{k}', 27.6, 30.4, a + 8.0, a + 52.0, Y_RING[0] - 0.5, Y_RING[0] + 3.5, True)
    save(d, name)


def stub_nut():
    name = 'forearm_organic_stub_nut_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    y_revolve(d, 'NUT', [(20.05, THREAD[0]), (22.0, THREAD[0]), (22.0, THREAD[1] - 0.05), (20.05, THREAD[1] - 0.05)])
    arc_y(d, 'WRENCH_SLOTS', 21.2, 22.5, 85.0, 95.0, THREAD[0] - 0.5, THREAD[0] + 1.5, True)     # spanner notch
    arc_y(d, 'WRENCH_SLOTS2', 21.2, 22.5, 265.0, 275.0, THREAD[0] - 0.5, THREAD[0] + 1.5, True)
    save(d, name)


def drive_shaft():
    name = 'forearm_organic_drive_shaft_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    t0, t1 = SHAFT['top']
    y_revolve(d, 'SHAFT', [(SHAFT['r_in'], SHAFT['foot']), (SHAFT['r_out'], SHAFT['foot']), (SHAFT['r_out'], t0),
                           (19.4, t0), (19.4, t1), (SHAFT['r_in'], t1)])
    for k, a in enumerate(DOGS):
        arc_y(d, f'DOG{k}', SHAFT['r_out'] - 0.1, 12.9, a - 10.0, a + 10.0, SHAFT['dogs'][0], SHAFT['dogs'][1], False)
    holes_y(d, 'OUTPUT_SCREWS', [(13.5, a) for a in OUT_SCREWS], 1.7, t0 - 1, t1 + 1)
    arc_y(d, 'RIBBON_WINDOW', 7.0, 11.0, 255.0, 285.0, 78.0, 88.0, True)
    save(d, name)


def hub():
    name = 'forearm_organic_hub_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    f0, f1 = HUB['flange']
    y_revolve(d, 'HUB', [(HUB['bore'], f0), (HUB['r_flange'], f0), (HUB['r_flange'], f1), (HUB['r_out'], f1), (HUB['r_out'], HUB['top']),
                         (23.5, HUB['top']), (23.5, Y_BRG[0][1]), (HUB['bore'], Y_BRG[0][1])])
    arc_y(d, 'STOP_TAB', 29.9, 33.0, TAB_A - STOP_SPAN / 2, TAB_A + STOP_SPAN / 2, 88.5, HUB['top'], False)
    holes_y(d, 'PLATE_INSERTS', [(29.5, a) for a in H_SCREWS], 2.0, f0 - 0.01, f0 + 6.0)      # 1.45 mm off the bearing bore
    z_holes(d, 'SHELL_INSERTS', [(HX, (f0 + f1) / 2)], 2.0, CZ - HUB['r_flange'] - 0.5, CZ - HUB['r_flange'] + 6.0)
    z_holes(d, 'SHELL_INSERTS2', [(HX, (f0 + f1) / 2)], 2.0, CZ + HUB['r_flange'] - 6.0, CZ + HUB['r_flange'] + 0.5)
    save(d, name)


def drive_plate():
    name = 'forearm_organic_drive_plate_left'
    d = M.new_part(DIR / (name + '.SLDPRT'))
    y_revolve(d, 'PLATE', [(PLATE['r_hole'], PLATE['y0']), (HUB['r_flange'], PLATE['y0']), (HUB['r_flange'], PLATE['y1']),
                           (HUB['bore'] - 0.1, PLATE['y1']), (HUB['bore'] - 0.1, PLATE['boss_top']), (23.5, PLATE['boss_top']),
                           (23.5, PLATE['y1']), (PLATE['r_hole'], PLATE['y1'])])
    for k, a in enumerate(DOGS):
        arc_y(d, f'DOG_SLOT{k}', PLATE['r_hole'] - 0.5, 13.2, a - 11.5, a + 11.5, PLATE['y0'] - 0.5, PLATE['y1'] + 0.5, True)
    holes_y(d, 'HUB_SCREWS', [(29.5, a) for a in H_SCREWS], 1.7, PLATE['y0'] - 1, PLATE['y1'] + 1)
    for k, a in enumerate(OUT_SCREWS):                  # lightening windows between the hub screws
        arc_y(d, f'WINDOW{k}', 15.0, 21.5, a - 18.0, a + 18.0, PLATE['y0'] - 0.5, PLATE['y1'] + 0.5, True)
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
    yr = 18.4
    z_holes(d, 'SHELL_INSERTS', [(HX, yr)], 2.0, CZ - w['r'] - 0.5, CZ - w['r'] + 6.0)
    z_holes(d, 'SHELL_INSERTS2', [(HX, yr)], 2.0, CZ + w['r'] - 6.0, CZ + w['r'] + 0.5)
    for k, a in enumerate(H_SCREWS):                    # lighten the rim from the top between the inserts (not over the shell inserts at 90 / 270)
        if not (a + 20.0 < 90.0 < a + 40.0 or a + 20.0 < 270.0 < a + 40.0):
            arc_y(d, f'RIM_POCKET{k}', 27.0, 31.5, a + 20.0, a + 40.0, w['top'] - 2.5, w['top'] + 0.5, True)
    save(d, name)


def shell_prof(close=False):
    s, t = SHELL, SHELL['t']
    g = 0.0 if close else 0.2
    return [(s['r_top'], s['top']), (s['r_cone'], s['cone_end']), (s['r_cuff'], s['cone_end']), (s['r_cuff'], WRIST['face']),
            (WRIST['r'] + g, WRIST['face']), (WRIST['r'] + g, WRIST['top']), (s['r_cone'] - t, WRIST['top'] + 1.0),
            (s['r_cone'] - t, s['cone_end'] + 2.0), (HUB['r_flange'] + g, HUB['flange'][0]), (HUB['r_flange'] + g, HUB['flange'][1]),
            (s['r_top'] - t, s['top'])]


def shell():
    """Both halves from one revolved skin, cut on Z 5.99."""
    yh = sum(HUB['flange']) / 2
    yw = 18.4
    for side, keep in (('back', -1), ('front', 1)):
        name = f'forearm_organic_shell_lower_{side}_left'
        d = M.new_part(DIR / (name + '.SLDPRT'))
        y_revolve(d, 'SKIN', shell_prof())
        c = CZ - keep * 75.0
        with Sk(d, plane(d, 'Z', c, 'OTHER_P'), 'OTHER') as sk:
            sk.poly([(HX - 200.0, 0.0, c), (HX + 200.0, 0.0, c), (HX + 200.0, 120.0, c), (HX - 200.0, 120.0, c)])
        feat(d, sk.feat, 'OTHER', 150.0, True, mode=MID)
        for nm, yy, r_in in (('TOP', yh, HUB['r_flange'] + 0.2), ('BOT', yw, WRIST['r'] + 0.2)):
            z_in, z_out = CZ + keep * (r_in - 0.5), CZ + keep * (r_in + 4.0)
            z_holes(d, f'{nm}_HOLE', [(HX, yy)], 1.7, min(z_in, z_out), max(z_in, z_out))
        save(d, name)


def fea_rot():
    """FEA model of the turning section as one body: hub, drive plate, shell (gaps closed) and wrist plate."""
    sim = CAD / '_sim' / 'forearm'
    sim.mkdir(parents=True, exist_ok=True)
    d = M.new_part(sim / 'ROT_A2_v2.SLDPRT')
    f0, f1 = HUB['flange']
    y_revolve(d, 'SKIN', shell_prof(close=True))
    y_revolve(d, 'HUB', [(HUB['bore'], f0), (HUB['r_flange'], f0), (HUB['r_flange'], f1), (HUB['r_out'], f1), (HUB['r_out'], HUB['top']),
                         (23.5, HUB['top']), (23.5, Y_BRG[0][1]), (HUB['bore'], Y_BRG[0][1])])
    y_revolve(d, 'PLATE', [(PLATE['r_hole'], PLATE['y0']), (HUB['r_flange'], PLATE['y0']), (HUB['r_flange'], PLATE['y1']),
                           (HUB['bore'] - 0.1, PLATE['y1']), (HUB['bore'] - 0.1, PLATE['boss_top']), (23.5, PLATE['boss_top']),
                           (23.5, PLATE['y1']), (PLATE['r_hole'], PLATE['y1'])])
    w = WRIST
    y_revolve(d, 'WRIST', [(w['opening'], w['face']), (w['r'], w['face']), (w['r'], w['top']), (w['rim_in'], w['top']),
                           (w['rim_in'], w['plate_top']), (w['opening'], w['plate_top'])])
    save(d, 'ROT_A2_v2', exports=False)


def fea_stub():
    """FEA model of the stub ring with its nut merged (the nut clamps the races; bonded here)."""
    sim = CAD / '_sim' / 'forearm'
    import shutil
    shutil.copy(DIR / 'forearm_organic_stub_ring_left.SLDPRT', sim / 'STUB_A2_v2.SLDPRT')


if __name__ == '__main__':
    for k in sys.argv[1:] or ('stub_ring', 'stub_nut', 'drive_shaft', 'hub', 'drive_plate', 'wrist_plate', 'shell', 'fea_rot', 'fea_stub'):
        print('==', k, flush=True)
        globals()[k]()
