"""Mesh checks for a printed part: one of the checks tools/cad/gate.py runs (conventions/part-lifecycle.md).

Ported from the left-arm build scripts (cad/scripts/arm/mesh_check.py), where each check was added after a defect reached
a print: spikes, slivers, then shallow notches (2026-11-07).

Fails unless:
  - the part is one watertight body (or the allowed body count for listed multi-body parts),
  - no vertex has an angle defect above 150 deg, except whitelisted design corners,
  - no knife edge: no pair of adjacent faces folded past 170 deg along an edge longer than 1 mm,
    except whitelisted spots,
  - no sampled wall thinner than 0.6 mm over 0.5 mm2 or more, except whitelisted boxes,
  - for parts with a turned or lofted outer surface (whitelist key 'revolve'): no radial deviation
    from the ideal surface over 0.03 mm, inward or outward, across 1 mm2 or more, outside whitelisted
    (angle, Y) boxes. This catches shallow notches and steps that no vertex or thickness test sees.

Needle triangles (min angle under 1 deg, edge over 2 mm) are counted and listed, not failed:
CAD tessellation makes thousands of them on flat fans, so a needle only matters when it forms a
knife edge or a thin wall, which the two checks above catch.

Whitelists are per part, in cad/manifests/mesh-whitelist.json: a point (or box) in the coordinates of the exported mesh,
plus a reason. Needs numpy, scipy and trimesh (pip install numpy scipy trimesh rtree).
"""
import numpy as np
import trimesh

DEFECT = 150.0
FOLD = 170.0
THIN = 0.6
THIN_AREA = 0.5


def _near(p, wl, r=1.5):
    return [w for w in wl if 'pt' in w and np.linalg.norm(np.asarray(p) - w['pt']) <= w.get('r', r)]


def _inbox(lo, hi, wl):
    out = []
    for w in wl:
        if 'box' in w:
            a, b = np.asarray(w['box'][0]), np.asarray(w['box'][1])
            if np.all(lo >= a - 1e-6) and np.all(hi <= b + 1e-6):
                out.append(w)
    return out


def thickness(m, chunk=3000):
    n = m.face_normals
    c = m.triangles_center - n * 0.005
    it = trimesh.ray.ray_triangle.RayMeshIntersector(m)
    th = np.full(len(c), np.inf)
    for s in range(0, len(c), chunk):
        loc, ri, _ = it.intersects_location(c[s:s + chunk], -n[s:s + chunk], multiple_hits=False)
        th[s + ri] = np.linalg.norm(loc - c[s:s + chunk][ri], axis=1)
    return th


def check(mesh, name, bodies=1, corners=(), folds=(), thin=(), revolve=None):
    """mesh: trimesh.Trimesh or (vertices, faces). Returns (ok, report text)."""
    m = mesh if isinstance(mesh, trimesh.Trimesh) else trimesh.Trimesh(*mesh, process=True)
    rep, ok = [f'mesh check: {name}', f'faces {len(m.faces)}, bounds {m.bounds.round(2).tolist()}'], True
    parts = m.split(only_watertight=False)
    good = (bodies is None or len(parts) == bodies) and m.is_watertight
    rep.append(f'[{"PASS" if good else "FAIL"}] bodies {len(parts)} (allowed {bodies}), watertight {m.is_watertight}')
    ok &= good
    s = np.zeros(len(m.vertices))
    np.add.at(s, m.faces.ravel(), m.face_angles.ravel())
    defect = 360 - np.degrees(s)
    bad, known = [], []
    for i in np.where(defect > DEFECT)[0]:
        p = m.vertices[i]
        w = _near(p, corners)
        (known if w else bad).append((p.round(2).tolist(), round(float(defect[i])), w[0]['reason'] if w else ''))
    rep.append(f'[{"PASS" if not bad else "FAIL"}] sharp vertices over {DEFECT:.0f} deg: {len(bad)} unlisted, {len(known)} listed design corners')
    rep += [f'    UNLISTED {p} {d} deg' for p, d, _ in bad[:30]]
    rep += [f'    listed   {p} {d} deg: {r}' for p, d, r in known]
    ok &= not bad
    ang = np.degrees(m.face_adjacency_angles)
    el = np.linalg.norm(np.diff(m.vertices[m.face_adjacency_edges], axis=1)[:, 0], axis=1)
    fb, fk = [], []
    for j in np.where((ang > FOLD) & (el > 1.0))[0]:
        mid = m.vertices[m.face_adjacency_edges[j]].mean(0)
        w = _near(mid, folds, 2.0)
        (fk if w else fb).append((mid.round(2).tolist(), round(float(ang[j]), 1), round(float(el[j]), 1), w[0]['reason'] if w else ''))
    rep.append(f'[{"PASS" if not fb else "FAIL"}] knife edges (fold over {FOLD:.0f} deg, edge over 1 mm): {len(fb)} unlisted, {len(fk)} listed')
    rep += [f'    UNLISTED {p} fold {a} deg, edge {e} mm' for p, a, e, _ in fb[:30]]
    rep += [f'    listed   {p} fold {a} deg, edge {e} mm: {r}' for p, a, e, r in fk[:10]]
    ok &= not fb
    fl = m.edges_unique_length[m.faces_unique_edges].max(1)
    needle = (np.degrees(m.face_angles.min(1)) < 1) & (fl > 2)
    rep.append(f'[INFO] needle triangles (min angle under 1 deg, edge over 2 mm): {int(needle.sum())}, tessellation only unless a check above fails')
    th = thickness(m)
    k = np.where((th < THIN) & (m.area_faces > 0.02))[0]
    tb, tk = [], []
    if len(k):
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        adj = m.face_adjacency[np.isin(m.face_adjacency, k).all(1)]
        idx = {f: i for i, f in enumerate(k)}
        A = coo_matrix((np.ones(len(adj)), ([idx[a] for a in adj[:, 0]], [idx[b] for b in adj[:, 1]])), shape=(len(k), len(k)))
        _, lab = connected_components(A, directed=False)
        for j in np.unique(lab):
            f = k[lab == j]
            area = float(m.area_faces[f].sum())
            if area < THIN_AREA:
                continue
            v = m.triangles[f].reshape(-1, 3)
            lo, hi = v.min(0), v.max(0)
            w = _inbox(lo, hi, thin)
            (tk if w else tb).append((round(area, 1), round(float(th[f].min()), 2), lo.round(1).tolist(), hi.round(1).tolist(), w[0]['reason'] if w else ''))
    rep.append(f'[{"PASS" if not tb else "FAIL"}] walls thinner than {THIN} mm over {THIN_AREA} mm2: {len(tb)} unlisted, {len(tk)} listed')
    rep += [f'    UNLISTED {a} mm2, min {t} mm, box {lo} to {hi}' for a, t, lo, hi, _ in sorted(tb, reverse=True)[:30]]
    rep += [f'    listed   {a} mm2, min {t} mm, box {lo} to {hi}: {r}' for a, t, lo, hi, r in sorted(tk, reverse=True)]
    ok &= not tb
    if revolve:
        good, lines = surface_deviation(m, **revolve)
        rep += lines
        ok &= good
    rep.append(f'RESULT: {"PASS" if ok else "FAIL"}')
    return ok, '\n'.join(rep) + '\n'


