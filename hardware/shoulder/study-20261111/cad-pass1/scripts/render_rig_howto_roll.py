"""How-to sheet for the roll cable rig (checks/cable_rigs/HOWTO_roll.png) and the shared picture of the shoulder on the torso
(checks/cable_rigs/shoulder_on_torso.png). Rendered from meshes; no SolidWorks.

    python render_rig_howto_roll.py        (under capped.py)
"""
import math

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy.interpolate import splev, splprep

import howto_common as H
from howto_common import R, RX, RY, C1, C2, C3, C4, HI, RED, BLACK, PAIR
import cable_rigs as CR
from check_clearance import tess
from dims import CAPZ, RZ, TRUNK_X, TRUNK_Y

W = 2400            # sheet width, px


def mesh(wp, tol=0.08):
    return tess(wp.val(), tol)


def rotz(m, deg):
    m = m.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(deg), (0, 0, 1)))
    return m


def smooth(pts, n=80):
    pts = np.array(pts, float)
    tck, _ = splprep(pts.T, s=0, k=min(3, len(pts) - 1))
    return np.array(splev(np.linspace(0, 1, n), tck)).T


def rig_wires(theta, tape=True):
    """Wires through the on-axis rig with the top at `theta` degrees from the base's channel (rig coordinates, mm)."""
    t = math.radians(theta)
    d = np.array([-math.sin(t), math.cos(t), 0.0])        # the top channel's direction
    n = np.array([math.cos(t), math.sin(t), 0.0])         # across it
    items = []
    for off, r, col in ((-5.0, 1.5, RED), (-1.6, 1.5, BLACK), (2.0, 0.9, PAIR), (4.6, 0.9, (0.25, 0.45, 0.9))):
        p = [(off, 70, r), (off, 40, r), (off, 16, r), (off * 0.45, 4, 4.0), (off * 0.35, 0, 9.0), (off * 0.35, 0, 15.0)]
        for s_, z_ in ((4.0, 20.0), (16.0, 21.0), (40.0, 21.0), (70.0, 21.0)):
            k = 0.45 if s_ < 10 else 1.0
            p.append(tuple(d * s_ + n * off * k + np.array([0, 0, z_])))
        items.append((R.tube(smooth(p), r), col, 1.0))
    if tape:
        for c_, dd, nn, z in (((0, 25, 0), np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), 3.4), (tuple(d * 25), d, n, 22.6)):
            b = trimesh.creation.box(extents=(17.5, 9.0, 0.8))
            T = np.eye(4)
            T[:3, 0], T[:3, 1], T[:3, 2] = nn, dd, (0, 0, 1)
            T[:3, 3] = np.array(c_) + np.array([0, 0, z])
            b.apply_transform(T)
            items.append((b, (0.98, 0.93, 0.55), 1.0))
    return items


BASE, TOP = mesh(CR.roll_axis_base()), mesh(CR.roll_axis_top())
TRAY, LID = mesh(CR.roll_deck_tray()), mesh(CR.roll_deck_lid())
UPZ = (0, 0, 1)


def rig_shot(name, items, eye=(75, 165, 125), focal=(0, 8, 9), size=(760, 640), angle=26):
    return H.shot(items, name, eye, focal, size=size, angle=angle, up=UPZ)


def rig_in_model(theta, with_path=True):
    """The on-axis rig placed on the real roll axis: its tube on the axis, its base channel along the cap's spoke."""
    s = np.array([TRUNK_X - RX, TRUNK_Y - RY, 0.0])
    s /= np.linalg.norm(s)
    ez = np.array([0, 0, -1.0])                           # the fork rear's channel is behind the cap's: rig up = model -Z
    ex = np.cross(s, ez)
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2] = ex, s, ez
    T[:3, 3] = (RX, RY, CAPZ + 3.0)
    out = []
    for m, col in ((BASE, C1), (rotz(TOP, theta), C2)):
        m = m.copy()
        m.apply_transform(T)
        out.append((m, col, 1.0))
    return out, T


