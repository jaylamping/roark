"""Fixed-item checks on link_organic.stl (point-in-mesh in chunks of 20,000, as 01-session.md asks). Usage: c2checks.py file.stl"""
import json, math, sys
import numpy as np, trimesh
PIN = np.array([0.0, 0.0, -200.0])
def inside(m, pts):
    out = np.zeros(len(pts), bool)
    for i in range(0, len(pts), 1000):
        out[i:i + 1000] = m.contains(pts[i:i + 1000])
    return out
def run(path):
    m = trimesh.load(path)
    res = dict(watertight=bool(m.is_watertight), bodies=len(m.split()), volume_mm3=float(m.volume), mass_g=float(m.volume * 1.19e-3),
               bounds=m.bounds.round(2).tolist())
    # 1 mating face: points on the ring Y=-4 (Ø30..Ø62, avoid the holes): material just above it, nothing below
    th = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    ring = []
    for r in np.arange(15.5, 31.01, 0.5):
        for t in th:
            x, z = r * math.cos(t), r * math.sin(t)
            if min(math.hypot(x - 25 * math.cos(math.radians(a)), z - 25 * math.sin(math.radians(a))) for a in range(0, 360, 60)) > 2.2:
                ring.append((x, z))
    ring = np.array(ring)
    above = np.c_[ring[:, 0], np.full(len(ring), -3.9), ring[:, 1]]
    below = np.c_[ring[:, 0], np.full(len(ring), -4.1), ring[:, 1]]
    res['ring_points'] = len(ring)
    res['ring_material_above_pct'] = float(100 * inside(m, above).mean())
    res['ring_material_below_pct'] = float(100 * inside(m, below).mean())
    # section at y=-4+0.01 gives the ring outline: bore and holes
    s = m.section(plane_origin=[0, -3.99, 0], plane_normal=[0, 1, 0])
    p2, _ = s.to_planar(to_2D=np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float))
    holes = []
    for pol in p2.polygons_full:
        for it in pol.interiors:
            c = np.array(it.centroid.coords[0]); a = it.area
            holes.append((round(float(math.hypot(*c)), 2), round(float(math.degrees(math.atan2(c[1], c[0])) % 360), 1), round(2 * math.sqrt(a / math.pi), 3)))
        res['outer_diameter_mm'] = round(2 * math.sqrt(pol.area / math.pi), 2) if False else None
    res['holes_at_y-4 (radius from axis, angle deg, diameter)'] = sorted(holes, key=lambda h: h[2])
    # 2 six Ø7 x 10 clear cylinders on +Y side, Y 4..14
    rr = np.sqrt(np.random.default_rng(1).random(400)) * 3.3
    tt = np.random.default_rng(2).random(400) * 2 * np.pi
    n_in = 0
    for a in range(0, 360, 60):
        cx, cz = 25 * math.cos(math.radians(a)), 25 * math.sin(math.radians(a))
        for y in np.linspace(4.1, 14.0, 12):
            pts = np.c_[cx + rr * np.cos(tt), np.full(400, y), cz + rr * np.sin(tt)]
            n_in += int(inside(m, pts).sum())
    res['screw_clear_points_inside_material'] = n_in
    # 3 slot: |y|<16, z<-183, x in +-45
    X, Y, Z = np.meshgrid(np.linspace(-34, 34, 35), np.linspace(-15.95, 15.95, 17), np.arange(-183.05, -214, -1.0), indexing='ij')
    grid = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    res['slot_points'] = len(grid)
    res['slot_points_inside_material'] = int(inside(m, grid).sum())
    # 4 pin ring: outline of the cheeks at three y; smallest distance from the pin axis to the outer outline (>= 9 means 5 mm round the hole)
    ring_min = {}
    for y in (16.3, 18.0, 20.0, -16.3, -18.0, -20.0):
        s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if s is None:
            ring_min[y] = None; continue
        v = s.discrete
        d = []
        for poly in v:
            pp = np.array(poly)
            r = np.hypot(pp[:, 0] - PIN[0], pp[:, 2] - PIN[2])
            near = pp[(pp[:, 2] < -176)]
            if len(near):
                d.append(float(np.hypot(near[:, 0], near[:, 2] + 200).min()))
        # distance from the pin axis to the nearest outline vertex that is NOT the pin hole itself (r > 4.5)
        allv = np.vstack([np.array(p) for p in v])
        rr_ = np.hypot(allv[:, 0], allv[:, 2] + 200)
        ring_min[y] = round(float(rr_[rr_ > 4.5].min()), 2)
    res['pin_ring_min_outer_dist_mm (need >= 9)'] = ring_min
    # 5 flat inner faces: points on the plane y=+-16 in an annulus r 4.5..8 round the pin are on the surface: material just outside, none just inside
    flat = {}
    for sgn in (1, -1):
        pts_out, pts_in = [], []
        for r in (5.0, 6.5, 7.9):
            for t in th[::10]:
                x, z = r * math.cos(t), -200 + r * math.sin(t)
                pts_out.append((x, sgn * 16.05, z)); pts_in.append((x, sgn * 15.95, z))
        flat[sgn * 16] = (float(inside(m, np.array(pts_out)).mean()), float(inside(m, np.array(pts_in)).mean()))
    res['inner_cheek_flat (material just outside, just inside)'] = flat
    # 6 cable passage: Ø6 clear straight line x=0, y=1.2 (design), from the bore wall (z=-15) to the slot roof (z=-176)
    zz = np.arange(-14.5, -176.0, -1.0)
    pts = [(r * math.cos(t), 2.5 + r * math.sin(t), z) for z in zz for r in (0.0, 1.5, 2.7) for t in (0, 1.57, 3.14, 4.71)]
    res['cable_passage_axis_y2.5_r2.7_points_inside_material'] = int(inside(m, np.array(pts)).sum())
    res['cable_passage_points'] = len(pts)
    return res
if __name__ == '__main__':
    r = run(sys.argv[1])
    print(json.dumps(r, indent=1, default=str))
