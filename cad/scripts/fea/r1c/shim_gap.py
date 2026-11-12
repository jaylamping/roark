"""R1e shim-body contact check (2026-11-12): axial opening between the shim underside and the arm's end face, per 30 deg sector,
from the nodal displacements (p3_fea FEA_SAVE_DISP). Opening > 0 = the ring lifted off the arm (no-penetration contact working);
~0 everywhere with axial tension in the ring = bonded behaviour.
    python shim_gap.py STRESS_NPZ POST_TXT DISP_NPZ [y_face=301.3]      (run under capped.py)"""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
d = np.load(sys.argv[1])
s = d['s']
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[2]).read().split('\n')[0])
body = {}
for nm, a, b in runs:
    for i in s[int(a):int(b) + 1, 0].astype(int):
        body[i] = nm
u = np.load(sys.argv[3])
pos, U = u['pos'], u['u']
yf = float(sys.argv[4]) if len(sys.argv) > 4 else 301.3
nb = np.array([body.get(int(i), '?') for i in U[:, 0]])
r = np.hypot(pos[:, 0] - HX, pos[:, 2] - CZ)
th = np.degrees(np.arctan2(pos[:, 2] - CZ, pos[:, 0] - HX)) % 360
face = (np.abs(pos[:, 1] - yf) < 0.03) & (r > 36.3) & (r < 38.3)
sh, ar = np.flatnonzero(face & (nb == 'shim')), np.flatnonzero(face & (nb == 'arm'))
print('face nodes shim', len(sh), 'arm', len(ar))
dist, j = cKDTree(pos[ar][:, [0, 2]]).query(pos[sh][:, [0, 2]])
gap = U[sh, 2] - U[ar[j], 2]      # UY shim - UY arm (the shim sits on +Y of the arm face)
slip = np.hypot(U[sh, 1] - U[ar[j], 1], U[sh, 3] - U[ar[j], 3])
print('pair distance max %.3f mm' % dist.max())
for a in range(0, 360, 30):
    k = (th[sh] >= a) & (th[sh] < a + 30)
    print('th %3d-%3d  opening mean %+.4f max %+.4f min %+.4f mm  slip mean %.4f mm' % (a, a + 30, gap[k].mean(), gap[k].max(), gap[k].min(), slip[k].mean()))
print('overall opening max %+.4f min %+.4f mm; nodes open > 0.001 mm: %d of %d' % (gap.max(), gap.min(), int((gap > 0.001).sum()), len(gap)))
