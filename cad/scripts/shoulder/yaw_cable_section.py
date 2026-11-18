"""YAW_CABLE_SECTION.png: where the yaw cable goes between the RS02 and the hub. Left: true section through the yaw axis
and the cable window (68 deg) of the exported meshes (hub, fork front, fork rear) and the placed RS02 model. Right: plan
of the dish from the motor side with the cable's path. Prints the gaps it measures from the meshes.

    python yaw_cable_section.py [--measure]
"""
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import trimesh

from dims import RX, YZ, HUB_WIN_A
from swk import CAD, WIP

OUT = CAD.parent / 'hardware' / 'shoulder' / 'study-20261111' / 'checks' / 'hub_print' / 'YAW_CABLE_SECTION.png'
EXP = CAD / 'exports' / 'shoulder'
CACHE = WIP / 'yaw_section_rs02.pkl'


def rs02():
    if CACHE.exists():
        return pickle.loads(CACHE.read_bytes())
    import check_clearance as CC
    from build_asm import T_RS02
    m = CC.mesh_step(CC.VENDOR / 'vendor_robstride_rs02.step', T_RS02)
    CACHE.write_bytes(pickle.dumps(m))
    return m


def section(m, a_deg):
    """Closed loops of the mesh cut by the plane through the yaw axis at a_deg, as (s, Y) arrays; s is the signed distance
    from the axis along the a_deg direction."""
    t = math.radians(a_deg)
    u = np.array((math.cos(t), 0.0, math.sin(t)))
    n = np.array((-math.sin(t), 0.0, math.cos(t)))
    sec = m.section(plane_origin=(RX, 300.0, YZ), plane_normal=n)
    out = []
    if sec is None:
        return out
    for e in sec.discrete:
        p = np.asarray(e)
        out.append(np.column_stack(((p - (RX, 0, YZ)) @ u, p[:, 1])))
    return out


def main():
    parts = dict(hub=trimesh.load(EXP / 'shoulder_hub_left.STL'), fork_front=trimesh.load(EXP / 'shoulder_fork_front_left.STL'),
                 fork_rear=trimesh.load(EXP / 'shoulder_fork_rear_left.STL'), rs02=rs02())
    secs = {k: section(m, HUB_WIN_A) for k, m in parts.items()}
    pickle.dump(secs, open(WIP / 'yaw_section_loops.pkl', 'wb'))
    for k, m in parts.items():
        p = m.vertices
        r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ)
        print(k, 'verts', len(p), 'Y', p[:, 1].min().round(2), p[:, 1].max().round(2), 'r max', r.max().round(2), 'loops at 68', len(secs[k]))
    # measured figures
    h = parts['hub'].vertices; rh = np.hypot(h[:, 0] - RX, h[:, 2] - YZ)
    print('hub top face Y', h[:, 1].max().round(3), ': radii of vertices on it', rh[h[:, 1] > h[:, 1].max() - 0.01].min().round(2), rh[h[:, 1] > h[:, 1].max() - 0.01].max().round(2))
    for y0 in (318.36,):
        k = abs(h[:, 1] - y0) < 0.02
        print('hub dish floor Y', y0, 'radii', rh[k].min().round(2), rh[k].max().round(2))
    print('hub rim: max r of hub above Y 316:', rh[h[:, 1] > 316].max().round(2), 'rim top Y', h[rh > 38.4][:, 1].max().round(2))
    m = parts['rs02']; p = m.vertices; r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ)
    print('rs02 lowest Y', p[:, 1].min().round(3))
    for lo, hi in ((0, 10), (10, 20), (20, 23), (23, 24), (24, 25.5), (25.5, 30), (30, 36), (36, 42), (42, 50)):
        k = (r >= lo) & (r < hi)
        if k.any():
            print('  rs02 r %g-%g: lowest Y %.3f' % (lo, hi, p[k, 1].min()))
    c, nrm = m.triangles_center, m.face_normals
    rc = np.hypot(c[:, 0] - RX, c[:, 2] - YZ)
    for y0 in np.unique(np.round(c[(nrm[:, 1] < -0.99) & (c[:, 1] < 330), 1], 2)):
        k = (nrm[:, 1] < -0.99) & (abs(c[:, 1] - y0) < 0.02)
        print('  rs02 downward flat face at Y %.2f: r %.2f-%.2f, area %.0f mm2' % (y0, rc[k].min(), rc[k].max(), m.area_faces[k].sum()))
    for k_ in ('fork_front', 'fork_rear'):
        p = parts[k_].vertices; r = np.hypot(p[:, 0] - RX, p[:, 2] - YZ)
        k = (p[:, 1] > 314.6) & (p[:, 1] < 323.5)
        print(k_, 'smallest r between Y 314.6 and 323.5:', r[k].min().round(2) if k.any() else None, ' lowest Y within r 45:', p[r < 45][:, 1].min().round(2) if (r < 45).any() else None)


if __name__ == '__main__':
    main()
