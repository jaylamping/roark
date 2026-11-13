import sys, numpy as np, trimesh
from shapely.geometry import LineString, Point
HX, CZ = 170.49, 5.985875
X = sys.argv[1]
ms = [trimesh.load(X + '/upper_arm_organic_front_left.STL'), trimesh.load(X + '/upper_arm_organic_back_left.STL')]
print('Y band survey: at each theta, material runs (r_in-r_out) along the ray from the hub axis, r 33-50; both halves')
for y in (294.5, 295.5, 296.2, 297.0, 297.7):
    polys = []
    for m in ms:
        s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if s is None: continue
        p2, T = s.to_planar(to_2D=np.array([[1,0,0,-HX],[0,0,1,-CZ],[0,-1,0,y],[0,0,0,1]]) if False else None, normal=[0,1,0])
        # use 3D path directly: collect polygons in (x,z)
        for ent in s.discrete:
            polys.append(np.c_[ent[:, 0] - HX, ent[:, 2] - CZ])
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    P = [Polygon(q).buffer(0) for q in polys if len(q) > 3]
    # even-odd: build region as symmetric difference of all loops
    reg = None
    for q in P:
        reg = q if reg is None else reg.symmetric_difference(q)
    out = []
    for th in range(0, 360, 10):
        d = np.array([np.cos(np.radians(th)), np.sin(np.radians(th))])
        ray = LineString([tuple(33 * d), tuple(50 * d)])
        g = reg.intersection(ray)
        segs = [g] if g.geom_type == 'LineString' else list(getattr(g, 'geoms', []))
        rr = []
        for sg in segs:
            if sg.is_empty: continue
            c = np.array(sg.coords); r = np.hypot(c[:, 0], c[:, 1]); rr.append('%.1f-%.1f' % (r.min(), r.max()))
        out.append('%3d:%s' % (th, ','.join(rr) or '-'))
    print('Y %.1f' % y)
    for i in range(0, len(out), 6): print('   ' + '  '.join(out[i:i + 6]))
