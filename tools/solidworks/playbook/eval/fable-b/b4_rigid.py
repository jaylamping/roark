"""Fit a rigid-body motion (translation + small rotation about the point (0, 0, 14)) to the tongue's nodal displacements."""
import sys
import numpy as np
from common import ROOT
z = np.load(ROOT / 'cad' / '_sim' / 'sw-eval' / 'fable-b' / f'{sys.argv[1]}.npz')
p, U = z['pos'], z['disp']
t = (np.abs(p[:, 0]) <= 4.001) & (p[:, 2] >= 8.099) & (np.abs(p[:, 1]) <= 10.001)
r = p[t] - np.array([0, 0, 14.0])
u = U[t, 1:4]
A = np.zeros((3 * len(r), 6)); b = u.reshape(-1)
for k in range(3):
    A[k::3, k] = 1
A[0::3, 4], A[0::3, 5] = r[:, 2], -r[:, 1]          # ux = tx + wy*z - wz*y
A[1::3, 5], A[1::3, 3] = r[:, 0], -r[:, 2]          # uy = ty + wz*x - wx*z
A[2::3, 3], A[2::3, 4] = r[:, 1], -r[:, 0]          # uz = tz + wx*y - wy*x
x, *_ = np.linalg.lstsq(A, b, rcond=None)
res = (A @ x - b).reshape(-1, 3)
print(sys.argv[1], 'translation mm', x[:3].round(4).tolist(), 'rotation rad (about X, Y, Z)', x[3:].round(5).tolist(),
      'largest elastic part mm', float(np.abs(res).max().round(4)))
