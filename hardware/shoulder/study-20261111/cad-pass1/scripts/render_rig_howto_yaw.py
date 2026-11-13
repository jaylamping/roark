"""How-to sheet for the yaw cable rig (checks/cable_rigs/HOWTO_yaw.png). Rendered from meshes; no SolidWorks.

    python render_rig_howto_yaw.py        (under capped.py)
"""
import math

import numpy as np
import trimesh
from PIL import Image, ImageDraw

import howto_common as H
from howto_common import R, RX, C1, C2, C3, HI, RED, BLACK, PAIR
import render_rig_howto_roll as RR
import cable_rigs as CR
import cable_loop_rig as Y1
from dims import YZ, DISH_Y

W = 2400
GREY, STEEL = (0.72, 0.73, 0.75), (0.55, 0.56, 0.6)
BLUE2 = (0.25, 0.45, 0.9)
mesh, rotz, smooth, text_block = RR.mesh, RR.rotz, RR.smooth, RR.text_block
HUB, CAP = mesh(CR.yaw_hub()), mesh(CR.yaw_cap())
FORK = {g: mesh(CR.yaw_fork(g)) for g in (5.5, 7.0)}
BOSS = {g: mesh(CR.yaw_boss(g)) for g in (5.5, 7.0)}
TOPZ = lambda g: g + Y1.ROOF_T + 0.2


def hub_pt(r, a, z=0.0):
    """Rig coordinates of a point at hub angle a (the rig's own convention: Y is flipped)."""
    x, y = Y1.pt(r, a)
    return np.array([x, y, z])


def turned(m, yaw):
    """A part that turns with the hub, at yaw (hub angles grow by yaw)."""
    return rotz(m, -yaw)


def screw(g):
    z1 = TOPZ(g) + 1.0
    sh = trimesh.creation.cylinder(radius=2.0, segment=np.array([(0, 0, -5.5), (0, 0, z1)]), sections=24)
    hd = trimesh.creation.cylinder(radius=3.6, segment=np.array([(0, 0, z1), (0, 0, z1 + 2.6)]), sections=24)
    nut = trimesh.creation.cylinder(radius=4.0, segment=np.array([(0, 0, -1.2 - 3.2), (0, 0, -1.2)]), sections=6)
    return trimesh.util.concatenate([sh, hd]), nut


def stack(g, yaw=0.0, fork_op=1.0, lift=None):
    """The assembled rig for dish depth g. lift: dict of part -> z offset, for the exploded view."""
    lift = lift or {}

    def up(m, k):
        m = m.copy()
        m.apply_translation((0, 0, lift.get(k, 0.0)))
        return m
    cap = CAP.copy()
    cap.apply_translation((0, 0, TOPZ(g)))
    s, n = screw(g)
    return [(up(turned(HUB, yaw), 'hub'), C2, 1.0), (up(turned(BOSS[g], yaw), 'boss'), GREY, 1.0), (up(FORK[g], 'fork'), C1, fork_op),
            (up(turned(cap, yaw), 'cap'), C3, 1.0), (up(s, 'screw'), STEEL, 1.0), (up(n, 'nut'), STEEL, 1.0)]


def spiral(yaw, turns, r0, r1):
    """Wires from the exit stub round the dish to the 68 deg window (which turns with the hub), `turns` turns, radius r0 at
    the exit end to r1 at the window end; then down the window's chute. Schematic."""
    a_exit = math.degrees(math.atan2(41.0, -5.4))                 # rig angle of the exit's mouth
    a_win = -(68.0 + yaw)                                          # rig angle of the window
    sweep = (a_exit - a_win) % 360.0 + 360.0 * math.floor(turns)   # clockwise, seen from above
    out = []
    for dz, dr, r_, col in ((1.25, 0.0, 1.3, RED), (3.9, 0.0, 1.3, BLACK), (1.0, -2.6, 0.8, PAIR), (4.4, -2.6, 0.8, (0.1, 0.75, 0.3))):
        p = [(-5.4 + dr * 0.3, 60.0, 1.2 + (dz - 2.4) * 0.5), (-5.4 + dr * 0.3, 47.0, 1.2 + (dz - 2.4) * 0.5)]
        for t in np.linspace(0, 1, 140):
            a = math.radians(a_exit - sweep * t)
            rr = r0 + (r1 - r0) * t + dr
            p.append((rr * math.cos(a), rr * math.sin(a), dz))
        w0, w1 = hub_pt(27.0 + dr * 0.4, 68.0 + yaw, -2.0), hub_pt(22.0, 68.0 + yaw, -16.0)
        p += [tuple(w0), tuple(w1)]
        out.append((R.tube(smooth(p, 260), r_), col, 1.0))
    return out


