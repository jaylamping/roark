"""How-to sheet for the pitch cable rig (checks/cable_rigs/HOWTO_pitch.png). Rendered from meshes; no SolidWorks.

    python render_rig_howto_pitch.py        (under capped.py)
"""
import math

import numpy as np
import trimesh
from PIL import Image, ImageDraw

import howto_common as H
from howto_common import R, RY, C1, C2, HI, RED, BLACK, PAIR
import render_rig_howto_roll as RR
import render_shoulder_with_shell as S
import cable_rigs as CR
from dims import PZ

W = 2400
STEEL = (0.55, 0.56, 0.6)
GREEN = (0.1, 0.75, 0.3)
mesh, rotz, smooth, text_block = RR.mesh, RR.rotz, RR.smooth, RR.text_block
TRAY, LID = mesh(CR.pitch_tray()), mesh(CR.pitch_lid())
RI, RO, AX = CR.RI, CR.RO, CR.AX


def screw():
    sh = trimesh.creation.cylinder(radius=2.0, segment=np.array([(0, 0, -7.0), (0, 0, 23.2)]), sections=24)
    hd = trimesh.creation.cylinder(radius=3.6, segment=np.array([(0, 0, 23.2), (0, 0, 25.8)]), sections=24)
    nut = trimesh.creation.cylinder(radius=4.0, segment=np.array([(0, 0, -4.0), (0, 0, -0.8)]), sections=6)
    return trimesh.util.concatenate([sh, hd, nut])


def rig(lid_angle=0.0, lid_op=1.0, lift=0.0):
    lid = rotz(LID, -lid_angle)
    lid.apply_translation((0, 0, lift))
    s = screw()
    s.apply_translation((0, 0, lift * 1.6))
    return [(TRAY, C1, 1.0), (lid, C2, lid_op), (s, STEEL, 1.0)]


def mouth(lid_angle):
    """Rig point of the lid's mouth (the lid's 90 deg direction, at r 65.5) with the lid turned."""
    x, y = CR.pt(65.5, 90.0 + lid_angle)
    return np.array([x, y])


def wires_spiral(lid_angle, turns, r0, r1):
    """Test E: from the tongue's tie holes, over the finger, round the channel `turns` times (r0 at the fixed end to r1 at
    the lid's mouth), up through the mouth. Side by side across the channel's height. Schematic."""
    out = []
    m = mouth(lid_angle)
    a_end = math.atan2(m[1], m[0])
    a0 = math.radians(60.0)                                    # where the wires come off the finger into the channel
    sweep = (a0 - a_end) % (2 * math.pi) + 2 * math.pi * turns
    for z, r_, col in ((3.5, 1.5, RED), (8.0, 1.5, BLACK), (12.5, 0.9, PAIR), (16.0, 0.9, GREEN)):
        p = [(-28.0, RO + 40.0, 2.0 + z * 0.15), (-28.0, RO + 26.0, 2.0 + z * 0.15), (-4.0, RO + 6.0, z), (22.0, RO - 6.0, z)]
        for t in np.linspace(0, 1, 160):
            a = a0 - sweep * t
            rr = r0 + (r1 - r0) * t
            p.append((rr * math.cos(a), rr * math.sin(a), z))
        p += [(m[0], m[1], AX - 1.0), (m[0], m[1], AX + 14.0)]
        out.append((R.tube(smooth(p, 300), r_), col, 1.0))
    return out