DEV = 0.03
DEV_AREA = 1.0


def surface_deviation(m, center, y_range, step=(0.1, 0.5), boxes=()):
    """Radial scan of a surface of revolution about an axis along Y through center (x, z).
    The ideal radius at each Y is the median over the full turn, so the bare tube sets the reference.
    boxes: [{'ang': (a0, a1), 'y': (y0, y1), 'reason': ...}] in degrees (0 = +X, 90 = +Z) and mm."""
    from scipy import ndimage
    dy, da = step
    it = trimesh.ray.ray_triangle.RayMeshIntersector(m)
    ys = np.arange(y_range[0], y_range[1], dy)
    an = np.arange(0, 360, da)
    dv = np.c_[np.cos(np.radians(an)), np.zeros(len(an)), np.sin(np.radians(an))]
    R = np.full((len(ys), len(an)), np.nan)
    for i, y in enumerate(ys):
        o = np.c_[center[0] + dv[:, 0] * 200, np.full(len(an), y), center[1] + dv[:, 2] * 200]
        loc, ri, _ = it.intersects_location(o, -dv, multiple_hits=False)
        R[i, ri] = np.hypot(loc[:, 0] - center[0], loc[:, 2] - center[1])
    ref = np.nanmedian(R, axis=1)[:, None]
    dev = R - ref
    cell = np.radians(da) * ref * dy * np.ones_like(dev)
    lines, bad = [], []
    for sign, lab in ((1, 'proud'), (-1, 'sunk')):
        lb, n = ndimage.label(np.nan_to_num(sign * dev) > DEV)
        for j in range(1, n + 1):
            w = lb == j
            area = float(cell[w].sum())
            if area < DEV_AREA:
                continue
            ii, jj = np.where(w)
            y0, y1, a0, a1 = ys[ii.min()], ys[ii.max()], an[jj.min()], an[jj.max()]
            hit = [b for b in boxes if b['ang'][0] <= a0 and a1 <= b['ang'][1] and b['y'][0] <= y0 and y1 <= b['y'][1]]
            item = f'{lab} {area:.1f} mm2, max {float(np.nanmax(sign * dev[w])):.2f} mm, Y {y0:.1f}-{y1:.1f}, angle {a0:.1f}-{a1:.1f}'
            if hit:
                lines.append(f'    listed   {item}: {hit[0]["reason"]}')
            else:
                bad.append(f'    UNLISTED {item}')
    head = f'[{"PASS" if not bad else "FAIL"}] surface deviation over {DEV} mm across {DEV_AREA} mm2: {len(bad)} unlisted, {len(lines)} listed'
    return not bad, [head] + bad + lines

