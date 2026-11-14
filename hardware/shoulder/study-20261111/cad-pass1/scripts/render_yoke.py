"""Yoke fork front sheet (checks/size_audit/YOKE.png): today's shoulder above, the finished yoke below (look build
LOOK=yokeS, cad/_wip/shoulder-pass1/stl_look_yokeS), then the yoke at roll +90 and at the -11 stop, and the figures.
Plastic opaque white, motors dark, the real outer shell solid, the organic upper arm on the hub.

    python render_yoke.py [RING_STL]     (under capped.py)

RING_STL: a flange ring look build drawn on the yoke rows instead of today's ring (rim B). The pitch cable cover is drawn
in the shell's white on the yoke rows (Joey's pick, colour only) and grey, as on the earlier sheets, on today's row.
"""
import json
import math
import sys

import numpy as np
import trimesh
from PIL import Image

import howto_common as H
from howto_common import R, RX, RY
import render_shoulder_with_shell as S

WIP = H.REPO / 'cad' / '_wip' / 'shoulder-pass1'
FIGS = WIP / 'yoke_figs.json'           # {"lines": [...]} written by the strength post-processing; drawn as the last block
ROLLS = ('fork_front', 'fork_rear', 'hub', 'access_plugs')      # what turns with the roll joint (with the RS02 and the arm)
COVERC = (0.62, 0.64, 0.67)


def rolled(m, deg):
    if not deg:
        return m
    m = m.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(deg), (0, 0, 1), (RX, RY, 0.0)))
    return m


def items(ff, sh, roll=0.0, ring=None, white_cover=False, small=False):
    it = []
    for k, m in R.P.items():
        m = ff if k == 'fork_front' else (ring if (k == 'ring' and ring is not None) else m)
        if small and k in ('ring', 'cover'):
            m = shrunk(m, k)
        it.append((rolled(m, roll) if k in ROLLS else m, H.PARTC if (k != 'cover' or white_cover) else COVERC, 1.0))
    it += [(rolled(m, roll) if k == 'rs02' else m, H.MOTORC, 1.0) for k, m in R.M.items()]
    it += [(rolled(m, roll), H.ARMC if n != 'rs02_ring' else H.MOTORC, 1.0) for n, m in R.UA.items()]
    return it + [(sh, S.SHELL_COL, 1.0)]


def shrunk(m, kind, d=5.0):
    """What-if for a 150 mm opening, picture only: the cover's outer wall and the ring's rim pulled in by d about the pitch
    axis (the channel r 57.4-73.5 squeezed to r 57.4-68.5; everything outside it moved in by d)."""
    m = m.copy()
    v = m.vertices
    dy, dz = v[:, 1] - RY, v[:, 2] - S.PZ
    r = np.hypot(dy, dz)
    r0, r1 = (57.4, 73.5) if kind == 'cover' else (55.0, 77.5)
    rn = np.where(r <= r0, r, np.where(r >= r1, r - d, r0 + (r - r0) * (r1 - d - r0) / (r1 - r0)))
    k = np.where(r > 1e-6, rn / np.maximum(r, 1e-6), 1.0)
    v[:, 1], v[:, 2] = RY + dy * k, S.PZ + dz * k
    return m


def text_block(lines, width, sz=30):
    im = Image.new('RGB', (width, 28 + len(lines) * int(sz * 1.42)), (255, 255, 255))
    for i, ln in enumerate(lines):
        H.label(im, (22, 14 + i * int(sz * 1.42)), ln, sz, bold=ln.endswith(':'), box=False)
    return im


