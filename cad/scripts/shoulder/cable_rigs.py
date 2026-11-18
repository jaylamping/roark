"""Test rigs for the three shoulder cable crossings (checks/CABLE_RIGS.md). cadquery, no SolidWorks; every part prints flat
without support.

    python cable_rigs.py OUTDIR

  yaw    (second version of cable_loop_rig.py) the dish under the RS02 with the hub window as in hub D3c6 (slot clipped at
         15.7), a tie post beside each window standing in for the boss tube, and tie slots in the exit stub's roof: for
         the spiral with both ends clamped, and for the plain arc.
  roll   deck rig: the rear cap's cavity (boss r 24, outer wall r 43, 7.8 deep) with an outer anchor, and a lid with the
         fork's post (r 28-31) and its slot. on-axis rig: today's route, a dia 25 bore 18 mm long between two radial
         16 x 6 channels that turn against each other.
  pitch  the loop channel (inner wall r 57.4, outer wall r 73.5, 21.1 apart) as a fixed tray with a bottom slot and a
         guide finger, and a turning lid with the trunk mouth. A second tray and lid (_r75) have the outer wall at r 68.5:
         the 11.1 mm channel a 150 mm shell opening would leave.
"""
import math
import sys
from pathlib import Path

import cadquery as cq

import cable_loop_rig as Y1          # the first yaw rig: its helpers and its fork, boss and cap parts are reused

pt, sector, ring, box = Y1.pt, Y1.sector, Y1.ring, Y1.box


# ------------------------------------------------------------------------------------------------------------------ yaw
def yaw_slot(w):
    """Hub D3c6 slot in (r, rig Z): the 9 mm slot from the dish down to the bore, not cut inside 15.7 along its line."""
    p1, p0 = Y1.P1, Y1.P0
    ux, uz = p0[0] - p1[0], p0[1] - p1[1]
    ln = math.hypot(ux, uz); ux, uz = ux / ln, uz / ln
    nx, nz = uz, -ux
    a, b = (p1[0], p1[1]), (p0[0] + ux * 6, p0[1] + uz * 6)
    lo_in, up_in = (a[0] + nx * 4.5, a[1] + nz * 4.5), (a[0] - nx * 4.5, a[1] - nz * 4.5)
    lo_out, up_out = (b[0] + nx * 4.5, b[1] + nz * 4.5), (b[0] - nx * 4.5, b[1] - nz * 4.5)
    clip = 15.7
    t1 = (lo_in[0] - clip) / (lo_in[0] - up_in[0])
    q1 = (clip, lo_in[1] + (up_in[1] - lo_in[1]) * t1)                 # on the bore-end face
    t2 = (clip - up_in[0]) / (up_out[0] - up_in[0])
    q2 = (clip, up_in[1] + (up_out[1] - up_in[1]) * t2)                # on the upper edge
    s = cq.Workplane('XZ').polyline([lo_in, q1, q2, up_out, lo_out]).close().extrude(8.0, both=True)
    return s.rotate((0, 0, 0), (0, 0, 1), -w)


def yaw_hub():
    h = ring(0, Y1.R_RIM, -Y1.FLOOR_T, 0)
    for w in Y1.WINDOWS:
        h = h.union(sector(18.0, 36.5, w - 24, w + 24, -5.56, 0))
        h = h.union(sector(23.0, 27.0, w - 24, w + 24, -22.0, -5.56))
        # tie posts: the boss tubes beside the window (r 12, 30 deg either side), dia 9, down to the bore's lower end
        for da in (-30.0, 30.0):
            x, y = pt(12.0, w + da)
            h = h.union(cq.Workplane('XY').workplane(offset=-22.0).center(x, y).circle(4.5).circle(2.6).extrude(22.0 - Y1.FLOOR_T + 0.2))
    for w in Y1.WINDOWS:
        h = h.cut(yaw_slot(w))
    h = h.union(sector(Y1.R_RIM - 0.5, 48.0, Y1.TAB_A - 4.0, Y1.TAB_A + 4.0, -0.8, 0))
    h = h.cut(ring(0, 2.15, -30, 10))
    for a in (158, 338):                                   # lightening, clear of the windows and posts
        x, y = pt(11.5, a)
        h = h.cut(cq.Workplane('XY').workplane(offset=-10).center(x, y).circle(5.0).extrude(20))
    return h


