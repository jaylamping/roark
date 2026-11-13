"""C2 helpers: common constants and section generators."""
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5 - 0] if False else Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools' / 'solidworks'))
OUT = ROOT / 'cad' / '_wip' / 'sw-eval' / 'sonnet-c2'
PIC = Path(__file__).resolve().parent / 'pictures'
OUT.mkdir(parents=True, exist_ok=True)
BOXY_VOL = 219436.04
BOXY_MASS = 261.03

def sec(cx, z, a, b, n=2.0, k=24, y0=0.0):
    """k model points (x, y, z) of a superellipse |x/a|^n + |y/b|^n = 1 centred (cx, y0), same count and start point."""
    pts = []
    for i in range(k):
        t = 2 * math.pi * i / k
        c, s = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2 / n), c)
        y = b * math.copysign(abs(s) ** (2 / n), s)
        pts.append((cx + x, y0 + y, z))
    return pts

def loft_sections(d, secs, name, plane, Sk, loft):
    """secs: list of (z, a, b, n, cx). Draws each as a closed spline on its own Z plane, lofts them."""
    sks = []
    for i, sc in enumerate(secs):
        z, a, b, n, cx = sc[:5]; y0 = sc[5] if len(sc) > 5 else 0.0
        with Sk(d, plane(d, 'Z', z, f'{name}_P{i}'), f'{name}_S{i}') as s:
            s.spline(sec(cx, z, a, b, n, y0=y0))
        sks.append(s.feat)
    return loft(d, sks, name)