def wires_bight(lid_angle, depth):
    """Test F: from the lid's mouth round the inner wall, over the finger, down through the slot as a hanging loop of
    `depth` mm, and back up to the tongue's tie holes. Rig +Y is down. Schematic."""
    out = []
    m = mouth(lid_angle)
    a_m = math.atan2(m[1], m[0])
    a_f = math.radians(52.0)                                   # where the wires leave the inner wall for the finger
    sweep = (a_m - a_f) % (2 * math.pi)
    for z, r_, col in ((3.5, 1.5, RED), (8.0, 1.5, BLACK), (12.5, 0.9, PAIR), (16.0, 0.9, GREEN)):
        p = [(m[0], m[1], AX + 14.0), (m[0], m[1], AX - 1.0)]
        for t in np.linspace(0, 1, 120):
            a = a_m - sweep * t
            p.append(((RI + 2.0) * math.cos(a), (RI + 2.0) * math.sin(a), z))
        y0 = RO + 34.0
        p += [(24.0, RI + 14.0, z), (14.0, RO + 2.0, z), (10.0, y0, z)]
        for t in np.linspace(0, math.pi, 24):                  # the hanging loop, R 20, `depth` below the tongue
            p.append((-10.0 + 20.0 * math.cos(t), y0 + depth - 20.0 + 20.0 * math.sin(t), z))
        p += [(-30.0, y0, z * 0.3 + 1.0), (-28.0, RO + 26.0, 1.5)]
        out.append((R.tube(smooth(p, 300), r_), col, 1.0))
    wt = trimesh.creation.cylinder(radius=7.0, segment=np.array([(-10.0, RO + 34.0 + depth, 4.0), (-10.0, RO + 34.0 + depth + 16.0, 4.0)]), sections=20)
    out.append((wt, (0.35, 0.35, 0.38), 1.0))
    return out


def flat_shot(name, items, size=(786, 720), eye=(40, 150, 330), focal=(0, 12, 8), angle=30):
    return H.shot(items, name, eye, focal, size=size, angle=angle, up=RR.UPZ)


def panel_where():
    fr, _ = H.torso_meshes()
    sh = S.outer_shell()
    F = np.array([40.0, 330.0, 0.0])
    ring = H.ring_marker((106.0, RY, PZ), (1, 0, 0), 92.0, 3.5)
    loop = trimesh.creation.box(extents=(12.0, 117.0, 60.0))
    loop.apply_translation((50.0, 236.5, 0.0))
    it = H.shoulder_scene() + [(fr, H.FRAMEC2, 1.0), (sh, S.SHELL_COL, 0.28), (ring, HI, 1.0), (loop, (0.9, 0.2, 0.6), 0.95)]
    a = H.shot(it, 'pitch_where_a', F + np.array([650.0, 250.0, 900.0]), F, size=(800, 760), angle=30)
    H.label(a, (16, 14), 'Seen from the front, body shell see-through', 28)
    H.label(a, (16, 704), 'pink block = where the spare wire would hang', 24, fill=(170, 30, 110))
    a = H.caption(a, 'Circled: the pitch joint, the one that swings the whole arm forward and back. It is at the body: the motor is bolted to the torso frame and the shoulder turns on it.', 27)
    P = R.P
    chan = trimesh.creation.annulus(r_min=RI, r_max=RO, height=AX, sections=96)
    chan.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
    chan.apply_translation((104.5 - AX / 2, RY, PZ))
    it = [(P['cover'], C1, 0.30), (P['ring'], C2, 0.55), (P['drum'], C2, 0.25), (R.M['pitch_rs03'], H.MOTORC, 0.6), (chan, HI, 0.9), (fr, H.FRAMEC2, 0.25)]
    Fz = np.array([92.0, RY - 10.0, PZ])
    eyeb = Fz + np.array([330.0, 110.0, 330.0])
    b = H.shot(it, 'pitch_where_b', eyeb, Fz, size=(800, 760), angle=26)
    H.label(b, (16, 14), 'Zoomed in, parts see-through', 30)
    H.label(b, (16, 704), 'bright orange ring = the space the wires get', 26, fill=(200, 90, 0))
    b = H.caption(b, 'Blue: the cover on the torso (stays still). Dark: the pitch motor. Orange: the shoulder\'s drum and its ring (turn with the arm). '
                     'Round the motor, between cover and ring, is a channel 16 mm wide and 21 mm deep. The wires cross the joint in it.', 27)
    T = np.array([[0, 0, 1, 104.5 - AX - 0.3], [0, -1, 0, RY], [1, 0, 0, PZ], [0, 0, 0, 1.0]])
    items = []
    for m, col, op in rig(0.0, lid_op=0.45):
        m = m.copy()
        m.apply_transform(T)
        items.append((m, col, op))
    c = H.shot(items, 'pitch_where_c', Fz + np.array([0.0, -25.0, 0.0]) + (eyeb - Fz) * 0.85, Fz + np.array([0.0, -25.0, 0.0]), size=(800, 760), angle=26)
    H.label(c, (16, 14), 'The rig, same view', 30)
    c = H.caption(c, 'The rig is that channel, lifted out and laid in a tray. Blue tray = the cover side, with a slot at the bottom and a tongue below it. Orange lid (see-through) = the shoulder\'s ring, with a small hole the wires leave through.', 27)
    return H.row([a, b, c])


