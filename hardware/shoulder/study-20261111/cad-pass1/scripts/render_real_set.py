"""Picture set of the real parts as they are now: side (outboard, inboard), back, rear three-quarter, front, front
three-quarter. python render_real_set.py OUTDIR"""
import sys
from pathlib import Path

import numpy as np

import render_pass1 as R
from dims import *

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
F = np.array([RX, 360.0, -5.0])
Fb = np.array([RX, 345.0, -20.0])
it = [(m, R.COL[k], 1.0) for k, m in R.P.items() if k != 'cover'] + [(m, R.COL[k], 1.0) for k, m in R.M.items()]
it += [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else R.DARK, 1.0) for n, m in R.UA.items()]
for vn, eye, foc in (('side_out', F + np.array([640.0, 0.0, 0.0]), F), ('side_in', F + np.array([-640.0, 0.0, 0.0]), F),
                     ('back', Fb + np.array([0.0, 20.0, -660.0]), Fb), ('back34', Fb + np.array([400.0, 60.0, -560.0]), Fb),
                     ('front', F + np.array([0.0, 30.0, 640.0]), F), ('front34', F + np.array([420.0, 90.0, 560.0]), F)):
    R.render(it, OUT / f'real_{vn}.png', eye, foc, size=(1100, 1200), angle=32, title='Real parts: r 47 sleeve, true-wrap front, stop rev 2, six-screw joint')
    print(vn, flush=True)
print('done')
