"""Collapse sliver facets in an exported STL: for every facet whose area is at or under the integrity check's limit
(tools/cad/mesh_check.integrity, 1e-6 mm2), its shortest edge is collapsed (one end moved onto the other in every facet
that uses it) and the facets that degenerate are dropped. Repeated until none is left. The result must pass the
integrity check, or nothing is written.

    python stl_sliver_fix.py IN.STL OUT.STL
"""
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools' / 'cad'))
import mesh_check as MC  # noqa: E402


def fix(src, dst, tol=1e-6):
    m = trimesh.load(str(src), process=False)
    v = np.asarray(m.vertices, float)
    key = np.round(v / 1e-5).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    vv = np.zeros((len(uniq), 3))
    vv[inv] = v
    f = inv[np.asarray(m.faces)]
    n0, moved = len(f), 0
    for _ in range(50):
        a = np.linalg.norm(np.cross(vv[f[:, 1]] - vv[f[:, 0]], vv[f[:, 2]] - vv[f[:, 0]]), axis=1) / 2
        bad = np.flatnonzero(a <= tol)
        if not len(bad):
            break
        t = f[bad[0]]
        e = [(np.linalg.norm(vv[t[i]] - vv[t[(i + 1) % 3]]), t[i], t[(i + 1) % 3]) for i in range(3)]
        _, keep, drop = min(e)
        f = np.where(f == drop, keep, f)
        f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])]
        moved += 1
    out = trimesh.Trimesh(vertices=vv, faces=f, process=False)
    vol0, vol1 = abs(trimesh.load(str(src)).volume), abs(out.volume)
    tmp = Path(str(dst) + '.tmp.stl')
    out.export(str(tmp))
    ok, lines, _ = MC.integrity_file(tmp)
    print(f'{Path(src).name}: {n0} facets, {moved} edge(s) collapsed, {len(f)} facets; volume {vol0:.1f} -> {vol1:.1f} mm3')
    print('  ' + lines[0])
    if not ok or abs(vol1 - vol0) > 0.5:
        tmp.unlink()
        raise SystemExit('not written: the result does not pass')
    tmp.replace(dst)
    return moved


if __name__ == '__main__':
    fix(sys.argv[1], sys.argv[2])