def panel_parts():
    lid_print = LID.copy()
    lid_print.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1, 0, 0)))
    lid_print.apply_translation((0, 0, AX + 1.1))
    a = flat_shot('pitch_part_tray', [(TRAY, C1, 1.0)], size=(1190, 800), eye=(90, 260, 250), focal=(0, 14, 6))
    H.label(a, (16, 14), 'TRAY   fixtures_cable_rig_pitch_tray', 30)
    for (x, y), t in (((700, 110), 'outer wall'), ((520, 250), 'inner wall'), ((80, 520), 'round guide post'), ((80, 620), 'tongue with two tie holes'), ((700, 640), 'slot in the outer wall')):
        H.label(a, (x, y), t, 24, bold=False)
    a = H.caption(a, 'As it prints: floor down. The ring-shaped channel between the two walls is where the wires go.', 27)
    b = flat_shot('pitch_part_lid', [(lid_print, C2, 1.0)], size=(1190, 800), eye=(90, 260, 250), focal=(0, 0, 4))
    H.label(b, (16, 14), 'LID   fixtures_cable_rig_pitch_lid', 30)
    b = H.caption(b, 'As it prints: flat side down. A flat ring with spokes, a small rectangular hole with a tie hole each side (the wires leave here), slots to look through, and a pointer on its rim.', 27)
    return H.row([a, b], gap=20)


def panel_assembly():
    a = flat_shot('pitch_asm_a', rig(0.0, lift=34.0), size=(1190, 860), eye=(120, 300, 210), focal=(0, 10, 22))
    H.label(a, (16, 14), '1. Lid over the tray, one M4 x 30 screw through both middles, nut underneath', 28)
    b = flat_shot('pitch_asm_b', rig(0.0), size=(1190, 860), eye=(90, 260, 250), focal=(0, 14, 6))
    H.label(b, (16, 14), '2. Together. The lid turns on the screw', 28)
    return H.caption(H.row([a, b], gap=20), 'Leave the nut loose enough for the lid to turn freely. The tray is the side that stays still; the lid is the side that turns.', 27)


def panel_wires_e():
    ims = []
    for ang, name, r0, r1 in ((0.0, 'Start: wires lying against the outer wall', RO - 2.5, RO - 2.5), (115.0, 'Lid turned until they are snug on the inner wall', RI + 3.0, RI + 2.5)):
        it = rig(ang, lid_op=0.14)[:2] + wires_spiral(ang, 2, r0, r1)
        im = flat_shot(f'pitch_e_{int(ang)}', it, size=(1190, 860), eye=(30, 110, 380), focal=(0, 16, 8))
        H.label(im, (14, 12), name, 28)
        ims.append(im)
    return H.caption(H.row(ims, gap=20), 'FIRST TEST, tray flat on the bench. The wires are tied to the tongue, go over the round post into the channel, lie two turns round it side by side '
                                         '(red, black, then the two thin pairs, one above the other across the channel\'s height), and come up through the lid\'s small hole, where they are tied. '
                                         'Turning the lid winds the two turns from the outer wall onto the inner wall. How far it turns before they go tight is the answer (expected about 115 degrees).', 27)


def panel_wires_f():
    ims = []
    for ang, name, depth in ((20.0, 'Start: long loop hanging (about 140 mm)', 140.0), (135.0, 'Half way', 80.0), (250.0, 'Lid turned 230 degrees: loop pulled up short', 22.0)):
        it = rig(ang, lid_op=0.14)[:2] + wires_bight(ang, depth)
        im = H.shot(it, f'pitch_f_{int(ang)}', (60, 60, 520), (0, 95, 8), size=(786, 980), angle=34, up=(0, -1, 0))
        H.label(im, (14, 12), name, 26)
        ims.append(im)
    return H.caption(H.row(ims, gap=20), 'SECOND TEST, tray held upright with the slot at the bottom (drawn as you would see it hanging on a shelf edge). The wires are tied at the lid\'s hole, run round the inner wall, '
                                         'over the round post and down through the slot, hang as a loop with a small weight in it (grey), and come back up to the tongue\'s tie holes. '
                                         'Turning the lid wraps wire onto the inner wall and the loop gets shorter; turning back, the weight pulls the loop long again.', 27)


