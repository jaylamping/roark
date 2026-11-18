"""Test rig for the yaw dish loop: does the arm bundle run between the fork's yaw exit and the hub's cable window over
yaw -90..+90, and where does its slack go?  (checks/CABLE_LOOP_RIG.md)

    python cable_loop_rig.py OUTDIR

Four small parts (cadquery, no SolidWorks), printed flat without support:
  fork  the fixed side: the RS02's underside as a roof (r 22.2-43.1, 5.5 mm above the dish floor), the fork skirt's bore
        (r 41.5) and the yaw exit (16 x 6 channel, centre X - RX -5.4, entering toward the axis at Z - YZ -37, i.e. at
        261.7 deg), a yaw scale every 10 deg and stops at +-90.
  hub   the turning side: the dish floor (r to 39.3) with the cable window at 68 and at 248 deg, each with the real slot
        (9 mm in the radial plane, +-8 across, from r 31 at the dish down to r 15.5 at Y 298), through the real floor
        thickness (5.56) and down the bore wall (r 23) to 22 mm below the floor; a pointer tab.
  boss  the hub's step ring (r 23.5, 1.5 high) and the RS02 rotor (r 21.8) above it; turns with the hub.
  cap   holds the fork on; one M4 x 16 and nut clamp cap, boss and hub together.
Angles are the hub's (atan2(z - YZ, x - RX)); the rig keeps the robot's handedness: rig X = x - RX, rig Y = -(z - YZ),
rig Z = y - 318.36 (the dish floor). Parts are exported as printed (fork and hub turned over).
"""
import math
import sys
from pathlib import Path

import cadquery as cq

GAP = 5.5                     # dish floor (Y 318.36) to the RS02's underside (Y 323.86)
FLOOR_T, ROOF_T = 1.2, 1.0
R_RIM, R_SKIRT, R_OUT = 39.3, 41.5, 43.1
R_STEP, R_ROTOR = 23.5, 21.8
EXIT_X, EXIT_Y0 = -5.4, 37.0  # channel centre (X - RX) and where it ends (|Z - YZ|)
EXIT_Z = (-1.81, 4.19)        # channel Y 316.55-322.55 against the floor at 318.36
WINDOWS = (68.0, 248.0)
P1, P0 = (15.5, 298.0 - 318.36), (31.0, 2.0)        # slot centre line (r, rig Z): bore end, dish end
TAB_A = 90.0                  # pointer tab on the hub; on the fork it reads 90 - yaw


def pt(r, a):
    a = math.radians(a)
    return (r * math.cos(a), -r * math.sin(a))


def sector(ri, ro, a0, a1, z0, z1, step=2.0):
    n = max(2, int(abs(a1 - a0) / step) + 1)
    aa = [a0 + (a1 - a0) * i / (n - 1) for i in range(n)]
    pts = [pt(ro, a) for a in aa] + [pt(ri, a) for a in reversed(aa)]
    return cq.Workplane('XY').workplane(offset=z0).polyline(pts).close().extrude(z1 - z0)


def ring(ri, ro, z0, z1):
    w = cq.Workplane('XY').workplane(offset=z0).circle(ro)
    if ri > 0:
        w = w.circle(ri)
    return w.extrude(z1 - z0)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def slot(w):
    ux, uz = P0[0] - P1[0], P0[1] - P1[1]
    ln = math.hypot(ux, uz); ux, uz = ux / ln, uz / ln
    nx, nz = uz, -ux
    a, b = (P1[0] - ux * 5, P1[1] - uz * 5), (P0[0] + ux * 6, P0[1] + uz * 6)
    pts = [(a[0] + nx * 4.5, a[1] + nz * 4.5), (b[0] + nx * 4.5, b[1] + nz * 4.5), (b[0] - nx * 4.5, b[1] - nz * 4.5), (a[0] - nx * 4.5, a[1] - nz * 4.5)]
    s = cq.Workplane('XZ').polyline(pts).close().extrude(8.0, both=True)
    return s.rotate((0, 0, 0), (0, 0, 1), -w)


def hub():
    h = ring(0, R_RIM, -FLOOR_T, 0)
    for w in WINDOWS:
        h = h.union(sector(18.0, 36.5, w - 24, w + 24, -5.56, 0))         # the real floor thickness round the window
        h = h.union(sector(23.0, 27.0, w - 24, w + 24, -22.0, -5.56))     # the bore wall below it (inner face r 23)
    for w in WINDOWS:
        h = h.cut(slot(w))
    h = h.union(sector(R_RIM - 0.5, 48.0, TAB_A - 4.0, TAB_A + 4.0, -0.8, 0))    # pointer tab
    h = h.cut(ring(0, 2.15, -30, 10))
    for a in (10, 130, 190, 310):                                          # lightening, clear of the windows
        x, y = pt(11.5, a)
        h = h.cut(cq.Workplane('XY').workplane(offset=-10).center(x, y).circle(5.5).extrude(20))
    return h