def yaw_fork(gap=5.5):
    """The fixed side for a dish `gap` deep (5.5 as built; 7.0 for the 1.5 mm deeper dish): roof, skirt, yaw exit stub with
    tie slots, viewing slots, yaw scale, stops. The roof's hole (r 20.3) rides on the boss's spigot and rests on its
    shoulder, so the dish height is set by the boss."""
    rt, ro, rs = Y1.ROOF_T, Y1.R_OUT, Y1.R_SKIRT
    zt = gap + rt
    f = ring(20.3, ro, gap, zt)
    f = f.union(ring(rs, ro, 0.4, gap))
    for a0, a1 in ((-12.0, -4.6), (184.6, 192.0)):                         # stops at yaw +90 and -90 for the hub's tab
        f = f.union(sector(rs, ro, a0, a1, -Y1.FLOOR_T, 0.4))
    ex, ez = Y1.EXIT_X, Y1.EXIT_Z                                          # the exit keeps its height above the floor
    f = f.union(box(ex - 9.2, ex + 9.2, 40.6, 57.0, ez[0] - 1.2, zt))
    f = f.union(box(ex - 9.2, ex + 9.2, Y1.EXIT_Y0, 42.0, ez[1], gap))
    f = f.cut(box(ex - 8.0, ex + 8.0, Y1.EXIT_Y0 - 1.0, 58.0, ez[0], ez[1]))
    for a in range(15, 360, 30):
        if abs(a - 255) < 20:
            continue
        f = f.cut(box(26.0, 37.0, -1.0, 1.0, gap - 1, zt + 1).rotate((0, 0, 0), (0, 0, 1), -a))
    for yaw in range(-90, 91, 10):
        r0 = 36.0 if yaw % 90 == 0 else 39.5
        f = f.cut(box(r0, ro + 1, -0.35, 0.35, zt - 0.4, zt + 1).rotate((0, 0, 0), (0, 0, 1), -(Y1.TAB_A - yaw)))
    for yaw, txt in ((-90, '-90'), (0, '0'), (90, '+90')):
        x, y = pt(31.0, Y1.TAB_A - yaw + 9.0)
        f = f.cut(cq.Workplane('XY').workplane(offset=zt - 0.4).center(x, y).text(txt, 4.5, 1.0, kind='bold'))
    x, y = pt(31.0, Y1.TAB_A + 40.0)                                       # the dish depth, so the two fork parts can't be mixed up
    f = f.cut(cq.Workplane('XY').workplane(offset=zt - 0.4).center(x, y).text(f'{gap:g}', 4.5, 1.0, kind='bold'))
    for dx in (-6.5, 6.5):                                 # tie slots through the exit stub's roof: a tie round the bundle
        f = f.cut(box(ex + dx - 0.9, ex + dx + 0.9, 46.0, 50.0, ez[1] - 0.5, zt + 1))
    return f


def yaw_boss(gap=5.5):
    """The hub's step ring (r 23.5, 1.5 high), the RS02 rotor (r 21.8) up to the dish height, and above it a spigot
    (r 20.0) through the roof. The roof rests on the rotor's top, so this part sets the dish depth."""
    top = gap + Y1.ROOF_T + 0.2
    b = ring(18.6, Y1.R_STEP, 0, 1.5)
    b = b.union(ring(18.6, Y1.R_ROTOR, 0, gap))
    b = b.union(ring(18.6, 20.0, 0, top))
    b = b.union(ring(0, 5.0, 0, top))
    for a in (0, 120, 240):
        b = b.union(box(4.0, 19.0, -2.5, 2.5, 0, 1.2).rotate((0, 0, 0), (0, 0, 1), a))
    if gap > 6:                                            # a raised bar on one spoke marks the 7.0 boss
        b = b.union(box(6.0, 17.0, -0.5, 0.5, 1.2, 3.2))
    return b.cut(ring(0, 2.15, -1, 20))