def sketch_good_bad(w=1100, h=430):
    im = Image.new('RGB', (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.text((40, 14), 'GOOD', fill=(20, 130, 40), font=H.fontb(30))
    d.text((w // 2 + 40, 14), 'BAD', fill=(190, 30, 30), font=H.fontb(30))
    d.line((w // 2, 10, w // 2, h - 10), fill=(180, 180, 180), width=2)
    for x0, bad in ((60, False), (w // 2 + 60, True)):
        d.rectangle((x0, 70, x0 + 380, 250), outline=(150, 150, 150), width=3)
        for i, col in enumerate(((215, 30, 30), (20, 20, 20), (235, 185, 30), (30, 170, 70))):
            y = 95 + i * 42
            if bad and i in (1, 2):
                pts = [(x0 + 10, y), (x0 + 150, y), (x0 + 200, y + (60 if i == 1 else -50)), (x0 + 250, y), (x0 + 370, y)]
            else:
                pts = [(x0 + 10, y), (x0 + 370, y)]
            d.line(pts, fill=col, width=9, joint='curve')
        d.text((x0, 256), 'looking in through a slot in the lid', fill=(110, 110, 110), font=H.font(20))
    for i, t in enumerate(('Wires stay side by side in one layer.', 'Light, even feel. The loop follows by itself.', 'No marks on the wires afterwards.')):
        d.text((40, h - 122 + i * 36), t, fill=(20, 20, 20), font=H.font(26))
    for i, t in enumerate(('Wires cross or pile up in the channel.', 'A tight spot, or the loop does not follow.', 'A wire jams at the slot or the post.')):
        d.text((w // 2 + 40, h - 122 + i * 36), t, fill=(20, 20, 20), font=H.font(26))
    return im


def panel_test():
    steps = text_block([
        (True, 'FIRST TEST (flat on the bench)'),
        (False, '1  Tie the wires to the two holes in the tongue. Lead them over the round post and lay two turns round the channel against the outer wall, side by side.'),
        (False, '2  Bring the end up through the small hole in the lid, tie it to the hole each side, and fit the lid and the screw.'),
        (False, '3  Mark where the lid\'s pointer is. Turn the lid the way that tightens the wires until they are snug on the inner wall. Mark again. Measure the angle between the marks.'),
        (False, '4  Go between the marks slowly five times, then 200 times.'),
        (True, 'SECOND TEST (upright, slot at the bottom)'),
        (False, '1  Tie the wires at the lid\'s hole, lead them round the inner wall, over the post and down through the slot.'),
        (False, '2  Hang about 30 g in the loop below the slot (six M8 nuts on a paper clip) and tie the free end to the tongue so the loop hangs about 140 mm.'),
        (False, '3  Turn the lid 230 degrees the way that wraps the wires on. The loop should rise to about 15 mm, and fall back by itself when you turn back.'),
        (False, '4  Five slow times, then 200. Try 270 degrees once. Then try a thin elastic in place of the weight, and no pull at all.'),
    ], 1250)
    return H.row([steps, sketch_good_bad()], gap=30)


def main():
    parts = [
        H.heading('PITCH CABLE RIG: what it is and how to run it', W, 52, 'Print fixtures_cable_rig_pitch_tray.3mf and fixtures_cable_rig_pitch_lid.3mf (one part each). Two tests on the same two parts.'),
        H.heading('1  Where it comes from', W, 36), panel_where(),
        H.heading('2  The two parts', W, 36), panel_parts(),
        H.heading('3  How they go together', W, 36), panel_assembly(),
        H.heading('4  The wires, first test: a spiral in the channel', W, 36), panel_wires_e(),
        H.heading('4  The wires, second test: wrap on the inner wall and a hanging loop', W, 36), panel_wires_f(),
        H.heading('5  The tests', W, 36), panel_test(),
    ]
    parts = [p if p.width == W else p.resize((W, int(p.height * W / p.width)), Image.LANCZOS) for p in parts]
    sheet = H.column(parts, gap=10)
    sheet.save(H.OUT / 'HOWTO_pitch.png', optimize=True)
    print('saved', H.OUT / 'HOWTO_pitch.png', sheet.size)


if __name__ == '__main__':
    main()