def panel_where():
    fr, sh = H.torso_meshes()
    spoke = np.array([TRUNK_X - RX, TRUNK_Y - RY])
    ang0 = math.degrees(math.atan2(spoke[1], spoke[0]))
    print('cap spoke direction %.1f deg; fork leg -90 deg; between them %.1f deg (the rig page says 135 at roll 0)' % (ang0, (ang0 + 90) % 360))
    # a) the whole thing, from behind and outboard
    F = np.array([40.0, 330.0, 0.0])
    ring = H.ring_marker((RX, RY, -52.0), (0.35, 0.1, -1.0), 78.0, 3.5)
    it = H.shoulder_scene() + [(fr, H.FRAMEC2, 1.0), (sh, H.SHELLC, 0.40), (ring, HI, 1.0)]
    a = H.shot(it, 'roll_where_a', F + np.array([620.0, 230.0, -880.0]), F, size=(800, 760), angle=30)
    H.label(a, (16, 14), 'Seen from behind', 30)
    a = H.caption(a, 'The left shoulder on the torso frame, shell shown see-through. Circled: the roll joint, the one that lifts the arm out sideways.', 27)
    # b) zoom: the two parts the wires pass between, see-through, with the wire path
    path = [(TRUNK_X, TRUNK_Y, CAPZ), (RX, RY, CAPZ), (RX, RY, RZ), (RX, RY - 85.0, RZ)]
    P = R.P
    it = [(P['drum'], H.PARTC, 0.16), (P['cap'], C1, 0.40), (P['fork_rear'], C2, 0.40), (P['fork_front'], H.PARTC, 0.16), (P['hub'], H.PARTC, 0.16),
          (R.tube(path, 3.2), HI, 1.0)]
    Fz = np.array([RX, RY - 22.0, -40.0])
    eyeb = Fz + np.array([300.0, 120.0, -430.0])
    b = H.shot(it, 'roll_where_b', eyeb, Fz, size=(800, 760), angle=24)
    H.label(b, (16, 14), 'Zoomed in, parts see-through', 30)
    H.label(b, (16, 700), 'orange line = where the wires run', 26, fill=(200, 90, 0))
    b = H.caption(b, 'Blue: the rear cap (stays still). Orange part: the fork (turns with the arm). The wires cross from one to the other through the hole in the middle.', 27)
    # c) the rig at the same angle
    rig, _ = rig_in_model(135.0)
    Fr = np.array([RX, RY - 8.0, -45.0])
    c = H.shot(rig, 'roll_where_c', Fr + (eyeb - Fz) * 0.42, Fr, size=(800, 760), angle=24)
    H.label(c, (16, 14), 'The rig, same view, enlarged', 30)
    c = H.caption(c, 'The rig is just that crossing, lifted out: blue base = the cap side, orange top = the fork side, the tube = the hole in the middle.', 27)
    return H.row([a, b, c])


def panel_parts():
    top_print = TOP.copy()
    top_print.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1, 0, 0)))
    top_print.apply_translation((0, 0, 25.0))
    a = rig_shot('roll_part_base', [(BASE, C1, 1.0)], size=(1190, 700))
    H.label(a, (16, 14), 'BASE   fixtures_cable_rig_roll_axis_base', 30)
    a = H.caption(a, 'Flat disc down, tube up, exactly as it prints. The slot is the channel the wires lie in.', 27)
    b = rig_shot('roll_part_top', [(top_print, C2, 1.0)], eye=(75, -165, 125), focal=(0, -8, 4), size=(1190, 700))
    H.label(b, (16, 14), 'TOP   fixtures_cable_rig_roll_axis_top', 30)
    b = H.caption(b, 'Shown as it prints: flat roof down. Turn it over to use it. The ring fits over the base\'s tube.', 27)
    return H.row([a, b], gap=20)


def panel_assembly():
    up = TOP.copy()
    up.apply_translation((0, 0, 26.0))
    arr = H.arrow((0, 0, 40.0), (0, 0, 27.0), 1.2)
    a = rig_shot('roll_asm_a', [(BASE, C1, 1.0), (rotz(up, 85.0), C2, 1.0), (arr, (0.2, 0.2, 0.2), 1.0)], focal=(0, 8, 22), eye=(80, 175, 140), size=(1190, 760))
    H.label(a, (16, 14), '1. Top goes over the tube, roof up', 30)
    b = rig_shot('roll_asm_b', [(BASE, C1, 1.0), (rotz(TOP, 85.0), C2, 1.0)], size=(1190, 760))
    H.label(b, (16, 14), '2. Together. The top turns freely on the tube', 30)
    return H.caption(H.row([a, b], gap=20), 'No screw, no glue. The base lies flat on the bench; hold it down with one hand or tape it to the bench. The top just sits on the tube and turns.', 27)


