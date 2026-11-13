"""Review B1 load path (2026-11-13): where does the -X lug's Fx go in a STOP_0 result? The plate faces (Z-normal, frictionless) can't
carry X. Candidates: the bolt shank bearing on the lug's Dia 3.4 hole (0.2 radial clearance), the lug's outer face (X offset 34.4)
against our pocket wall (34.6), the spigot / seat. Reads the nodal displacements (FEA_SAVE_DISP) and stresses.
Prints: relative X displacement across each gap (closure), the bolt shank's transverse shear force (section), tangential tractions
on the plate faces, and the -X lug root-band Fx.
    python fx_path.py NPZ DISP_NPZ POST_TXT      (run under capped.py)"""
import re
import sys

import numpy as np
from scipy.spatial import cKDTree

HX, CZ = 170.49, 5.985875
BX, BY = 147.5, 292.0
d = np.load(sys.argv[1])
p, s = d['pos'], d['s']
u = np.load(sys.argv[2])
U = dict(zip(u['u'][:, 0].astype(int), u['u'][:, 1:4]))
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', open(sys.argv[3]).read().split('\n')[0])
body = np.full(len(p), '?', object)
for nm, a, b in runs:
    body[int(a):int(b) + 1] = nm
uu = np.array([U.get(int(i), (np.nan,) * 3) for i in s[:, 0]])
dz = p[:, 2] - CZ
rb = np.hypot(p[:, 0] - BX, p[:, 1] - BY)
xo = HX - p[:, 0]      # -X lug: offset from the axis
lug = (body == 'hub') & (np.abs(dz) < 4.95) & (xo > 18.0) & (xo < 34.5) & (p[:, 1] > 288.0) & (p[:, 1] < 295.5)
print('-X lug mean displacement (mm): ux %+.4f uy %+.4f uz %+.4f' % tuple(np.nanmean(uu[lug], axis=0)))
# 1. lug hole wall (hub, r 1.6-1.8 from the bolt axis) against the bolt shank (steel, r < 1.55), inside the lug (|dz| < 4.9)
hole = (body == 'hub') & (rb > 1.6) & (rb < 1.85) & (np.abs(dz) < 4.9)
shank = (body == 'steel') & (rb < 1.55) & (np.abs(dz) < 4.9)
for side, sx in (('hole wall on +X side of the bolt', 1), ('hole wall on -X side', -1)):
    m = hole & (np.sign(p[:, 0] - BX) == sx) & (np.abs(p[:, 1] - BY) < 0.6)
    ms = shank & (np.sign(p[:, 0] - BX) == sx) & (np.abs(p[:, 1] - BY) < 0.6)
    if m.any() and ms.any():
        gap0 = np.mean(np.abs(p[m, 0] - BX)) - np.mean(np.abs(p[ms, 0] - BX))
        rel = sx * (np.nanmean(uu[m, 0]) - np.nanmean(uu[ms, 0]))
        print(f'{side}: initial radial gap {gap0:.3f}, closure (gap change) {rel:+.4f} mm -> gap now {gap0 + rel:.3f}; '
              f'hub-side normal stress sx {s[m, 1].mean():+.1f} MPa')
# 2. bolt shank transverse shear force at the lug mid-plane (Z = CZ), section of the shank
sec = (body == 'steel') & (rb < 1.55) & (np.abs(dz) < 0.25)
if sec.any():
    txz, tyz = s[sec, 5].mean(), s[sec, 6].mean()
    A = np.pi * 1.5 ** 2
    print(f'bolt shank at the lug mid-plane: mean txz {txz:+.1f}, tyz {tyz:+.1f} MPa -> transverse force about Fx {txz * A:+.0f} N, Fy {tyz * A:+.0f} N')
for zz in (-5.25, 5.25):      # at the two lug faces / plate planes
    sec = (body == 'steel') & (rb < 1.55) & (np.abs(dz - zz) < 0.25)
    if sec.any():
        print(f'   shank at dz {zz:+.2f}: txz {s[sec, 5].mean():+.1f} MPa -> Fx about {s[sec, 5].mean() * np.pi * 1.5 ** 2:+.0f} N')
# 3. lug outer face (hub, X offset 34.2-34.45) against our pocket wall (arm, 34.55-34.8)
lf = (body == 'hub') & (xo > 34.2) & (xo < 34.45) & (np.abs(dz) < 4.9) & (p[:, 1] > 288.5) & (p[:, 1] < 294.5)
pw = (body == 'arm') & (xo > 34.55) & (xo < 34.85) & (np.abs(dz) < 5.4) & (p[:, 1] > 288.5) & (p[:, 1] < 294.5)
if lf.any() and pw.any():
    print(f'lug outer face vs pocket wall: gap 0.20, lug ux {np.nanmean(uu[lf, 0]):+.4f}, wall ux {np.nanmean(uu[pw, 0]):+.4f} -> closure {np.nanmean(uu[pw, 0]) - np.nanmean(uu[lf, 0]):+.4f} '
          f'(negative = the lug moved toward the wall); hub sx there {s[lf, 1].mean():+.2f} MPa')
# 4. tangential tractions on the plate faces (our boss faces at dz = +-5.0, inside the plate outline) near the hole edge and overall
for zz, nm in ((5.0, 'front'), (-5.0, 'back')):
    f = (body == 'arm') & (np.abs(dz - zz) < 0.03) & (xo > 18.96) & (xo < 34.2) & (p[:, 1] > 288.2) & (p[:, 1] < 294.6)
    e = f & (rb > 2.1) & (rb < 2.6)
    if f.any():
        print(f'plate face {nm}: whole face mean txz {s[f, 5].mean():+.2f}, tyz {s[f, 6].mean():+.2f}, sz {s[f, 3].mean():+.2f} MPa; '
              f'at the hole edge (r 2.1-2.6): txz {s[e, 5].mean():+.2f}, tyz {s[e, 6].mean():+.2f}, sz {s[e, 3].mean():+.2f} MPa (n {int(e.sum())})')
        hf = (body == 'hub') & (np.abs(dz - zz) < 0.03) & (xo > 18.96) & (xo < 34.2) & (p[:, 1] > 288.2) & (p[:, 1] < 294.6)
        if hf.any():
            rel = np.nanmean(uu[hf, 0]) - np.nanmean(uu[f, 0])
            print(f'   relative X slip lug face vs plate face: {rel:+.4f} mm (a frictionless face slides freely; ~0 means sticking)')