def yaw_cap():
    """A flat disc that holds the fork part down on the boss; one M4 clamps cap, boss and hub."""
    c = ring(0, 26.0, 0, 1.0)
    for a in (60, 180, 300):
        x, y = pt(14.5, a)
        c = c.cut(cq.Workplane('XY').workplane(offset=-1).center(x, y).circle(7.0).extrude(3))
    return c.cut(ring(0, 2.15, -1, 2))


# ----------------------------------------------------------------------------------------------------------------- roll
DECK = dict(boss=24.0, wall=43.0, depth=7.8, post=(28.0, 31.0), post_half=7.0, travel=(-11.0, 110.0))


def roll_deck_tray():
    """The cap side: floor, boss, outer wall with the outer anchor's gap, on a centre pin."""
    d = DECK
    t = ring(d['boss'] - 2.5, 47.0, -1.2, 0)
    t = t.union(ring(d['boss'] - 1.6, d['boss'], 0, d['depth']))       # the boss as a thin wall
    for a in (30, 150, 270):
        t = t.union(box(3.0, d['boss'] - 1.0, -3.0, 3.0, -1.2, 0.6).rotate((0, 0, 0), (0, 0, 1), -a))
    t = t.union(ring(0, 6.0, -1.2, d['depth']))
    t = t.union(ring(d['wall'], d['wall'] + 1.6, 0, d['depth']))
    # outer anchor at 135 deg (where the trunk's spoke comes in): a 10 mm gap in the wall and a tie bar outside it
    t = t.cut(sector(d['wall'] - 0.5, d['wall'] + 3.0, 135 - 7.5, 135 + 7.5, 0, d['depth'] + 1))
    t = t.union(sector(d['wall'] + 4.0, d['wall'] + 6.0, 135 - 9, 135 + 9, -1.2, 3.0))
    t = t.union(sector(d['wall'], d['wall'] + 6.0, 135 - 14, 135 + 14, -1.2, 0))
    t = t.cut(ring(0, 2.15, -5, 20))
    # stops for the lid's tab: roll -11 and +110 (the tab is at lid angle 0; it reads roll as its tray angle + 11)
    for a0, a1 in ((-11.0 - 9.0, -11.0 - 4.2), (110.0 + 4.2, 110.0 + 9.0)):
        t = t.union(sector(47.0, 49.0, a0, a1, -1.2, d['depth'] + 2.0))
    return t


def roll_deck_lid():
    """The fork side: a lid over the deck with the post (r 28-31) standing into it, a slot beside the post for the cable
    to leave through, tie holes, viewing slots and a pointer tab."""
    d = DECK
    z0 = d['depth'] + 0.3
    l = ring(DECK['boss'] - 2.5, 46.0, z0, z0 + 1.0)
    for a in (90, 210, 330):
        l = l.union(box(3.0, DECK['boss'] - 1.0, -3.0, 3.0, z0, z0 + 1.0).rotate((0, 0, 0), (0, 0, 1), -a))
    l = l.union(ring(0, 6.0, z0, z0 + 1.0))
    l = l.union(sector(d['post'][0], d['post'][1], 270 - d['post_half'], 270 + d['post_half'], 0.4, z0))
    l = l.cut(sector(d['post'][0] - 0.2, d['post'][1] + 3.6, 270 + d['post_half'], 270 + d['post_half'] + 22, z0 - 0.5, z0 + 2))   # cable exit beside the post
    for a in (270 - 12, 270 + 34):                         # tie holes either side of the exit
        x, y = pt(33.0, a)
        l = l.cut(cq.Workplane('XY').workplane(offset=z0 - 1).center(x, y).circle(1.3).extrude(3))
    for a in range(15, 360, 30):
        if abs(a - 285) < 25:
            continue
        l = l.cut(box(26.5, 41.5, -1.0, 1.0, z0 - 1, z0 + 2).rotate((0, 0, 0), (0, 0, 1), -a))
    l = l.union(sector(45.5, 51.5, -3.5, 3.5, z0, z0 + 1.0))
    return l.cut(ring(0, 2.15, -5, 20))