def dish_shot(name, items, size=(786, 720), eye=(35, 120, 215), focal=(0, 6, 0), angle=30):
    return H.shot(items, name, eye, focal, size=size, angle=angle, up=RR.UPZ)


def panel_where():
    fr, sh = H.torso_meshes()
    F = np.array([40.0, 330.0, 0.0])
    ring = H.ring_marker((RX, DISH_Y - 2.0, YZ), (0, 1, 0), 66.0, 3.5)
    it = H.shoulder_scene() + [(fr, H.FRAMEC2, 1.0), (sh, H.SHELLC, 0.40), (ring, HI, 1.0)]
    a = H.shot(it, 'yaw_where_a', F + np.array([650.0, 250.0, 900.0]), F, size=(800, 760), angle=30)
    H.label(a, (16, 14), 'Seen from the front', 30)
    a = H.caption(a, 'The left shoulder on the torso frame, shell shown see-through. Circled: the yaw joint, the one that twists the upper arm about its own length.', 27)
    # zoom: the flat round space under the yaw motor
    P = R.P
    dish = trimesh.creation.annulus(r_min=25.0, r_max=41.5, height=5.5, sections=96)
    dish.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
    dish.apply_translation((RX, DISH_Y + 2.75, YZ))
    it = [(P['fork_front'], C1, 0.30), (P['fork_rear'], C1, 0.30), (P['hub'], C2, 0.55), (R.M['rs02'], H.MOTORC, 0.35), (dish, HI, 0.95)]
    it += [(m, H.ARMC, 0.25) for n, m in R.UA.items()]
    Fz = np.array([RX, DISH_Y - 6.0, YZ])
    eyeb = Fz + np.array([250.0, 170.0, 330.0])
    b = H.shot(it, 'yaw_where_b', eyeb, Fz, size=(800, 760), angle=24)
    H.label(b, (16, 14), 'Zoomed in, parts see-through', 30)
    H.label(b, (16, 700), 'bright orange ring = the space the wires get', 26, fill=(200, 90, 0))
    b = H.caption(b, 'Blue: the fork (stays still). Dark: the yaw motor, bolted in the fork. Orange disc under it: the hub, which turns with the arm. '
                     'Between the motor and the hub is a flat ring of space only 5.5 mm high. The wires must cross the joint inside it.', 27)
    # the rig placed there: rig X = x - RX, rig Y = -(z - YZ), rig Z = y - floor
    T = np.array([[1, 0, 0, RX], [0, 0, 1, DISH_Y], [0, -1, 0, YZ], [0, 0, 0, 1.0]])
    rig = []
    for m, col, op in stack(5.5, fork_op=0.45):
        m = m.copy()
        m.apply_transform(T)
        rig.append((m, col, op))
    c = H.shot(rig, 'yaw_where_c', Fz + (eyeb - Fz) * 0.62, Fz, size=(800, 760), angle=24)
    H.label(c, (16, 14), 'The rig, same view, enlarged', 30)
    c = H.caption(c, 'The rig is that ring of space, lifted out. Orange = the hub\'s floor, with the hole the wires leave through. Blue (see-through) = the motor\'s underside and the fork\'s wall, with the stub the wires come in by.', 27)
    return H.row([a, b, c])


