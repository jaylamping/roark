"""Mesh gate and support-on-visible-face check for the upper-arm clamshell exports in their print orientations.
usage: python ua_gate_run.py [upper lower ring hub clip]; writes cad/_wip/arm-gate/."""
import sys, json, numpy as np, trimesh
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesh_check
from mesh_whitelist import WHITELIST
from support_check import check
from ua_names import EXPORTS, EXPORT, GATE

UP = {'upper': [0, 0, 1], 'lower': [0, 0, -1], 'ring': [1, 0, 0], 'hub': [0, -1, 0], 'clip': [0, -0.70710678, -0.70710678]}
load = lambda j: trimesh.load(str(EXPORTS / (EXPORT[j] + '.stl')), force='mesh')
ref = trimesh.util.concatenate([load(j) for j in ('upper', 'lower', 'ring', 'hub', 'carrier')])   # what can hide a face
GATE.mkdir(parents=True, exist_ok=True)
res = {}
for n in sys.argv[1:] or UP:
    m = load(n)
    wl = WHITELIST.get('ua_' + n if n != 'clip' else 'ua_loop_clip', {})
    ok, r = mesh_check.check(m, n, bodies=wl.get('bodies', 1), corners=wl.get('corners', ()), thin=wl.get('thin', ()))
    (GATE / f'{EXPORT[n]}_meshcheck.txt').write_text(r)
    s, outer, inner = check(m, UP[n], ref=ref if n != 'clip' else None)
    c = m.triangles_center[outer]
    s['outer_where'] = [[round(float(v), 1) for v in c.min(0)], [round(float(v), 1) for v in c.max(0)]] if len(c) else []
    res[n] = dict(mesh='PASS' if ok else 'FAIL', **s)
    print(n, res[n], flush=True)
    if not ok:
        print(r)
(GATE / 'summary.json').write_text(json.dumps(res, indent=1))
