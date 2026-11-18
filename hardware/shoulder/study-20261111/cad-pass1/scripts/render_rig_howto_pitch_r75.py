"""Add-on to the pitch rig's how-to (checks/cable_rigs/HOWTO_pitch_r75.png): the narrow-channel tray and lid for the
150 mm shell opening what-if, beside the first pair. Rendered from the cadquery parts; no SolidWorks.

    python render_rig_howto_pitch_r75.py        (under capped.py)
"""
import numpy as np
from PIL import Image

import howto_common as H
from howto_common import C1, C2
import render_rig_howto_roll as RR
import cable_rigs as CR

mesh, text_block = RR.mesh, RR.text_block
RO2 = 68.5


def pair(ro, tag):
    tray, lid = mesh(CR.pitch_tray(ro)), mesh(CR.pitch_lid(ro))
    lid_up = lid.copy()
    lid_up.apply_translation((0, 0, 45.0))
    F = np.array([0.0, 12.0, 10.0])
    a = H.shot([(tray, C1, 1.0)], f'pr75_{tag}_top', F + np.array([0.0, 0.0, 520.0]), F, size=(900, 820), angle=26, up=(0, 1, 0))
    b = H.shot([(tray, C1, 1.0), (lid_up, C2, 1.0)], f'pr75_{tag}_iso', F + np.array([260.0, -300.0, 330.0]), F + np.array([0, 0, 15.0]), size=(900, 820), angle=26, up=(0, 0, 1))
    return a, b


def main():
    a1, b1 = pair(None, 'first')
    a2, b2 = pair(RO2, 'r75')
    H.label(a1, (14, 12), 'FIRST TRAY: channel 16.1 mm, shell opening 160', 26)
    H.label(a2, (14, 12), 'NARROW TRAY "_r75": channel 11.1 mm, shell opening 150', 26)
    H.label(b1, (14, 12), 'first tray with its lid lifted', 24)
    H.label(b2, (14, 12), 'narrow tray with its own lid lifted (mouth at mid channel)', 24)
    top = H.row([a1, a2])
    bot = H.row([b1, b2])
    w = top.width
    txt = text_block([
        (True, 'What it is for'),
        (False, 'A smaller opening in the body shell (150 mm instead of 160) would leave the pitch cable 11.1 mm of channel instead of 16.1. '
                'The narrow tray has only its outer wall moved in by 5 mm. Inner wall, depth, guide finger, slot, tongue and clamp holes are the same.'),
        (True, 'Print'),
        (False, 'fixtures_cable_rig_pitch_tray_r75.3mf (28.8 g, 46 min) and fixtures_cable_rig_pitch_lid_r75.3mf (8.2 g, 28 min). PLA, no supports, as the other rigs. '
                'Use the narrow tray with the narrow lid; the centre screw and nut are the same M4.'),
        (True, 'Test'),
        (False, 'Run tests E (spiral) and F (wrap and loop) from HOWTO_pitch.png on both pairs with the same wires. '
                'Expect about 45 to 60 degrees from test E on the narrow tray against about 90 to 115 on the first. Test F should behave the same on both. Report the angles side by side.'),
    ], w)
    head = H.heading('Pitch cable rig: the narrow tray for a 150 mm shell opening (add-on to HOWTO_pitch)', w, 44)
    sheet = H.column([head, top, bot, txt], gap=10)
    sheet = sheet.resize((2400, int(sheet.height * 2400 / sheet.width)), Image.LANCZOS)
    sheet.save(H.OUT / 'HOWTO_pitch_r75.png', optimize=True)
    print('saved', H.OUT / 'HOWTO_pitch_r75.png', sheet.size)


if __name__ == '__main__':
    main()
