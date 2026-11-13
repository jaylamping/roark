"""Re-export a saved part's fine STL (and STEP) with other tessellation settings until mesh_check.integrity passes.
python reexport_stl.py KEY [dev_mm,ang_deg ...]   e.g. fork_front 0.009,3 0.011,3 0.01,2.8"""
import os
import sys

from build_parts import NAMES, STL, STEPD
from swk import *

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools', 'cad'))
import mesh_check as MC

key = sys.argv[1]
tries = [tuple(t.split(',')) for t in sys.argv[2:]] or [('0.009', '3'), ('0.011', '3'), ('0.01', '2.8'), ('0.008', '2.5')]
e_, w_ = L(), L()
d = app().OpenDoc6(str(OUT / f'{NAMES[key]}.SLDPRT'), 1, 1, '', e_, w_)
try:
    for dev, ang in tries:
        os.environ['STL_DEV_MM'], os.environ['STL_ANG_DEG'] = dev, ang
        export(d, STL / f'{key}.stl')
        ok, lines, _ = MC.integrity_file(STL / f'{key}.stl')
        log(f'  STL {dev} mm / {ang} deg: ' + ' | '.join(l.strip() for l in lines))
        if ok:
            break
    export(d, STEPD / f'{key}.step', stl_fine=False)
finally:
    app().CloseAllDocuments(True)
    finish()
