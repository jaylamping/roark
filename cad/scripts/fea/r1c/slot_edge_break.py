"""Slot edge break study (2026-11-12): the shoulder thread adds an R1.2 fillet at the hub lug roots (lug Z faces at CZ +- 5 meeting
the spigot underside at Y 296). Our post faces (the slot walls) sit at Z = CZ +- 5.1 up to the post top (Y 295.7), so their top
edges need breaking. For a 45 deg chamfer and for a round, both 1.4: clearance to the fillet (section in Y-Z), bearing area lost
on the lug-facing post faces (from the printed-half and hub meshes), and the distance to the insert / clearance hole mouth and
the fin tops.
    python slot_edge_break.py FRONT_STL BACK_STL HUB_STL"""
import json
import sys

import numpy as np
import trimesh

CZ = 5.985875
LUG_HZ, CL = 5.0, 0.1
FACE = LUG_HZ + CL          # post face, from the seam plane
POST_TOP = 295.7            # R1d trimmed post top
SPIGOT = 296.0              # hub spigot underside (lug root)
FR = 1.2                    # shoulder thread's lug-root fillet radius
BREAK = 1.4
COLS = [(147.5, 292.0), (193.5, 292.0)]
FIN_TOP = 291.4             # organic_parts.HUB_POST_Y: the fins run from here down to Y 276


def fillet_material(n=400):
    """Section points of the hub's fillet material (z measured from the seam, outward): inside the corner square, outside the arc."""
    c = np.array([LUG_HZ + FR, SPIGOT - FR])
    zs, ys = np.meshgrid(np.linspace(LUG_HZ, LUG_HZ + FR, n), np.linspace(SPIGOT - FR, SPIGOT, n))
    pts = np.c_[zs.ravel(), ys.ravel()]
    return pts[np.linalg.norm(pts - c, axis=1) >= FR]


def post_section(kind, n=600):
    """Post section points near the corner (z >= FACE, y <= POST_TOP) after the edge break."""
    zs, ys = np.meshgrid(np.linspace(FACE, FACE + 4.0, n), np.linspace(POST_TOP - 4.0, POST_TOP, n))
    pts = np.c_[zs.ravel(), ys.ravel()]
    if kind == 'chamfer':
        keep = (pts[:, 1] - POST_TOP) <= -(BREAK - (pts[:, 0] - FACE))      # below the 45 deg line through (FACE, top - B), (FACE + B, top)
    elif kind == 'round':
        c = np.array([FACE + BREAK, POST_TOP - BREAK])
        corner = (pts[:, 0] < c[0]) & (pts[:, 1] > c[1])
        keep = ~corner | (np.linalg.norm(pts - c, axis=1) <= BREAK)
    else:
        keep = np.ones(len(pts), bool)
    return pts[keep]


def clearance(kind):
    from scipy.spatial import cKDTree
    return float(cKDTree(fillet_material()).query(post_section(kind))[0].min())


def section(m, z):
    """The mesh's cross-section polygons in the plane Z = z, as a shapely geometry in (X, Y). Plane sections only: a full
    point-in-mesh test over the half meshes needed tens of GB (2026-11-12)."""
    from shapely.ops import unary_union
    sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        return None
    planar, to3d = sec.to_2D()
    polys = []
    for poly in planar.polygons_full:
        pts3 = trimesh.transform_points(np.c_[np.asarray(poly.exterior.coords), np.zeros(len(poly.exterior.coords))], to3d)
        holes = [trimesh.transform_points(np.c_[np.asarray(h.coords), np.zeros(len(h.coords))], to3d)[:, :2] for h in poly.interiors]
        from shapely.geometry import Polygon
        polys.append(Polygon(pts3[:, :2], holes))
    return unary_union(polys)


def bearing(front, back, hub):
    """Lug-facing post face area per post: the post's section just behind its face intersected with the lug's section just in
    front of it, near each lug; and the part of it above POST_TOP - BREAK (removed by the break)."""
    from shapely.geometry import box
    out = {}
    for half, m, sg in (('front', front, 1), ('back', back, -1)):
        post_sec = section(m, CZ + sg * (FACE + 0.05))
        lug_sec = section(hub, CZ + sg * (LUG_HZ - 0.05))
        for x0, y0 in COLS:
            win = box(x0 - 10, 284.0, x0 + 10, 296.5)
            both = post_sec.intersection(lug_sec).intersection(win)
            a = both.area
            cut = both.intersection(box(x0 - 10, POST_TOP - BREAK, x0 + 10, 296.5)).area
            pb = post_sec.intersection(win).bounds
            out[f'{half} X{x0:.0f}'] = dict(bearing_mm2=round(a, 1), removed_mm2=round(cut, 1), removed_pct=round(100 * cut / a, 1) if a else None,
                                            contact_Y=[round(both.bounds[1], 2), round(both.bounds[3], 2)] if a else None,
                                            contact_X=[round(both.bounds[0], 2), round(both.bounds[2], 2)] if a else None,
                                            post_section_bounds=[round(v, 2) for v in pb])
    return out


if __name__ == '__main__':
    front, back, hub = (trimesh.load(f) for f in sys.argv[1:4])
    res = {'fillet': f'R{FR} at the lug root (lug face |Z| {LUG_HZ}, spigot underside Y {SPIGOT})', 'post': f'face |Z| {FACE}, top Y {POST_TOP}',
           'clearance_to_fillet_mm': {k: round(clearance(k), 3) for k in ('none', 'chamfer', 'round')},
           'break_lowest_Y_on_face': round(POST_TOP - BREAK, 2),
           'insert_hole_top_Y (front, Dia 4.0)': COLS[0][1] + 2.0, 'clearance_hole_top_Y (back, Dia 3.4)': COLS[0][1] + 1.7,
           'fin_top_Y': FIN_TOP}
    res['ligament_on_face_to_insert_mouth_mm'] = round(POST_TOP - BREAK - (COLS[0][1] + 2.0), 2)
    res['ligament_on_face_to_back_hole_mm'] = round(POST_TOP - BREAK - (COLS[0][1] + 1.7), 2)
    res['bearing'] = bearing(front, back, hub)
    print(json.dumps(res, indent=1))
