"""Per-part SF from a saved clamshell FEA (<case>.npz, written by p3_fea.py): nodes assigned to the nearest printed part,
each part judged with its own layer normal, points within 4.5 mm of the loaded carrier-screw holes and the fixture face
excluded. Prints one JSON line per case.

    python cad/scripts/fea/fea_parts.py clam_GLm clam_GLp ...
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

CAD = Path(__file__).resolve().parents[2]
FEA = CAD / '_sim' / 'upper-arm'
EXP = CAD / 'exports' / 'upper-arm'
PARTS = {'front': ('upper_arm_shell_front_left', (0, 0, 1)), 'back': ('upper_arm_shell_back_left', (0, 0, 1)),
         'ring': ('upper_arm_elbow_ring_left', (1, 0, 0)), 'hub': ('upper_arm_hub_left', (0, 1, 0))}
YIELD, LAYER = 45.0, 0.5
# The bonded model joins the ring to the halves, which makes a re-entrant edge along X 166.35, Y 242.1 (ring outer end face
# against the skirt trim plane). In the printed parts that is the 0.1 mm kerf between ring and halves, and the halves' edge
# there is convex: the peak on it is a model artefact and grows with refinement (front layer SF 1.72 / 1.62 / 1.16 at
# 3 / 2 / 1.5 mm, lateral case). Nodes within 3 mm of that edge (along Z) are excluded.
KERF_EDGE = (166.35, 242.1, 3.0)
CY, CZ = 209.860668, 5.985875
meshes = {k: trimesh.load(str(EXP / (v[0] + '.stl')), force='mesh') for k, v in PARTS.items()}
# loaded carrier-screw holes: r 1.65 holes along X in the ring. A hole-wall triangle's outward normal points at the axis.
ring = meshes['ring']
c, nrm = ring.triangles_center, ring.face_normals
w = (np.abs(nrm[:, 0]) < 0.05) & (c[:, 0] > 150) & (c[:, 0] < 167)
ax = c[w][:, 1:] + 1.65 * nrm[w][:, 1:]
cnt = np.array([(np.linalg.norm(ax - p, axis=1) < 0.1).sum() for p in ax])
ctr = []
for p in ax[np.argsort(-cnt)]:
    if all(np.linalg.norm(p - q) > 1.0 for q in ctr) and (np.linalg.norm(ax - p, axis=1) < 0.1).sum() >= 8:
        ctr.append(p)
holes = np.vstack([np.c_[x * np.ones(len(ctr)), np.array(ctr)] for x in np.arange(150.0, 167.5, 0.5)])
print('loaded holes found:', len(ctr), [np.round(q, 1).tolist() for q in ctr])
trees = [cKDTree(trimesh.sample.sample_surface_even(m, int(m.area / 0.0625))[0]) for m in meshes.values()]
for case in sys.argv[1:]:
    z = np.load(str(FEA / (case + '.npz')))
    pos, s = z['pos'], z['s']
    vm = s[:, 10]
    S = s[:, 1:7]
    d = np.stack([t.query(pos)[0] for t in trees], 1)      # nearest surface sample (0.25 mm spacing) per part
    owner = np.argmin(d, 1)
    # exclusions: fixture face (Y >= 315.36) and the loaded hole surfaces (nodes within 4.5 mm of r 1.65 hole walls in the ring)
    ex = pos[:, 1] >= 319.86 - 4.5
    out = {}
    for i, (k, (nm, n)) in enumerate(PARTS.items()):
        mk = (owner == i) & ~ex
        mk &= cKDTree(holes).query(pos)[0] >= 4.5 + 1.65
        mk &= np.hypot(pos[:, 0] - KERF_EDGE[0], pos[:, 1] - KERF_EDGE[1]) >= KERF_EDGE[2]
        n = np.array(n, float)
        sn = n[0] ** 2 * S[:, 0] + n[1] ** 2 * S[:, 1] + n[2] ** 2 * S[:, 2] + 2 * (n[0] * n[1] * S[:, 3] + n[0] * n[2] * S[:, 4] + n[1] * n[2] * S[:, 5])
        j = np.flatnonzero(mk)[np.argmax(vm[mk])]
        l = np.flatnonzero(mk)[np.argmax(sn[mk])]
        out[k] = dict(bulk=round(YIELD / vm[j], 2), at=pos[j].round(1).tolist(), layer=round(YIELD * LAYER / max(sn[l], 1e-9), 2), layer_at=pos[l].round(1).tolist())
    print(case, json.dumps(out))