def fork():
    f = ring(R_ROTOR + 0.4, R_OUT, GAP, GAP + ROOF_T)
    f = f.union(ring(R_SKIRT, R_OUT, 0.4, GAP))
    for a0, a1 in ((-12.0, -4.6), (184.6, 192.0)):                         # stops at yaw +90 and -90 for the tab
        f = f.union(sector(R_SKIRT, R_OUT, a0, a1, -FLOOR_T, 0.4))
    # yaw exit: a stub outside the skirt with the 16 x 6 channel, and the channel's roof inside the skirt
    f = f.union(box(EXIT_X - 9.2, EXIT_X + 9.2, 40.6, 57.0, EXIT_Z[0] - 1.2, GAP + ROOF_T))
    f = f.union(box(EXIT_X - 9.2, EXIT_X + 9.2, EXIT_Y0, 42.0, EXIT_Z[1], GAP))
    f = f.cut(box(EXIT_X - 8.0, EXIT_X + 8.0, EXIT_Y0 - 1.0, 58.0, EXIT_Z[0], EXIT_Z[1]))
    # viewing slots in the roof (2 mm: narrower than the wires)
    for a in range(15, 360, 30):
        if abs(a - 255) < 20:
            continue
        s = box(26.0, 37.0, -1.0, 1.0, GAP - 1, GAP + ROOF_T + 1).rotate((0, 0, 0), (0, 0, 1), -a)
        f = f.cut(s)
    # yaw scale on the roof's top: a tick every 10 deg, long at -90 / 0 / +90 (the tab reads 90 - yaw)
    zt = GAP + ROOF_T
    for yaw in range(-90, 91, 10):
        r0 = 36.0 if yaw % 90 == 0 else 39.5
        f = f.cut(box(r0, R_OUT + 1, -0.35, 0.35, zt - 0.4, zt + 1).rotate((0, 0, 0), (0, 0, 1), -(TAB_A - yaw)))
    for yaw, txt in ((-90, '-90'), (0, '0'), (90, '+90')):
        x, y = pt(31.0, TAB_A - yaw + 9.0)
        t = cq.Workplane('XY').workplane(offset=zt - 0.4).center(x, y).text(txt, 4.5, 1.0, kind='bold')
        f = f.cut(t)
    return f


def boss():
    b = ring(20.0, R_STEP, 0, 1.5)
    b = b.union(ring(20.0, R_ROTOR, 0, GAP + ROOF_T + 0.2))
    b = b.union(ring(0, 5.0, 0, GAP + ROOF_T + 0.2))
    for a in (0, 120, 240):
        b = b.union(box(4.0, 20.5, -2.5, 2.5, 0, 1.2).rotate((0, 0, 0), (0, 0, 1), a))
    return b.cut(ring(0, 2.15, -1, 20))


def cap():
    z = GAP + ROOF_T + 0.2
    c = ring(0, 26.0, z, z + 1.0)
    for a in (60, 180, 300):
        x, y = pt(14.5, a)
        c = c.cut(cq.Workplane('XY').workplane(offset=z - 1).center(x, y).circle(7.0).extrude(3))
    return c.cut(ring(0, 2.15, z - 1, z + 2))


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    parts = dict(fork=fork(), hub=hub(), boss=boss(), cap=cap())
    asm = cq.Assembly()
    for k, p in parts.items():
        asm.add(p, name=k)
        vol = p.val().Volume()
        printed = p
        if k == 'fork':                       # roof on the bed
            printed = p.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, GAP + ROOF_T))
        if k == 'hub':                        # dish floor on the bed, the window chutes up
            printed = p.rotate((0, 0, 0), (1, 0, 0), 180)
        if k == 'cap':
            printed = p.translate((0, 0, -(GAP + ROOF_T + 0.2)))
        bb = printed.val().BoundingBox()
        cq.exporters.export(printed, str(out / f'fixtures_yaw_loop_rig_{k}.stl'), tolerance=0.01, angularTolerance=0.1)
        cq.exporters.export(printed, str(out / f'fixtures_yaw_loop_rig_{k}.step'))
        print(f'{k}: {vol:.0f} mm3, {vol * 1.24e-3:.1f} g PLA, printed box {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f}, z {bb.zmin:.2f}..{bb.zmax:.2f}')
    cq.exporters.export(asm.toCompound(), str(out / 'fixtures_yaw_loop_rig_assembled.stl'), tolerance=0.02, angularTolerance=0.15)
    for k, p in parts.items():
        cq.exporters.export(p, str(out / f'_asm_{k}.stl'), tolerance=0.02, angularTolerance=0.15)


if __name__ == '__main__':
    main()
