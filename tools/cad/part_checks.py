"""Geometry checks for a printed part that need the mesh: support on visible faces and interference with a mating part.
Two of the checks tools/cad/gate.py runs (conventions/part-lifecycle.md). Needs numpy and trimesh.

support() is ported from the left-arm build scripts (cad/scripts/arm/support_check.py), written after the one-piece upper arm
printed with rough supported outer skin and support trapped in its cavity (2026-11-08).
interference() was missing when an RS02 tab lip met the printed upper arm about 1 mm deep (2026-11-08).
"""

import numpy as np
import trimesh


def support(m, up, limit=45.0, bed_tol=0.3, ref=None):
    """Faces that need support in the print orientation `up` (overhang past `limit` degrees, not on the bed), split into
    visible outer faces and hidden ones. A face is outer when a ray from it along its normal escapes `ref` (the assembled
    outer body; default the part itself), so the cut faces of a clamshell half that look into the closed link don't count.
    Returns (dict of areas in mm2, outer face mask, hidden face mask)."""
    up = np.asarray(up, float)
    up /= np.linalg.norm(up)
    n, c, a = m.face_normals, m.triangles_center, m.area_faces
    h = c @ up
    h0 = (m.vertices @ up).min()
    need = (n @ up < -np.cos(np.radians(limit))) & ~(h - h0 < bed_tol)
    o = c[need] + n[need] * 0.05
    r = m if ref is None else ref
    hit = r.ray.intersects_any(o, n[need]) if need.any() else np.zeros(0, bool)
    outer = np.zeros(len(n), bool)
    outer[np.flatnonzero(need)[~hit]] = True
    hidden = need & ~outer
    areas = dict(
        support_mm2=round(float(a[need].sum()), 1),
        outer_mm2=round(float(a[outer].sum()), 1),
        hidden_mm2=round(float(a[hidden].sum()), 1),
    )
    if outer.any():
        cc = c[outer]
        areas['outer_where'] = [cc.min(0).round(1).tolist(), cc.max(0).round(1).tolist()]
    return areas, outer, hidden


def interference(part, other, samples=20000, seed=0):
    """Deepest point of `part` inside `other` and of `other` inside `part`, both meshes in the same (assembly) coordinates.
    Touching faces read about 0; a positive depth is overlap. Returns (depth mm, location)."""
    worst = (0.0, None)
    for a, b in ((part, other), (other, part)):
        pts, _ = trimesh.sample.sample_surface_even(a, samples, seed=seed)
        pts = np.vstack([pts, a.vertices])
        lo, hi = b.bounds
        pts = pts[np.all((pts >= lo - 1e-6) & (pts <= hi + 1e-6), axis=1)]
        if not len(pts):
            continue
        d = trimesh.proximity.signed_distance(b, pts)  # positive inside b
        i = int(np.argmax(d))
        if d[i] > worst[0]:
            worst = (float(d[i]), pts[i].round(2).tolist())
    return worst
