"""B2 follow-up: the two sharp edges where the arm's side faces meet the plate (X 5, Y 15 and Y 25, Z 37 to 55).

The specification rounds the arm's top and bottom but not its sides. Printed on its side (layers along Y) the tension
across layers and the shear between them peak on these edges and moved with the mesh in b2_study. Here the edges get
their own mesh control at three sizes: a value that climbs while its 1 mm average holds is a corner, not a section.
"""
import json

import numpy as np
from scipy.spatial import cKDTree

from common import WIP, put
from swkit import *
from bracket_fea import ALLOW, checks, mask, measures, solve

N = np.array((0.0, 1.0, 0.0))


def layer(r):
    S = r.s
    sn = S[:, 2]
    t = np.c_[S[:, 4], S[:, 2], S[:, 6]]
    tau = np.linalg.norm(t - np.outer(t @ N, N), axis=1)
    return sn, tau


def near_edges(r, keep):
    """Peak and local averages of the two layer measures within 2.5 mm of the sharp edges."""
    p = r.pos
    dist = np.minimum(np.hypot(p[:, 0] - 5, p[:, 1] - 15), np.hypot(p[:, 0] - 5, p[:, 1] - 25))
    reg = (dist < 2.5) & (p[:, 2] > 36.9) & (p[:, 2] < 55.1) & keep
    tree = cKDTree(p)
    out = {}
    for name, v in zip(('tension', 'shear'), layer(r)):
        i = np.flatnonzero(reg)[np.argmax(v[reg])]
        row = dict(peak=round(float(v[i]), 2), at=p[i].round(2).tolist(), factor=round(ALLOW[name] / float(v[i]), 2))
        for rad in (0.5, 1.0, 2.0):
            idx = tree.query_ball_point(p[i], rad)
            row[f'avg_{rad}'] = (round(float(v[idx].mean()), 2), len(idx))
        out[name] = row
    return out


P = WIP / 'wall_bracket.SLDPRT'
rows = []
with job() as j:
    j.simulation()
    d = open_doc(j.sw, P)
    for support in ('wall', 'holes'):
        for es in (0.4, 0.2, 0.1):
            def c(d, es=es):
                ed = edges_where(d, lambda p: abs(p[0] - 5) < 0.01 and min(abs(p[1] - 15), abs(p[1] - 25)) < 0.01 and 36.9 < p[2] < 55.1)
                expect('sharp side edges', len(ed), 2, 0)
                fl = pick(d, kind='cyl', r=3.0)
                expect('fillet faces', len(fl), 2, 0)
                return [(fl, 0.6), (ed, es)]
            tag = f'B2E_{support}_{str(es).replace(".", "p")}'
            r = solve(j, d, tag, support, 2.0, c, dict(nodes='40,000 to 150,000', disp='1.51 (wall) / 1.88 (holes), as b2_study',
                                                       peak='vm 18.5 to 19.6 in the upper fillet as before; layer measures on the side edges'))
            ck = checks(r, tag=tag)
            keep = mask(r, 1.0)        # the edges start 2.75 mm from the upper hole wall and 5 mm from the wall face
            row = dict(tag=tag, support=support, edge_el=es, nodes=r.nodes, checks=ck, vm=measures(r)['vm'], edges=near_edges(r, keep))
            log(tag, json.dumps(row['edges']), 'vm', row['vm'])
            rows.append(row)
            put('b2_edges', rows)
    close(j.sw, d)
print('B2 EDGES DONE')
