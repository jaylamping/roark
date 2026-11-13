"""D2 post-processing from the saved nodal results: per half, per print axis, outside a distance from the screw axes.

    python d2_post.py [exclusion_mm]     default 3.0 (the bonded head edge is a singularity: see REPORT.md)
"""
import json
import sys
from pathlib import Path

import numpy as np

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d2")
RES = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d")
EX = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
ALLOW = dict(yield_=45.0, layer=22.5, shear=13.0)


def split(p):
    rad = np.hypot(p[:, 0], p[:, 1])
    dist = np.full(len(p), 1e9)
    pin = np.zeros(len(p), bool)
    for sx in (-1, 1):
        for z in (1.0, 6.0):
            d = np.hypot(p[:, 0] - sx * 30, p[:, 2] - z)
            dist = np.minimum(dist, d)
            pin |= (d < 2.05) & (p[:, 1] > -6.1) & (p[:, 1] < 31.6)
    ring = (rad < 25.99) & (rad >= 23.99) & (p[:, 2] > 0.19) & (p[:, 2] < 7.21)
    pad = np.zeros(len(p), bool)
    for a in (45, 135, 225, 315):
        x, y = 25 * np.cos(np.radians(a)), 25 * np.sin(np.radians(a))
        pad |= (np.hypot(p[:, 0] - x, p[:, 1] - y) < 2) & (p[:, 2] > 7.1) & (p[:, 2] < 7.7)
    return pin, ring, pad, dist


def tens(s, n):
    n = np.array(n, float)
    return (n[0] ** 2 * s[:, 1] + n[1] ** 2 * s[:, 2] + n[2] ** 2 * s[:, 3]
            + 2 * (n[0] * n[1] * s[:, 4] + n[0] * n[2] * s[:, 5] + n[1] * n[2] * s[:, 6]))


def shear(s, n):
    n = np.array(n, float)
    t = np.c_[s[:, 1] * n[0] + s[:, 4] * n[1] + s[:, 5] * n[2], s[:, 4] * n[0] + s[:, 2] * n[1] + s[:, 6] * n[2],
              s[:, 5] * n[0] + s[:, 6] * n[1] + s[:, 3] * n[2]]
    return np.linalg.norm(t - np.outer(t @ n, n), axis=1)


out = {}
for case in ('Y', 'X', 'YB'):
    f = OUT / f'D2_{case}.npz'
    if not f.exists():
        continue
    z = np.load(f)
    p, s = z['pos'], z['s']
    pin, ring, pad, dist = split(p)
    hous = ~pin & ~ring & ~pad
    keep = hous & (p[:, 1] > -32 + 7.0) & (dist >= EX)      # not within 2 elements of the fixed face, not at a screw head edge
    for half, hm in (('upper', p[:, 1] > 0), ('lower', p[:, 1] < 0)):
        mk = keep & hm
        vm = s[:, 10]
        i = np.flatnonzero(mk)[np.argmax(vm[mk])]
        row = dict(vm=round(float(vm[i]), 2), at=p[i].round(1).tolist(), sf_yield=round(45 / float(vm[i]), 1))
        for ax, n in (('X', (1, 0, 0)), ('Y', (0, 1, 0)), ('Z', (0, 0, 1))):
            t = tens(s, n)
            j = np.flatnonzero(mk)[np.argmax(t[mk])]
            sh = shear(s, n)
            k = np.flatnonzero(mk)[np.argmax(sh[mk])]
            row[f'layers_along_{ax}'] = dict(tension=round(float(t[j]), 2), tension_at=p[j].round(1).tolist(), sf_tension=round(22.5 / max(float(t[j]), 1e-9), 1),
                                              shear=round(float(sh[k]), 2), shear_at=p[k].round(1).tolist(), sf_shear=round(13 / max(float(sh[k]), 1e-9), 1))
        out.setdefault(case, {})[half] = row
(RES / f'd2_post_ex{EX:g}.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
