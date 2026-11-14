"""End-face corner: r1g4 against r1g6 for one case (2026-11-13, coordinator 23:48Z). Post-processing only.
    python endface_compare.py NPZ_A DISP_A POST_A NPZ_B DISP_B POST_B [LABEL_A LABEL_B]      (under capped.py)
(a) the end-face contact (arm end face at its top Y, r 35.8-45) by 30 deg sector: nodes, mean and peak normal pressure (-sy), and
    the sector force (mean pressure x the sector's annulus area); the same on the hub disc face; totals.
(b) displacements: arm against hub at theta 296 on the end face; the lugs against our posts; a plane fit of uy over the arm end
    face and the hub disc face (axial shift and tilt about X and Z).
(c) where the peak is now: every arm node in the end-face corner band (r 35.8-37.6, Y 300.8-302.1) and on the ridge flank
    (r 34.6-35.9, Y 297.5-299.5) as a 0.5 mm sphere centre; the five worst vm and shear centres, with theta.
(d) the r1g4 spot (186.7, 302.0, -26.6): the nodes of each mesh within 0.3 mm, and the 0.5 / 1 / 2 mm averages at that exact
    point in both."""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
SPOT = np.array([186.7, 302.0, -26.6])


def load(npz, disp, post):
    d = np.load(npz)
    p, s = d['pos'], d['s']
    u = np.load(disp)['u']
    U = dict(zip(u[:, 0].astype(int), u[:, 1:4]))
    uu = np.array([U.get(int(i), (np.nan,) * 3) for i in s[:, 0]])
    runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(post).read().split('\n')[0])
    body = np.full(len(p), '?', object)
    for nm, a, b in runs:
        body[int(a):int(b) + 1] = nm
    T = np.zeros((len(p), 3, 3))
    T[:, 0, 0], T[:, 1, 1], T[:, 2, 2] = s[:, 1], s[:, 2], s[:, 3]
    T[:, 0, 1] = T[:, 1, 0] = s[:, 4]
    T[:, 0, 2] = T[:, 2, 0] = s[:, 5]
    T[:, 1, 2] = T[:, 2, 1] = s[:, 6]
    dev = T - np.trace(T, axis1=1, axis2=2)[:, None, None] / 3 * np.eye(3)
    vm = np.sqrt(1.5 * (dev ** 2).sum(axis=(1, 2)))
    sh = np.hypot(s[:, 5], s[:, 6])
    r = np.hypot(p[:, 0] - HX, p[:, 2] - CZ)
    th = np.degrees(np.arctan2(p[:, 2] - CZ, p[:, 0] - HX)) % 360
    return dict(p=p, s=s, u=uu, body=body, vm=vm, sh=sh, r=r, th=th)


def face(M, who, rlo, rhi, ytop=None, tol=0.06):
    m = (M['body'] == who) & (M['r'] > rlo) & (M['r'] < rhi)
    y = M['p'][:, 1]
    if ytop is None:
        ytop = np.round(np.percentile(y[m & (y > 300.0)], 99.5), 2)
    return np.flatnonzero(m & (np.abs(y - ytop) < tol)), ytop