def panel_parts():
    def flipped(m, h):
        m = m.copy()
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1, 0, 0)))
        m.apply_translation((0, 0, h))
        return m
    specs = [('HUB   ..._yaw2_hub', flipped(HUB, 0.0), C2, 'As it prints: floor down, posts and chutes up. Turn it over to use it.'),
             ('FORK PART 5.5   ..._yaw2_fork', flipped(FORK[5.5], 6.5), C1, 'As it prints: roof down. "5.5" is cut into the roof. Turn it over to use it.'),
             ('FORK PART 7   ..._yaw2_fork_7', flipped(FORK[7.0], 8.0), C1, 'The deeper one: "7" is cut into the roof.'),
             ('BOSS 5.5   ..._yaw2_boss', BOSS[5.5], GREY, 'Plain spokes. Goes with fork part 5.5.'),
             ('BOSS 7   ..._yaw2_boss_7', BOSS[7.0], GREY, 'A raised bar on one spoke. Goes with fork part 7.'),
             ('CAP   ..._yaw2_cap', CAP, C3, 'Flat disc with three holes.')]
    ims = []
    for i, (name, m, col, cap) in enumerate(specs):
        im = RR.rig_shot(f'yaw_part_{i}', [(m, col, 1.0)], eye=(70, 150, 150), focal=(0, 4, 3), size=(786, 520), angle=30 if i < 3 else 20)
        H.label(im, (12, 10), name, 26)
        ims.append(H.caption(im, cap, 25))
    return H.column([H.row(ims[:3], gap=20), H.row(ims[3:], gap=20)], gap=12)


def panel_assembly():
    lift = dict(nut=-14.0, hub=0.0, boss=14.0, fork=30.0, cap=44.0, screw=62.0)
    a = RR.rig_shot('yaw_asm_a', stack(5.5, lift=lift), eye=(150, 230, 120), focal=(0, 0, 28), size=(1190, 1000), angle=30)
    for (x, y), t in (((60, 150), 'M4 x 16 screw'), ((60, 300), 'cap'), ((60, 440), 'fork part (roof up)'), ((60, 590), 'boss'), ((60, 730), 'hub (floor up, posts down)'), ((60, 880), 'M4 nut')):
        H.label(a, (x, y), t, 28)
    H.label(a, (16, 14), '1. The stack, bottom to top', 30)
    b = RR.rig_shot('yaw_asm_b', stack(5.5), eye=(110, 190, 150), focal=(0, 4, 2), size=(1190, 1000), angle=24)
    H.label(b, (16, 14), '2. Together', 30)
    H.label(b, (16, 930), 'the stub where the wires come in', 26, fill=(30, 70, 150))
    return H.caption(H.row([a, b], gap=20), 'The screw clamps cap, boss and hub together: those three turn as one, and stand for the arm. The blue fork part is not clamped: it rests on the boss\'s step and stays still '
                                           '(hold it by its stub). Use boss 5.5 with fork part 5.5, or boss 7 with fork part 7: the boss sets how high the roof sits over the floor.', 27)


def panel_wires():
    ims = []
    for yaw, name, turns, r0, r1 in ((-90.0, 'Arm twisted fully one way', 2, 40.0, 35.5), (0.0, 'Arm straight ahead', 2, 39.5, 31.0), (90.0, 'Arm twisted fully the other way', 2, 36.5, 27.5)):
        it = stack(5.5, yaw=yaw, fork_op=0.10)
        it = [x for x in it if x[1] not in (C3, STEEL)] + spiral(yaw, turns, r0, r1)
        im = dish_shot(f'yaw_wires_{int(yaw)}', it)
        H.label(im, (14, 12), name, 28)
        ims.append(im)
    return H.caption(H.row(ims, gap=20), 'Looking down through the roof (cap and screw left out, fork part see-through). The wires come in by the stub and are tied there (tie through the two slots in the stub\'s roof). '
                                         'They lie as a flat spiral on the hub\'s floor, power wires one on top of the other, thin wires (yellow, green) beside them, and leave down through the hole in the floor, '
                                         'where they are tied to the post under the floor. As the hub turns, the spiral opens out against the outer wall (left) or winds in round the middle (right). Drawn roughly: the real one is what the test shows.', 27)