def roll_axis_base():
    """Today's route, the cap's side: a dia 25 bore 18 mm long (centre to centre of the two channels) with a 16 x 6 radial
    channel across its lower end."""
    b = ring(12.5, 15.0, 0, 18.0)                          # the stub bore, dia 25; the upper channel starts at its top, so the
                                                           # two channel centres (Z 3 and Z 21) are 18 mm apart
    b = b.union(ring(0, 34.0, -0.8, 0))
    for a in range(0, 360, 10):                            # a tick every 10 deg on the floor's rim
        b = b.cut(box(31.0 if a % 30 else 28.0, 35.0, -0.3, 0.3, -0.4, 1).rotate((0, 0, 0), (0, 0, 1), -a))
    b = b.union(box(-9.2, 9.2, 0, 34.0, 0, 6.0))           # channel walls out to r 34
    b = b.cut(box(-8.0, 8.0, -12.5, 35.0, 0, 6.0))         # the channel, open at the top, running into the bore
    return b


def roll_axis_top():
    """The fork's side: a cap that turns on the stub's top, with its own 16 x 6 radial channel 18 mm above the lower one."""
    z0 = 18.0
    t = ring(0, 20.0, z0 + 6.0, z0 + 7.0)
    t = t.union(box(-9.2, 9.2, 0, 34.0, z0 + 6.0, z0 + 7.0))
    t = t.union(ring(15.3, 16.9, z0 - 3.0, z0 + 6.0))      # skirt over the stub's outside
    t = t.union(box(-9.2, 9.2, 0, 34.0, z0, z0 + 6.0))
    t = t.cut(box(-8.0, 8.0, -12.5, 35.0, z0, z0 + 6.0))
    t = t.cut(ring(0, 15.15, z0 - 4.0, z0))                # clear the stub's wall under the channel walls
    t = t.union(box(-0.6, 0.6, 34.0, 38.0, z0 + 6.0, z0 + 7.0))        # pointer, in line with the channel
    return t


# ---------------------------------------------------------------------------------------------------------------- pitch
RI, RO, AX = 57.4, 73.5, 21.1


def pitch_tray(ro=None):
    """The fixed side (the cover): floor, inner wall, outer wall with a slot at the bottom (270 deg) and a guide finger
    (a rounded lip the cable leaves the wall over), three spokes to a centre pin, and a clamp bar below the slot."""
    # ro: the outer wall's inside radius, for a narrower channel (the r 75 opening what-if: 68.5, a channel of 11.1). The
    # guide finger, the tongue's end and the clamp stay where they are, so only the outer wall moves in
    ro = ro or RO
    t = ring(RI - 2.0, ro + 1.0, -0.8, 0)
    t = t.union(ring(RI - 0.9, RI, 0, AX))
    t = t.union(ring(ro, ro + 0.9, 0, AX))
    t = t.cut(sector(ro - 0.5, ro + 3.0, 270 - 12, 270 + 12, 0, AX + 1))           # bottom slot in the outer wall, about 30 mm wide
    # tongue below the slot: the floor runs on 32 mm, with the guide finger and the fixed clamp's tie holes
    t = t.union(box(-36.0, 36.0, ro - 2.0, RO + 32.0, -0.8, 0))
    # guide finger: a round post R 10 the cable turns over as it leaves the inner wall and drops through the slot
    t = t.union(cq.Workplane('XY').center(12.0, RI + 13.4).circle(10.0).circle(8.8).extrude(AX))
    for x_ in (-31.0, -25.0):                                                       # fixed clamp: two tie holes
        t = t.cut(cq.Workplane('XY').workplane(offset=-2).center(x_, RO + 26.0).circle(1.3).extrude(4))
    for a in (30, 150, 270):
        t = t.union(box(4.0, RI - 1.0, -3.0, 3.0, -0.8, 0.8).rotate((0, 0, 0), (0, 0, 1), -a))
    t = t.union(ring(0, 7.0, -0.8, 3.0)).cut(ring(0, 2.15, -3, 30))
    return t


