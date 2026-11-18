"""Superpose two solved hub cases on the same mesh (linear statics): OUT = a * A + b * B, node by node.

    python hub_combine.py A B a b OUT        (names of npz files in cad/_sim/shoulder, without the extension)

Used for the combined arm-horizontal + yaw case at another yaw load: HUBL_G90 + k * HUBL_YAW_COP. Stops if the two meshes
are not the same nodes (count, and positions within 1e-3 mm). von Mises is recomputed from the summed components.
"""
import sys

import numpy as np

import fea_shoulder as FS

A, B, a, b, OUT = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
za, zb = np.load(str(FS.F / f'{A}.npz')), np.load(str(FS.F / f'{B}.npz'))
pa, pb = za['pos'], zb['pos']
if pa.shape != pb.shape or np.abs(pa - pb).max() > 1e-3:
    raise SystemExit(f'meshes differ: {pa.shape} against {pb.shape}' + ('' if pa.shape != pb.shape else f', largest node offset {np.abs(pa - pb).max():.4f} mm'))
s = a * za['s'] + b * zb['s']
# columns as fea_shoulder.run stores them: 0 node id, 1-3 sigma x y z, 4 txy, 5 txz, 6 tyz, 7-9 principals, 10 von Mises, 11 intensity
s[:, 0] = za['s'][:, 0]
sx, sy, sz, txy, txz, tyz = (s[:, i] for i in (1, 2, 3, 4, 5, 6))
s[:, 10] = np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3.0 * (txy ** 2 + txz ** 2 + tyz ** 2))
s[:, 7:10] = np.nan          # principals and intensity do not superpose; not used by the lug read-out
s[:, 11] = np.nan
out = {k: za[k] for k in za.files}
out['s'] = s
np.savez_compressed(str(FS.F / f'{OUT}.npz'), **out)
print(f'{OUT}: {a:g} x {A} + {b:g} x {B}, {len(pa)} nodes')