def main():
    ring = trimesh.load(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != '-' else None
    sh = S.outer_shell()
    yk = trimesh.load(WIP / 'stl_look_yokeS' / 'fork_front.stl')      # the yoke with the solid neck (same outside as LOOK=yoke)
    F = np.array([70.0, 350.0, 0.0])
    Fc = np.array([RX, RY - 12.0, 30.0])
    views = [('Front three-quarter', F + np.array([560.0, 200.0, 780.0]), F, 28, (760, 760)),
             ('Back three-quarter', F + np.array([540.0, 180.0, -760.0]), F, 28, (760, 760)),
             ('Straight from the front', F + np.array([0.0, 0.0, 1000.0]), F, 28, (760, 760)),
             ('Straight from the left side', F + np.array([1000.0, 0.0, 0.0]), F, 28, (760, 760)),
             ('Close, from the front', Fc + np.array([120.0, 60.0, 430.0]), Fc, 26, (900, 760))]
    rows = []
    for tag, title, ff, rg, wc in (('today', 'TODAY: the fork front covers the roll motor\'s whole face', R.P['fork_front'], None, False),
                                   ('yoke', 'YOKE: nothing above the hub; six of the drum\'s eight lip screws show, evenly, round the roll motor\'s dark face', yk, ring, True)):
        ims = []
        for i, (name, eye, foc, ang, size) in enumerate(views):
            im = H.shot(items(ff, sh, 0.0, rg, wc), f'yoke_{tag}_{i}', eye, foc, size=size, angle=ang)
            H.label(im, (12, 10), name, 24)
            ims.append(im)
        r = H.row(ims)
        g = abs(ff.volume) * 1.27e-3
        rows.append(H.column([H.heading(title, r.width, 32, f'fork front {g:.0f} g'), r], gap=6))
    # the yoke moving: roll +90 (arm straight out) and the -11 stop (arm swung in against the body)
    Fr = np.array([RX, RY - 30.0, 10.0])
    ims = []
    for roll, nm in ((90.0, 'roll +90: arm straight out'), (-11.0, 'roll -11: at the inward stop'), (45.0, 'roll +45')):
        for j, (vn, eye, ang, size) in enumerate((('front three-quarter', Fr + np.array([420.0, 190.0, 640.0]), 30, (640, 760)), ('straight from the front', Fr + np.array([0.0, 0.0, 800.0]), 30, (640, 760)))):
            if roll == 45.0 and j == 0:
                continue
            im = H.shot(items(yk, sh, roll, ring, True), f'yoke_roll{int(roll)}_{j}', eye, Fr, size=size, angle=ang)
            H.label(im, (12, 10), f'{nm}, {vn}', 22)
            ims.append(im)
    r3 = H.row(ims)
    rows.append(H.column([H.heading('The yoke moving: the drum and its screws stay with the body, the yoke turns over them', rows[0].width, 32), r3], gap=6))
    # what the opened area shows, close: as built, and with a dark cover ring pressed into the drum's lip (r 24.5-43, Z 33.5-36),
    # which closes the 7 mm slot between the RS03's turning face (to r 36) and the lip's bore (r 43)
    cov = trimesh.creation.annulus(r_min=24.5, r_max=42.8, height=2.5, sections=120)
    cov.apply_translation((RX, RY, 34.75))
    Fz = np.array([RX, RY + 4.0, 36.0])
    ims = []
    for nm, extra in (("as built: the motor's turning face, and the slot round it", []), ('with a dark cover ring in the lip (an option, not built)', [(cov, (0.13, 0.13, 0.14), 1.0)])):
        for j, eye in enumerate((Fz + np.array([70.0, 50.0, 300.0]), Fz + np.array([150.0, 150.0, 190.0]))):
            im = H.shot(items(yk, sh, 0.0, ring, True) + extra, f'yoke_cov{len(ims)}', eye, Fz, size=(940, 760), angle=24)
            H.label(im, (12, 10), nm, 22)
            ims.append(im)
    r5 = H.row(ims)
    rows.append(H.column([H.heading('What the opened area shows', rows[0].width, 32), r5], gap=6))
    # what-if: the shell opening at 150 mm (r 75), the cover's band and the ring's rim 5 mm smaller (mesh edit, picture only)
    sh75 = S.outer_shell(75.0)
    ims = []
    for i, (name, eye, foc, ang, size) in enumerate(views):
        im = H.shot(items(yk, sh75, 0.0, ring, True, True), f'yoke_150_{i}', eye, foc, size=size, angle=ang)
        H.label(im, (12, 10), name, 24)
        ims.append(im)
    r4 = H.row(ims)
    rows.append(H.column([H.heading('WHAT-IF, not a design: the shell opening at 150 mm instead of 160 (cover band r 70.9, ring r 72.5)', r4.width, 32,
                                    'Picture only: the meshes pulled in. It leaves an 11.1 mm cable channel instead of 16.1; what that does to the pitch cable is in checks/PITCH_OPENING_150.md'), r4], gap=6))
    if FIGS.exists():
        lines = json.loads(FIGS.read_text(encoding='utf-8'))['lines']
        rows.append(H.column([H.heading('Figures', rows[0].width, 32), text_block(lines, rows[0].width)], gap=6))
    head = H.heading('Shoulder fork front as a yoke (look build in CAD; the real part is unchanged)', rows[0].width, 46,
                     'Same motors, joints, bearings, screws and reach. Outer body shell of 2026-11-06 with the opening drawn in; organic upper arm on the hub. '
                     + ('Flange ring with the rolled rim B and the cable cover in white on the yoke rows.' if ring is not None else ''))
    sheet = H.column([head] + rows, gap=10)
    sheet = sheet.resize((3000, int(sheet.height * 3000 / sheet.width)), Image.LANCZOS)
    sheet.save(S.OUT / 'YOKE.png', optimize=True)
    print('saved', S.OUT / 'YOKE.png', sheet.size)


if __name__ == '__main__':
    main()
