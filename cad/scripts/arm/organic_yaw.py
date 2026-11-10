"""Yaw-stage changes for concept A, on the draft 4 parts (local frame: forearm axis along Y through the origin).

Clock spring: a reverse-wound flat flex ribbon (FFC, up to 9 mm wide, 0.1 mm thick) in the annulus between the turning tube's
collar (r 21.5) and the static sleeve bore, between the two 6808s. The sleeve bore there opens from r 26.05 to r 27.6, so the
ribbon's U-turn has a 3.05 mm bend radius, and that also takes 11 g out of the sleeve. The ribbon enters the tube bore through
the tube's existing back window (Y 45-55) and leaves the coil up the sleeve's back groove, past the upper bearing, through the
RS00 ring's back slot and the belly rim's cable channel; the groove and the ring slot widen from 15 and 13 deg to 24 deg
(11.5 mm) to take it flat.

Cone-and-cuff wrist (chosen 2026-11-10): the sleeve gets a 1.2 mm cone skin from Ø72 at the ring to Ø68 at the lower bearing
band, closing a void round its barrel; under the skin the barrel thins from r 31 to r 30 between the bearings, since the skin
now shares the bending. The wrist cap gets a Ø70.4 cuff down to the wrist flange's face, 0.8 mm clear of the flange's
yaw-stop tab (r 33.2), so the end reads as one band and a flat face.

    python organic_yaw.py [sleeve ring cone cuff]   (each step runs once on the draft 4 file; groove_lip is a fix-up)
"""
import math
import shutil
import sys
from pathlib import Path

import numpy as np

import organic_master as M
from organic_master import fine_stl, sw
from swg import *

CAD = M.CAD
DIR = CAD / 'forearm'
EXP = CAD / 'exports' / 'forearm'
BORE = dict(r=27.6, y0=32.4, y1=68.3)        # clock-spring bore between the bearing seats (Y 24.4-31.4 and 69.3-76.3)
GROOVE = dict(r0=24.3, r1=28.5, a0=258.0, a1=282.0)      # through the upper lip too, as the original groove
RING_SLOT = dict(r0=24.4, r1=33.5, a0=258.0, a1=282.0)


def open_part(name):
    p = DIR / f'forearm_{name}_left.SLDPRT'
    e, w = L(), L()
    d = sw.OpenDoc6(str(p), 1, 1, '', e, w)
    if d is None:
        raise SystemExit(f'open {p}: {e.value}')
    return d, p


def y_revolve0(d, name, prof, cut):
    """Revolve an (r, y) profile about the local Y axis (through the origin)."""
    with Sk(d, plane(d, 'Z', 0.0, name + '_P'), name) as s:
        s.poly([(r, y, 0.0) for r, y in prof])
        centerline(s, (0.0, -10.0, 0.0), (0.0, 120.0, 0.0))
    return revolve(d, s.feat, name, None, cut)


def arc_band_y(d, name, r0, r1, a0, a1, y0, y1, cut, n=40):
    ym = (y0 + y1) / 2
    pts = [(r1 * math.cos(math.radians(a)), r1 * math.sin(math.radians(a))) for a in np.linspace(a0, a1, n)]
    pts += [(r0 * math.cos(math.radians(a)), r0 * math.sin(math.radians(a))) for a in np.linspace(a1, a0, n)]
    with Sk(d, plane(d, 'Y', ym, name + '_P'), name) as s:
        s.poly([(x, ym, z) for x, z in pts])
    return feat(d, s.feat, name, abs(y1 - y0), cut, mode=MID, lo=0.01)


def finish(d, p, name):
    d.ForceRebuild3(False)
    print('  bodies', bodies(d), flush=True)
    e, w = L(), L()
    d.Save3(1, e, w)
    for ext in ('.stl', '.step'):
        d.Extension.SaveAs(str(EXP / (p.stem + ext)), 0, 1, NUL, e, w)
    sw.CloseDoc(d.GetTitle)


def sleeve():
    d, p = open_part('sleeve')
    y_revolve0(d, 'CLOCK_BORE', [(25.5, BORE['y0']), (BORE['r'], BORE['y0']), (BORE['r'], BORE['y1']), (25.5, BORE['y1'])], True)
    arc_band_y(d, 'RIBBON_GROOVE', GROOVE['r0'], GROOVE['r1'], GROOVE['a0'], GROOVE['a1'], 31.0, 84.6, True)
    finish(d, p, 'sleeve')


def ring():
    d, p = open_part('rs00_ring')
    arc_band_y(d, 'RIBBON_SLOT', RING_SLOT['r0'], RING_SLOT['r1'], RING_SLOT['a0'], RING_SLOT['a1'], 84.0, 90.6, True)
    finish(d, p, 'rs00_ring')


def groove_lip():
    """Run the widened back groove through the upper lip too (r 24.3), as the original groove does."""
    d, p = open_part('sleeve')
    arc_band_y(d, 'RIBBON_GROOVE_LIP', 24.3, 26.1, GROOVE['a0'], GROOVE['a1'], 75.5, 84.6, True)
    finish(d, p, 'sleeve')


def cone():
    d, p = open_part('sleeve')
    y_revolve0(d, 'CONE_SKIN', [(34.0, 24.4), (36.0, 84.3), (34.8, 84.3), (32.8, 24.4)], False)
    y_revolve0(d, 'BARREL_THIN', [(30.0, 37.0), (31.2, 37.0), (31.2, 63.0), (30.0, 63.0)], True)
    finish(d, p, 'sleeve')


def cuff():
    d, p = open_part('wrist_cap')
    y_revolve0(d, 'CUFF', [(34.0, 14.9), (35.2, 14.9), (35.2, 24.3), (33.9, 24.3), (33.9, 21.5), (34.0, 21.5)], False)
    finish(d, p, 'wrist_cap')


if __name__ == '__main__':
    for k in sys.argv[1:] or ('sleeve', 'ring'):
        print('==', k, flush=True)
        globals()[k]()