def sketch_good_bad(w=1100, h=470):
    im = Image.new('RGB', (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.text((40, 14), 'GOOD', fill=(20, 130, 40), font=H.fontb(30))
    d.text((w // 2 + 40, 14), 'BAD', fill=(190, 30, 30), font=H.fontb(30))
    d.line((w // 2, 10, w // 2, h - 10), fill=(180, 180, 180), width=2)
    for cx, bad in ((w // 4, False), (3 * w // 4, True)):
        cy = 190
        d.ellipse((cx - 150, cy - 130, cx + 150, cy + 130), outline=(150, 150, 150), width=3)
        d.ellipse((cx - 60, cy - 52, cx + 60, cy + 52), outline=(150, 150, 150), width=3)
        pts = []
        for i in range(0, 760, 6):
            a = math.radians(i)
            r = 138 - i * 0.075
            if bad and 380 < i < 520:
                r -= 34 * math.sin((i - 380) / 140 * math.pi) * (1 if (i // 12) % 2 else -0.4)
            pts.append((cx + r * math.cos(a), cy + r * 0.87 * math.sin(a)))
        d.line(pts, fill=(215, 30, 30), width=7, joint='curve')
        if bad:
            d.ellipse((cx - 150, cy - 10, cx - 40, cy + 110), outline=(190, 30, 30), width=4)
    for i, t in enumerate(('The wires stay in one even band.', 'Nothing bunches or lifts the roof.', 'Light, even feel all the way round.')):
        d.text((40, h - 126 + i * 36), t, fill=(20, 20, 20), font=H.font(26))
    for i, t in enumerate(('Bunching, or a wire trapped under another.', 'A tight spot, or the roof lifting.', 'A thin wire caught at the rim.')):
        d.text((w // 2 + 40, h - 126 + i * 36), t, fill=(20, 20, 20), font=H.font(26))
    return im


def panel_test():
    steps = text_block([
        (True, '1  Tie in at the stub.'), (False, 'Push the wires in through the blue stub and tie them down with a small cable tie through the two slots in its roof.'),
        (True, '2  Lay the spiral.'), (False, 'With the fork part lying beside the hub, lay the wires round the hub\'s floor about two and a half times, thick wires stacked, thin ones beside them.'),
        (True, '3  Tie off under the floor.'), (False, 'Lead the end down the hole in the floor that is next to the pointer tab on the hub (tape over the other hole) and tie it to the post beside it, under the floor.'),
        (True, '4  Stack it.'), (False, 'Boss on the hub, fork part over the boss, cap, screw and nut. Pointer at 0.'),
        (True, '5  Turn.'), (False, 'Hold the stub still and turn the hub slowly between the two stops (-90 and +90 on the roof), five times, looking through the slots in the roof. Then 200 times.'),
        (True, 'Do it four times:'), (False, 'thin power wire (18 AWG) with parts 5.5; thick (16 AWG) with parts 5.5; thick with parts 7; and thick with parts 5.5 laid as one plain arc, not a spiral, turning only a little each way. '
                                             'Try the two spiral ones that work both with the thin pairs left twisted and with their last half metre untwisted.'),
    ], 1250)
    return H.row([steps, sketch_good_bad()], gap=30)


def main():
    parts = [
        H.heading('YAW CABLE RIG: what it is and how to run it', W, 52, 'Print fixtures_cable_rig_yaw.3mf: six parts. It comes in two heights (5.5 and 7) so thin and thick power wire can both be tried.'),
        H.heading('1  Where it comes from', W, 36), panel_where(),
        H.heading('2  The six parts', W, 36), panel_parts(),
        H.heading('3  How they go together', W, 36), panel_assembly(),
        H.heading('4  The wires, at the two ends of travel and in the middle', W, 36), panel_wires(),
        H.heading('5  The test', W, 36), panel_test(),
    ]
    parts = [p if p.width == W else p.resize((W, int(p.height * W / p.width)), Image.LANCZOS) for p in parts]
    sheet = H.column(parts, gap=10)
    sheet.save(H.OUT / 'HOWTO_yaw.png', optimize=True)
    print('saved', H.OUT / 'HOWTO_yaw.png', sheet.size)


if __name__ == '__main__':
    main()
