"""Repair needle triangles in an exported STL without moving the surface: a zero-area triangle whose three vertices are
collinear (A, M, B with M on AB) is a T-junction the CAD tessellator closed with a flat sliver. The neighbour across AB,
(A, B, C), is split at M into (A, M, C) and (M, B, C), and the needle is dropped. The vertices and the surface are unchanged;
the mesh stays watertight. Then mesh_check.integrity is run on the result.
python mesh_fix_needles.py IN.stl [OUT.stl]   (OUT defaults to IN)"""
import os
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesh_check as MC


def fix(path_in, path_out=None, area_tol=1e-6):
    raw = trimesh.load(path_in, process=False)
    key = np.round(raw.vertices / 1e-5).astype(np.int64)
    uk, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    V = np.zeros((len(uk), 3))
    V[inv] = raw.vertices
    F = inv[raw.faces].copy()
    a = np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1) / 2
    needles = np.where(a <= area_tol)[0]
    drop, add, fixed = set(), [], 0
    for i in needles:
        t = F[i]
        # M: the vertex nearest the segment of the other two (the middle one)
        best = None
        for k in range(3):
            A_, M_, B_ = t[(k + 1) % 3], t[k], t[(k + 2) % 3]
            ab = V[B_] - V[A_]
            s = np.dot(V[M_] - V[A_], ab) / max(np.dot(ab, ab), 1e-30)
            if 0.0 < s < 1.0:
                dist = np.linalg.norm(V[A_] + s * ab - V[M_])
                if best is None or dist < best[0]:
                    best = (dist, A_, M_, B_)
        if best is None:
            continue
        _, A_, M_, B_ = best
        # the neighbour sharing edge A-B (not the needle itself)
        nb = np.where(((F == A_).any(1)) & ((F == B_).any(1)))[0]
        nb = [j for j in nb if j != i and j not in drop]
        if len(nb) != 1:
            continue
        j = nb[0]
        tj = list(F[j])
        C_ = [q for q in tj if q not in (A_, B_)][0]
        # keep the neighbour's winding: replace it by the two halves in the same orientation
        ia, ib = tj.index(A_), tj.index(B_)
        if (ib - ia) % 3 == 1:          # neighbour runs A -> B -> C
            add += [[A_, M_, C_], [M_, B_, C_]]
        else:                           # neighbour runs B -> A -> C
            add += [[B_, M_, C_], [M_, A_, C_]]
        drop.update((i, j))
        fixed += 1
    keep = np.array([k for k in range(len(F)) if k not in drop], int)
    F2 = np.vstack([F[keep], np.array(add, int).reshape(-1, 3)])
    m = trimesh.Trimesh(V, F2, process=False)
    out = path_out or path_in
    m.export(out)
    ok, lines, det = MC.integrity_file(out)
    return fixed, len(needles), ok, lines


if __name__ == '__main__':
    n, tot, ok, lines = fix(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f'needles repaired {n} of {tot}')
    print('\n'.join(lines))
    sys.exit(0 if ok else 1)