def panel_wires():
    ims = []
    for th, name in ((146.0, 'Arm down against the body'), (85.0, 'Half way'), (25.0, 'Arm lifted fully out sideways')):
        it = [(BASE, C1, 1.0), (rotz(TOP, th), C2, 0.45)] + rig_wires(th)
        im = rig_shot(f'roll_wires_{int(th)}', it, eye=(40, 150, 200), focal=(0, 10, 8), size=(786, 700), angle=34)
        H.label(im, (14, 12), name, 28)
        ims.append(im)
    r = H.row(ims, gap=20)
    return H.caption(r, 'Red and black: the two thick power wires. Yellow and blue: the two thin twisted signal pairs. They lie in the base\'s channel, go up the tube, and leave along the top\'s channel. '
                        'Pale yellow strips: tape, holding the wires down in each channel about 25 mm from the middle of the tube. The top is drawn see-through so the wires show. '
                        'Turning the top between the two end pictures is the whole test: the wires twist inside the tube.', 27)


def sketch_good_bad(w=1120, h=470):
    im = Image.new('RGB', (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    f = H.fontb(30)
    d.text((40, 16), 'GOOD', fill=(20, 130, 40), font=f)
    d.text((w // 2 + 40, 16), 'BAD', fill=(190, 30, 30), font=f)
    d.line((w // 2, 10, w // 2, h - 10), fill=(180, 180, 180), width=2)
    for i, col in enumerate(((215, 30, 30), (20, 20, 20), (235, 185, 30))):
        pts = [(60 + t * 4.2, 200 + 46 * math.sin(t / 26.0 + i * 0.5) * (1 - abs(t - 55) / 110) + (i - 1) * 26) for t in range(0, 111)]
        d.line(pts, fill=col, width=9, joint='curve')
    for i, t in enumerate(('Smooth, even twist.', 'No sharp bend. Marks not moved.', 'Turns with a light touch.')):
        d.text((40, h - 130 + i * 36), t, fill=(20, 20, 20), font=H.font(26))
    x0 = w // 2 + 60
    d.line([(x0, 150), (x0 + 150, 152), (x0 + 215, 165), (x0 + 232, 215), (x0 + 205, 232), (x0 + 228, 250), (x0 + 300, 262), (x0 + 450, 264)], fill=(215, 30, 30), width=9, joint='curve')
    d.ellipse((x0 + 180, 180, x0 + 262, 262), outline=(190, 30, 30), width=4)
    d.text((x0 + 268, 172), 'kink', fill=(190, 30, 30), font=H.fontb(26))
    d.line([(x0, 210), (x0 + 450, 300)], fill=(20, 20, 20), width=9)
    d.line([(x0, 300), (x0 + 450, 205)], fill=(235, 185, 30), width=7)
    for i, t in enumerate(('A kink, or a wire climbing over another.', 'A white mark or flat spot on a wire.', 'It springs back, or needs force.')):
        d.text((x0 - 20, h - 130 + i * 36), t, fill=(20, 20, 20), font=H.font(26))
    return im


def text_block(lines, width, sz=30, pad=22, bg=(246, 248, 252)):
    f, fb = H.font(sz), H.fontb(sz)
    tmp = Image.new('RGB', (width, 10))
    d = ImageDraw.Draw(tmp)
    out_lines = []
    for bold, text in lines:
        fo = fb if bold else f
        cur = ''
        for wd in text.split():
            t = (cur + ' ' + wd).strip()
            if d.textlength(t, font=fo) > width - 2 * pad and cur:
                out_lines.append((bold, cur))
                cur = wd
            else:
                cur = t
        out_lines.append((bold, cur))
    lh = int(sz * 1.38)
    im = Image.new('RGB', (width, len(out_lines) * lh + 2 * pad), bg)
    d = ImageDraw.Draw(im)
    for i, (bold, t) in enumerate(out_lines):
        d.text((pad, pad + i * lh), t, fill=(20, 20, 20), font=fb if bold else f)
    return im


def panel_test():
    steps = text_block([
        (True, '1  Thread.'), (False, 'Lay the wires in the base\'s channel, up through the tube, and out. Lower the top over them so they lie in its channel.'),
        (True, '2  Tape.'), (False, 'Turn the top to half way (about 85 degrees from the base\'s channel: count the marks on the base, one every 10 degrees). Tape the wires down in both channels, neither tight nor slack.'),
        (True, '3  Mark.'), (False, 'Draw a line across each wire where it goes into the tube and where it comes out.'),
        (True, '4  Turn.'), (False, 'Swing the top slowly between the two end positions (25 and 146 degrees from the base\'s channel), five times, watching. Then 200 times by hand.'),
        (True, '5  Look.'), (False, 'Lift the top off and look at the wires and your marks. (The top\'s roof covers the tube, so you cannot see in from above while it is on: look in along the channel, or lift it.)'),
    ], 1250)
    return H.row([steps, sketch_good_bad()], gap=30)


def panel_deck():
    a = rig_shot('roll_deck_parts', [(TRAY, C3, 1.0)], eye=(120, -190, 170), focal=(0, 0, 4), size=(560, 470), angle=30)
    H.label(a, (12, 10), 'TRAY  ..._roll_deck_tray', 22)
    lid_print = LID.copy()
    lid_print.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1, 0, 0)))
    lid_print.apply_translation((0, 0, 9.5))
    b = rig_shot('roll_deck_lid', [(lid_print, C4, 1.0)], eye=(120, -190, 170), focal=(0, 0, 4), size=(560, 470), angle=30)
    H.label(b, (12, 10), 'LID  ..._roll_deck_lid (as printed)', 22)
    # spiral: about 1.2 turns from the outer anchor (135 deg, r 41.5) inward to the post (270 deg, r 32.5)
    t = np.linspace(math.radians(135), math.radians(135 - 430), 120)
    rr = np.linspace(41.5, 32.5, 120)
    it = [(TRAY, C3, 1.0), (LID, C4, 0.35)]
    for dz, r_, col in ((1.6, 1.5, RED), (4.7, 1.5, BLACK)):
        it.append((R.tube(np.c_[rr * np.cos(t), rr * np.sin(t), np.full(120, dz)], r_), col, 1.0))
    it.append((R.tube(np.c_[(rr - 2.6) * np.cos(t), (rr - 2.6) * np.sin(t), np.full(120, 1.2)], 0.9), PAIR, 1.0))
    c = rig_shot('roll_deck_asm', it, eye=(60, -150, 230), focal=(0, 0, 4), size=(620, 470), angle=30)
    H.label(c, (12, 10), 'Together, lid see-through, wires as a spiral', 22)
    txt = text_block([
        (True, 'Second rig: the spiral. Only if the first test fails.'),
        (False, 'The wires are tied at the gap in the tray\'s outer wall, laid about one and a quarter turns round the tray against the wall, and tied to the two holes in the lid beside its post. '
                'One M4 x 16 screw and nut through the middle, left loose enough to turn. Turn the lid between the tray\'s two stops: the spiral should wind in and open out without bunching.'),
    ], 620, sz=24)
    return H.row([a, b, c, txt], gap=14)


def main():
    fr, sh = H.torso_meshes()
    # the shared overview: front three-quarter and back three-quarter
    F = np.array([40.0, 330.0, 0.0])
    it = H.shoulder_scene() + [(fr, H.FRAMEC2, 1.0), (sh, H.SHELLC, 0.40)]
    ov = H.row([H.caption(H.label(H.shot(it, 'ov_front', F + np.array([650.0, 250.0, 900.0]), F, size=(1200, 1120), angle=30), (16, 14), 'From the front', 32), 'Front three-quarter view.', 26),
                H.caption(H.label(H.shot(it, 'ov_back', F + np.array([620.0, 230.0, -880.0]), F, size=(1200, 1120), angle=30), (16, 14), 'From behind', 32), 'Back three-quarter view.', 26)])
    ov = H.column([H.heading('Left shoulder and upper arm on the torso', ov.width, 40,
                             'Torso frame rev A with its shell (shown see-through), shoulder as built in CAD today, upper arm frozen at its last release'), ov])
    ov.save(H.OUT / 'shoulder_on_torso.png')
    print('saved', H.OUT / 'shoulder_on_torso.png', ov.size)

    parts = [
        H.heading('ROLL CABLE RIG: what it is and how to run it', W, 52, 'Print fixtures_cable_rig_roll.3mf. This page is the first rig (two parts). The second pair on the plate is only needed if this test fails.'),
        H.heading('1  Where it comes from', W, 36), panel_where(),
        H.heading('2  The two parts', W, 36), panel_parts(),
        H.heading('3  How they go together', W, 36), panel_assembly(),
        H.heading('4  The wires, at the two ends of travel and half way', W, 36), panel_wires(),
        H.heading('5  The test', W, 36), panel_test(),
        H.heading('The other two parts on the plate', W, 30), panel_deck(),
    ]
    parts = [p if p.width == W else p.resize((W, int(p.height * W / p.width)), Image.LANCZOS) for p in parts]
    sheet = H.column(parts, gap=10)
    sheet.save(H.OUT / 'HOWTO_roll.png', optimize=True)
    print('saved', H.OUT / 'HOWTO_roll.png', sheet.size)


if __name__ == '__main__':
    main()