def pitch_lid(ro=None):
    """The moving side (the drum's flange): a ring over the channel with the trunk mouth (13 x 4) and tie holes at r 65,
    three spokes to the centre pin, viewing slots, and a pointer."""
    RO = ro or globals()['RO']      # a narrower channel: the ring, the trunk mouth (mid channel), the slots and the pointer follow
    z0 = AX + 0.3
    l = ring(RI - 2.0, RO + 1.0, z0, z0 + 0.8)
    x, y = pt((RI + RO) / 2 + 0.05, 90.0)
    l = l.cut(cq.Workplane('XY').workplane(offset=z0 - 1).center(x, y).rect(13.0, 4.0).extrude(3))
    for dx in (-10.0, 10.0):
        l = l.cut(cq.Workplane('XY').workplane(offset=z0 - 1).center(x + dx, y).circle(1.3).extrude(3))
    for a in range(0, 360, 20):
        if abs(a - 90) < 15:
            continue
        l = l.cut(box(RI + 1.5, RO - 1.5, -0.9, 0.9, z0 - 1, z0 + 2).rotate((0, 0, 0), (0, 0, 1), -a))
    for a in (90, 210, 330):
        l = l.union(box(4.0, RI - 1.0, -3.0, 3.0, z0, z0 + 0.8).rotate((0, 0, 0), (0, 0, 1), -a))
    l = l.union(ring(0, 7.0, 3.2, z0 + 0.8)).cut(ring(0, 2.15, -3, 30))
    l = l.union(sector(RO + 0.5, RO + 6.0, 87.0, 93.0, z0, z0 + 0.8))
    return l


def flip(p, top):
    return p.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, top))


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    zr = Y1.GAP + Y1.ROOF_T
    parts = {
        'yaw2_hub': (yaw_hub(), lambda p: flip(p, 0)),
        'yaw2_fork': (yaw_fork(5.5), lambda p: flip(p, 5.5 + Y1.ROOF_T)),
        'yaw2_fork_7': (yaw_fork(7.0), lambda p: flip(p, 7.0 + Y1.ROOF_T)),
        'yaw2_boss': (yaw_boss(5.5), lambda p: p),
        'yaw2_boss_7': (yaw_boss(7.0), lambda p: p),
        'yaw2_cap': (yaw_cap(), lambda p: p),
        'roll_deck_tray': (roll_deck_tray(), lambda p: p.translate((0, 0, 1.2))),
        'roll_deck_lid': (roll_deck_lid(), lambda p: flip(p, DECK['depth'] + 1.3)),
        'roll_axis_base': (roll_axis_base(), lambda p: p.translate((0, 0, 0.8))),
        'roll_axis_top': (roll_axis_top(), lambda p: flip(p, 25.0)),
        'pitch_tray': (pitch_tray(), lambda p: p.translate((0, 0, 0.8))),
        'pitch_lid': (pitch_lid(), lambda p: flip(p, AX + 1.1)),
        'pitch_tray_r75': (pitch_tray(68.5), lambda p: p.translate((0, 0, 0.8))),
        'pitch_lid_r75': (pitch_lid(68.5), lambda p: flip(p, AX + 1.1)),
    }
    for k, (p, pr) in parts.items():
        vol = p.val().Volume()
        printed = pr(p)
        bb = printed.val().BoundingBox()
        cq.exporters.export(printed, str(out / f'fixtures_cable_rig_{k}.stl'), tolerance=0.01, angularTolerance=0.1)
        cq.exporters.export(printed, str(out / f'fixtures_cable_rig_{k}.step'))
        cq.exporters.export(p, str(out / f'_asm_{k}.stl'), tolerance=0.02, angularTolerance=0.15)
        print(f'{k}: {vol:.0f} mm3, {vol * 1.24e-3:.1f} g PLA, printed box {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f}, z {bb.zmin:.2f}..{bb.zmax:.2f}', flush=True)


if __name__ == '__main__':
    main()
