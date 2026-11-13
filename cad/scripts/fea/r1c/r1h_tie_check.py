"""R1h tie bridge checks (2026-11-13): the bridge against the front half (the halves close along Z onto the seam at CZ), what the
bridge adds to the back half, and the free section the harness has at the bridge, R1g against R1h.
    python r1h_tie_check.py R1G_EXPORTS R1H_EXPORTS OUT_TXT"""
import sys, numpy as np, trimesh
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
HX, CZ = 170.49, 5.985875
G, Hh, OUT = sys.argv[1:4]
ld = lambda d, n: trimesh.load(f'{d}/upper_arm_organic_{n}_left.STL')
fr, bg, bh = ld(Hh, 'front'), ld(G, 'back'), ld(Hh, 'back')
o = []
o.append(f'back half R1g: volume {bg.volume:.1f} mm3, watertight {bg.is_watertight}; R1h: volume {bh.volume:.1f} mm3, watertight {bh.is_watertight}, bodies {len(bh.split(only_watertight=False))}')
o.append(f'R1h adds {bh.volume - bg.volume:.1f} mm3 ({(bh.volume - bg.volume) * 1.27e-3:.2f} g PETG)')
B = (145.0, 151.0, 254.0, 262.0)      # X, Y window round the bridge
def sec(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0]); g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4: g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return g.buffer(0)
# the bridge itself: R1h minus R1g in the window, per section; its Z extent and its distance to the front half
for y in (255.5, 256.0, 257.0, 258.0, 259.0, 260.0, 260.5):
    add = sec(bh, y).difference(sec(bg, y).buffer(0.01)).intersection(box(B[0], CZ - 6, B[1], CZ + 1))
    f = sec(fr, y)
    if add.is_empty:
        o.append(f'Y {y}: nothing added'); continue
    x0, z0, x1, z1 = add.bounds
    fw = f.intersection(box(x0 - 0.01, CZ - 10, x1 + 0.01, CZ + 10))      # front material over the bridge's X span (the closing sweep)
    zf = fw.bounds[1] if not fw.is_empty else float('nan')
    fb = f.intersection(box(147.4, CZ - 10, 149.9, CZ + 20))      # front material over the bar and its lower round (X 147.4-149.9)
    zb_ = fb.bounds[1] - CZ if not fb.is_empty else float('nan')
    o.append(f'Y {y}: front half over the bar (X 147.4-149.9) lowest at Z - CZ {zb_:+.2f}')
    o.append(f'Y {y}: bridge X {x0:.2f}-{x1:.2f}, Z - CZ {z0 - CZ:+.2f} to {z1 - CZ:+.2f}, {add.area:.2f} mm2; front half over that X span lowest at Z - CZ {zf - CZ:+.2f}; '
             f'nearest front material {add.distance(f):.2f} mm; front overlap {add.intersection(f).area:.3f} mm2')
# the free section inside the arm at the bridge, R1g against R1h (the bundle passes here)
for y in (256.0, 258.0, 260.0):
    def cav(bk):
        both = unary_union([sec(fr, y), sec(bk, y)])
        ext = unary_union([Polygon(p.exterior) for p in getattr(both, 'geoms', [both])])
        return ext.difference(both)
    cg, ch = cav(bg), cav(bh)
    big = lambda c: max(getattr(c, 'geoms', [c]), key=lambda p: p.area)
    pg, ph = big(cg), big(ch)
    def inr(p):
        lo, hi = 0.0, 60.0
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if not p.buffer(-mid).is_empty else (lo, mid)
        return lo
    o.append(f'Y {y}: free section R1g {pg.area:.1f} mm2 (largest inscribed circle Dia {2 * inr(pg):.2f}), R1h {ph.area:.1f} mm2 (Dia {2 * inr(ph):.2f}); '
             f'X span R1g {pg.bounds[0]:.1f}-{pg.bounds[2]:.1f}, R1h {ph.bounds[0]:.1f}-{ph.bounds[2]:.1f}')
open(OUT, 'w').write('\n'.join(o) + '\n'); print('\n'.join(o))
