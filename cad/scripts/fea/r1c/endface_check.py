"""End-face seat check (2026-11-12): radial profiles (r from the hub axis, Y) of the hub's spigot foot (spigot r 35.8 meeting the
disc underside at Y 302) and of our arm's bore-to-end-face edge, from plane sections at several angles, and the clearance between
them for a given end-face edge treatment (none / chamfer c / round R) on the arm.
    python endface_check.py HUB_STL [HUB_STL2] --arm ARM_STL      (run under capped.py)"""
import json
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875


def profile(m, theta_deg, rlo=35.0, rhi=37.8, ylo=300.8, yhi=302.6):
    """Surface points of mesh m in the radial half-plane at angle theta (from +X toward +Z), as (r, Y), densified."""
    t = np.radians(theta_deg)
    d = np.array([np.cos(t), 0.0, np.sin(t)])
    n = np.array([-np.sin(t), 0.0, np.cos(t)])
    sec = m.section(plane_origin=[HX, 0, CZ], plane_normal=n)
    if sec is None:
        return np.zeros((0, 2))
    pts = []
    for e in sec.entities:
        v = sec.vertices[e.points]
        for a, b in zip(v[:-1], v[1:]):
            k = max(2, int(np.linalg.norm(b - a) / 0.01))
            pts.append(np.linspace(a, b, k))
    q = np.vstack(pts)
    r = (q[:, 0] - HX) * d[0] + (q[:, 2] - CZ) * d[2]
    keep = (r > rlo) & (r < rhi) & (q[:, 1] > ylo) & (q[:, 1] < yhi)
    return np.c_[r[keep], q[keep, 1]]


def hub_foot(p):
    """From the hub profile: where the disc underside (Y ~ 302) starts (smallest r with Y > 301.99) and the spigot wall (largest
    r with Y < 301.5); the fillet lies between."""
    disc = p[(p[:, 1] > 301.99) & (p[:, 1] < 302.01)]
    wall = p[(p[:, 1] < 301.5)]
    return dict(disc_starts_r=round(float(disc[:, 0].min()), 3) if len(disc) else None,
                spigot_wall_r=round(float(np.median(wall[:, 0])), 3) if len(wall) else None,
                foot_height_at_r35_9=round(float(p[np.abs(p[:, 0] - 35.9) < 0.01, 1].max() - 302.0), 3) if (np.abs(p[:, 0] - 35.9) < 0.01).any() else None)


def arm_edge(kind, size, s=np.linspace(0, 1, 2001)):
    """Our arm's surface near the edge, as (r, Y): bore wall r 35.9 up to the edge treatment, then the end face Y 302 outward."""
    R0, Y0 = 35.9, 302.0
    if kind == 'chamfer':
        bore = np.c_[np.full(400, R0), np.linspace(300.8, Y0 - size, 400)]
        ch = np.c_[R0 + size * s, Y0 - size + size * s]
        face = np.c_[np.linspace(R0 + size, 37.8, 400), np.full(400, Y0)]
        return np.vstack([bore, ch, face])
    if kind == 'round':
        c = np.array([R0 + size, Y0 - size])
        a = np.linspace(np.pi, np.pi / 2, 400)
        arc = c + size * np.c_[np.cos(a), np.sin(a)]
        bore = np.c_[np.full(400, R0), np.linspace(300.8, Y0 - size, 400)]
        face = np.c_[np.linspace(R0 + size, 37.8, 400), np.full(400, Y0)]
        return np.vstack([bore, arc, face])
    return np.vstack([np.c_[np.full(400, R0), np.linspace(300.8, Y0, 400)], np.c_[np.linspace(R0, 37.8, 400), np.full(400, Y0)]])


def clearance(hub_p, arm_p):
    """Smallest distance from the hub's foot (points with r < 36.6 and Y > 301.3, i.e. the spigot top and the fillet) to the arm
    surface, ignoring the designed 0.1 radial gap along the straight spigot wall below the fillet."""
    foot = hub_p[(hub_p[:, 1] > 301.6) & (hub_p[:, 1] < 301.995) & (hub_p[:, 0] > 35.82) & (hub_p[:, 0] < 36.2)]      # the foot fillet only
    return round(float(cKDTree(arm_p).query(foot)[0].min()), 3) if len(foot) else None


if __name__ == '__main__':
    args = sys.argv[1:]
    arm_stl = args[args.index('--arm') + 1] if '--arm' in args else None
    hubs = [a for a in args if a.lower().endswith('.stl') and a != arm_stl]
    res = {}
    for h in hubs:
        m = trimesh.load(h)
        rows = {}
        for th in (10, 30, 60, 90, 120, 150, 170, 200, 270, 330):
            p = profile(m, th)
            if not len(p):
                continue
            f = hub_foot(p)
            f['clearance'] = {f'{k}{s}': clearance(p, arm_edge(k, s)) for k, s in (('none', 0), ('chamfer', 0.5), ('chamfer', 0.6), ('chamfer', 0.7),
                                                                                 ('round', 0.5), ('round', 0.6), ('round', 0.7), ('round', 0.8))}
            rows[th] = f
        res[h.replace('\\', '/').split('/')[-1] + ' @ ' + h.replace('\\', '/').split('/')[-2]] = rows
    if arm_stl:
        m = trimesh.load(arm_stl)
        arm_rows = {}
        for th in (45, 90, 135):
            p = profile(m, th, rlo=35.6, rhi=37.6, ylo=300.8, yhi=302.2)
            if len(p):
                edge = p[(p[:, 1] > 301.0) & (p[:, 1] < 302.01)]
                face = p[np.abs(p[:, 1] - 302.0) < 0.005]
                arm_rows[th] = dict(end_face_r=[round(float(face[:, 0].min()), 3), round(float(face[:, 0].max()), 3)] if len(face) else None,
                                    bore_top_Y=round(float(p[np.abs(p[:, 0] - 35.9) < 0.005, 1].max()), 3) if (np.abs(p[:, 0] - 35.9) < 0.005).any() else None)
        res['arm ' + arm_stl.replace('\\', '/').split('/')[-1]] = arm_rows
    print(json.dumps(res, indent=1))