def contact(M, lab):
    print(f'--- (a) {lab}: end-face contact by 30 deg sector')
    out = {}
    for who, rlo, rhi in (('arm', 35.8, 45.0), ('hub', 35.8, 45.0)):
        idx, yt = face(M, who, rlo, rhi, 302.0)
        pr = -M['s'][idx, 2]
        rr = M['r'][idx]
        th = M['th'][idx]
        tot = 0.0
        rows = []
        for a in range(0, 360, 30):
            k = (th >= a) & (th < a + 30)
            if not k.any():
                rows.append(f'{a:3d}-{a + 30:3d}: no nodes'); continue
            pc = np.clip(pr[k], 0, None)
            con = rr[k][pr[k] > 0.05]
            area = (np.radians(30) / 2 * (con.max() ** 2 - con.min() ** 2)) if len(con) > 2 else 0.0
            F = pc.mean() * area
            tot += F
            rows.append(f'{a:3d}-{a + 30:3d}: n {k.sum():4d}  in contact (p > 0.05) {np.mean(pr[k] > 0.05) * 100:3.0f} %  p mean {pc.mean():5.2f}  '
                        f'p max {pc.max():6.2f} MPa at r {rr[k][np.argmax(pc)]:.2f}  contact r {con.min() if len(con) else np.nan:.2f}-{con.max() if len(con) else np.nan:.2f}  F about {F:6.1f} N')
        print(f'  {who} face at Y {yt} (r {rlo}-{rhi}, {len(idx)} nodes): total axial force about {tot:.1f} N')
        for ln in rows:
            print('    ' + ln)
        out[who] = tot
    return out


def disp(M, lab):
    print(f'--- (b) {lab}: displacements (mm)')
    t = cKDTree(M['p'])
    for who in ('arm', 'hub'):
        nb = [i for i in t.query_ball_point(SPOT, 1.0) if M['body'][i] == who]
        print(f'  {who} at the theta 296 spot (1 mm, {len(nb)} nodes): u {np.round(np.nanmean(M["u"][nb], axis=0), 4).tolist()}')
    a = [i for i in t.query_ball_point(SPOT, 1.0) if M['body'][i] == 'arm']
    h = [i for i in t.query_ball_point(SPOT, 1.0) if M['body'][i] == 'hub']
    rel = np.nanmean(M['u'][a], axis=0) - np.nanmean(M['u'][h], axis=0)
    print(f'  arm minus hub there: {np.round(rel, 4).tolist()} (uy > 0 = the arm moves toward the hub disc)')
    for side, xs in (('-X', -1), ('+X', 1)):
        dz = M['p'][:, 2] - CZ
        xo = xs * (M['p'][:, 0] - HX)
        lug = (M['body'] == 'hub') & (np.abs(dz) < 4.95) & (xo > 18) & (xo < 34.5) & (M['p'][:, 1] > 288) & (M['p'][:, 1] < 295.5)
        post = (M['body'] == 'arm') & (np.abs(dz) < 12) & (xo > 18) & (xo < 34.5) & (M['p'][:, 1] > 288) & (M['p'][:, 1] < 295.5)
        ul, up = np.nanmean(M['u'][lug], axis=0), np.nanmean(M['u'][post], axis=0)
        print(f'  {side} lug u {np.round(ul, 4).tolist()}, our {side} posts u {np.round(up, 4).tolist()}, lug minus posts {np.round(ul - up, 4).tolist()}')
    for who, rlo, rhi in (('arm', 35.8, 45.0), ('hub', 35.8, 45.0)):
        idx, _ = face(M, who, rlo, rhi, 302.0)
        A = np.c_[np.ones(len(idx)), M['p'][idx, 0] - HX, M['p'][idx, 2] - CZ]
        uy = M['u'][idx, 1]
        k = np.isfinite(uy)
        c = np.linalg.lstsq(A[k], uy[k], rcond=None)[0]
        print(f'  {who} face plane fit of uy: shift {c[0]:+.4f}, slope in X {c[1] * 1000:+.3f} um/mm, slope in Z {c[2] * 1000:+.3f} um/mm '
              f'(tilt {np.degrees(np.arctan(c[1])) * 1000:+.2f} / {np.degrees(np.arctan(c[2])) * 1000:+.2f} mdeg)')
    ia, _ = face(M, 'arm', 35.8, 45.0, 302.0)
    ih, _ = face(M, 'hub', 35.8, 45.0, 302.0)
    th = np.radians(np.arange(0, 360, 30))
    print('  relative uy, arm face minus hub face, by angle (r 37):', end='')
    for a in th:
        q = np.array([HX + 37 * np.cos(a), 302.0, CZ + 37 * np.sin(a)])
        ta = cKDTree(M['p'][ia]); th_ = cKDTree(M['p'][ih])
        _, ja = ta.query(q, 3); _, jh = th_.query(q, 3)
        print(f' {np.degrees(a):.0f}: {np.nanmean(M["u"][ia[ja], 1]) - np.nanmean(M["u"][ih[jh], 1]):+.4f}', end='')
    print()


