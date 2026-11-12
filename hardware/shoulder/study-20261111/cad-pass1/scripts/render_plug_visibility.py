"""Is the RS02 plug (worst credible: XT30(2+2)-F on the 173 deg socket, 15.5 x 6.2 footprint, up to Y 371.1, plus leads
leaving sideways at Y 369.6 toward the back) visible from normal views of the real parts? Plug in orange.
python render_plug_visibility.py OUTDIR"""
import math
import sys
from pathlib import Path

import numpy as np
import trimesh

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
a = math.radians(173.0)
c = np.array([RX + 34.4 * math.cos(a), (360.1 + 371.1) / 2, YZ + 34.4 * math.sin(a)])
plug = trimesh.creation.box(extents=(6.2, 11.0, 15.5))                     # radial (~X) x height x tangential (~Z)
plug.apply_translation(c)
lead = trimesh.creation.box(extents=(4.0, 3.0, 14.0)); lead.apply_translation(c + np.array([0.0, 4.0, -14.0]))   # sideways, toward the back
ORANGE = (0.95, 0.55, 0.1)
it = [(m, R.COL[k], 1.0) for k, m in R.P.items() if k != 'cover'] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
it += [(plug, ORANGE, 1.0), (lead, ORANGE, 1.0)]
F = np.array([RX - 30, 368.0, 0.0])
for vn, eye in (('inboard_side', F + np.array([-600.0, 0.0, 0.0])), ('front_inboard34', F + np.array([-420.0, 60.0, 420.0])),
                ('back_inboard34', F + np.array([-420.0, 60.0, -420.0])), ('front', F + np.array([30.0, 20.0, 600.0])),
                ('back', F + np.array([30.0, 20.0, -600.0])), ('below_inboard', F + np.array([-380.0, -300.0, 150.0]))):
    R.render(it, OUT / f'vis_{vn}.png', eye, F, size=(1000, 1000), angle=24, title='Worst-credible RS02 plug on the 173 deg socket (orange): ' + vn)
print('done')
