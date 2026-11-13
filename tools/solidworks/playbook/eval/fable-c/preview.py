"""A preview of the bone form straight from the section table, without SolidWorks: skin of the sections plus the disc.

Not a solid and not watertight where the disc and the skin cross; it exists so the form can be looked at while
SolidWorks launches are held up by another session's solve. python preview.py out.stl
"""
import math
import struct
import sys

import numpy as np

import c2_build as c


def write_stl(path, tris):
    tris = np.asarray(tris, np.float32)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    with open(path, 'wb') as f:
        f.write(b'preview'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for t, m in zip(tris, n):
            f.write(struct.pack('<12fH', *m, *t.ravel(), 0))


def skin(rows, yc=lambda z: 0.0, fine=6):
    zs = np.array([r[0] for r in rows], float)
    cols = np.array([r[1:] for r in rows], float)
    zz = np.linspace(zs[0], zs[-1], fine * len(rows))
    rings = []
    for z in zz:
        a, bp, bm, n = (np.interp(-z, -zs, cols[:, k]) for k in range(4))
        rings.append(np.array(c.section(z, a, bp, bm, n, yc(z), npts=64)))
    tris = []
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(64):
            k2 = (k + 1) % 64
            tris += [[r0[k], r1[k], r1[k2]], [r0[k], r1[k2], r0[k2]]]
    for r, flip in ((rings[0], False), (rings[-1], True)):
        ctr = r.mean(axis=0)
        for k in range(64):
            k2 = (k + 1) % 64
            tris.append([ctr, r[k2], r[k]] if flip else [ctr, r[k], r[k2]])
    return tris, rings[-1]


def ring_solid(r0, r1, y0, y1, zc=0.0, seg=72):
    tris = []
    for k in range(seg):
        t0, t1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        p = lambda r, t, y: (r * math.cos(t), y, zc + r * math.sin(t))      # noqa: E731
        tris += [[p(r1, t0, y0), p(r1, t1, y0), p(r1, t1, y1)], [p(r1, t0, y0), p(r1, t1, y1), p(r1, t0, y1)],
                 [p(r0, t0, y0), p(r0, t1, y1), p(r0, t1, y0)], [p(r0, t0, y0), p(r0, t0, y1), p(r0, t1, y1)],
                 [p(r0, t0, y1), p(r1, t0, y1), p(r1, t1, y1)], [p(r0, t0, y1), p(r1, t1, y1), p(r0, t1, y1)],
                 [p(r0, t0, y0), p(r1, t1, y0), p(r1, t0, y0)], [p(r0, t0, y0), p(r0, t1, y0), p(r1, t1, y0)]]
    return tris


if __name__ == '__main__':
    tris, last = skin(c.BONE)
    # the round end: the last section turned about the pin axis
    half = last[last[:, 0] >= -1e-9]
    half = half[np.argsort(half[:, 1])]
    for k in range(24):
        t0, t1 = -math.pi * k / 24, -math.pi * (k + 1) / 24
        for p, q in zip(half[:-1], half[1:]):
            def rot(v, t):
                return (v[0] * math.cos(t), v[1], c.Z_PIN + v[0] * math.sin(t))
            tris += [[rot(p, t0), rot(q, t0), rot(q, t1)], [rot(p, t0), rot(q, t1), rot(p, t1)]]
    tris += ring_solid(c.R_BORE, c.R_DISC, -4, 4)
    write_stl(sys.argv[1], tris)