def avg(M, c, ids, R):
    t = cKDTree(M['p'][ids])
    nb = ids[t.query_ball_point(c, R)]
    if len(nb) == 0:
        return None
    A = np.zeros((3, 3))
    s = M['s'][nb]
    return len(nb), M['vm'][nb].mean(), M['sh'][nb].mean()


def peaks(M, lab):
    print(f'--- (c) {lab}: worst 0.5 mm centres (average of nodal values, as the region report)')
    arm = np.flatnonzero(M['body'] == 'arm')
    p = M['p']
    for name, m in (('end-face corner band (r 35.8-37.6, Y 300.8-302.1)', (M['r'] > 35.8) & (M['r'] < 37.6) & (p[:, 1] > 300.8) & (p[:, 1] < 302.1)),
                    ('ridge flank (r 34.6-35.9, Y 297.5-299.5)', (M['r'] > 34.6) & (M['r'] < 35.9) & (p[:, 1] > 297.5) & (p[:, 1] < 299.5))):
        cand = np.flatnonzero(m & (M['body'] == 'arm'))
        t = cKDTree(p[arm])
        vals = []
        for i in cand:
            nb = arm[t.query_ball_point(p[i], 0.5)]
            vals.append((M['vm'][nb].mean(), M['sh'][nb].mean(), len(nb), i))
        vals = np.array(vals)
        print(f'  {name}: {len(cand)} centres')
        for col, nm, allow in ((0, 'vm', 45.0), (1, 'shear', 13.0)):
            o = np.argsort(-vals[:, col])[:5]
            for j in o:
                i = int(vals[j, 3])
                print(f'    {nm:5s} {vals[j, col]:6.2f} MPa (SF {allow / vals[j, col]:5.2f}, n {int(vals[j, 2])}) at {np.round(p[i], 2).tolist()} theta {M["th"][i]:.0f} r {M["r"][i]:.2f}')


def same(M, lab):
    print(f'--- (d) {lab}: at the r1g4 spot {SPOT.tolist()}')
    arm = np.flatnonzero(M['body'] == 'arm')
    t = cKDTree(M['p'][arm])
    d, j = t.query(SPOT, 5)
    for dd, jj in zip(d, j):
        if dd <= 0.3:
            i = arm[jj]
            print(f'    node {int(M["s"][i, 0])} at {np.round(M["p"][i], 3).tolist()} ({dd:.3f} away): vm {M["vm"][i]:.1f}, shear {M["sh"][i]:.1f}, '
                  f'sy {M["s"][i, 2]:+.1f} MPa')
    for R in (0.5, 1.0, 2.0):
        nb = arm[t.query_ball_point(SPOT, R)]
        print(f'    R {R}: n {len(nb)}  vm {M["vm"][nb].mean():.2f} (SF {45 / M["vm"][nb].mean():.2f})  shear {M["sh"][nb].mean():.2f} (SF {13 / M["sh"][nb].mean():.2f})  '
              f'sy mean {M["s"][nb, 2].mean():+.2f}')


A = load(*sys.argv[1:4])
B = load(*sys.argv[4:7])
la, lb = (sys.argv[7:9] if len(sys.argv) > 8 else ('A', 'B'))
for M, lab in ((A, la), (B, lb)):
    contact(M, lab)
for M, lab in ((A, la), (B, lb)):
    disp(M, lab)
for M, lab in ((A, la), (B, lb)):
    peaks(M, lab)
for M, lab in ((A, la), (B, lb)):
    same(M, lab)
