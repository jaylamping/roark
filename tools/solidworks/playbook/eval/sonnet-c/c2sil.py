"""C2 final builder: two silhouettes (XZ extruded, then YZ cut) + fillets. Replaces the loft (which pinched, see REPORT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *

# (z, a = half width in X, y0, y1)   all in mm, PCHIP-smoothed between keys
KEYS = [(-17, 7.5, -4, 9), (-25, 8, -4, 9.5), (-37, 14, -4, 10), (-52, 17, -5.5, 10.5), (-75, 16, -8, 10.5),
        (-105, 13.5, -8.5, 9.5), (-132, 12.8, -10.5, 11), (-155, 14.5, -14.5, 14.5), (-176, 16.5, -21, 21), (-200, 15, -22, 22), (-208, 14, -22, 22)]

def curves(keys=KEYS):
    u = -np.array([k[0] for k in keys], float)
    return [PchipInterpolator(u, [k[i] for k in keys]) for i in range(1, 4)]

def build(j, path, keys=KEYS, rfil=(7.0, 6.0, 5.0, 4.0)):
    fa, fy0, fy1 = curves(keys)
    zs = [-17.0, -25.0] + [-v for v in np.arange(37.0, 200.0, 12.0)] + [-200.0, -206.0]
    d = new_part(j.sw, path)
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), 33.0)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID, expect_dv=math.pi * 33**2 * 8)
    # XZ silhouette: closed spline, rounded bottom
    R = [(float(fa(-z)), 0.0, z) for z in zs]
    bottom = [(12.0, 0.0, -210.5), (7.5, 0.0, -213.0), (0.0, 0.0, -213.8)]
    pts = [(0.0, 0.0, -17.0)] + R + bottom + [(-x, y, z) for x, y, z in reversed(R + bottom[:-1])]
    with Sk(d, plane(d, 'Y', 0, 'XZ_P'), 'XZ_SIL') as s:
        s.spline(pts)
    extrude(d, s.feat, 'SHAFT', 70.0, mode=MID)
    # YZ silhouette: the region OUTSIDE the profile, cut through all X; the profile is open at the top (z > -17)
    right = [(0.0, float(fy1(-z)), z) for z in zs] + [(0.0, 20.0, -210.0), (0.0, 12.0, -213.5)]
    left = [(0.0, float(fy0(-z)), z) for z in zs] + [(0.0, -20.0, -210.0), (0.0, -12.0, -213.5)]
    prof = [(0.0, float(fy1(17.0)), -12.0)] + right + [(0.0, 0.0, -216.0)] + list(reversed(left)) + [(0.0, float(fy0(17.0)), -12.0)]
    # spline through prof (open); closed by lines around a box
    with Sk(d, plane(d, 'X', 0, 'YZ_P'), 'YZ_SIL') as s:
        s.spline(prof, closed=False)
        top_r, top_l = prof[0], prof[-1]
        box = [top_r, (0.0, 40.0, -12.0), (0.0, 40.0, -235.0), (0.0, -40.0, -235.0), (0.0, -40.0, -12.0), top_l]
        s.poly(box, closed=False)
    extrude(d, s.feat, 'YZ_CUT', 140.0, cut=True, mode=MID)
    save(d)
    return d

def closed_edges(d):
    """The one closed loop where the two silhouette surfaces meet: its start and end points are the same."""
    out = []
    for b in solid_bodies(d):
        for e in (call(b, 'GetEdges') or []):
            cp = e.GetCurveParams3
            a, c = np.array(cp.StartPoint[:3]) * 1e3, np.array(cp.EndPoint[:3]) * 1e3
            if np.linalg.norm(a - c) < 1e-3 and a[2] < -15:
                out.append(e)
    return out

def round_shaft(d, radii=(8.0, 7.0, 6.0, 5.0, 4.0)):
    e = closed_edges(d)
    log('shaft loop edges', len(e))
    r = fillet(d, e, radii, 'SHAFT_R')
    log('shaft round', r)
    return r

def final(j, out, **kw):
    d = build(j, WIP / f'{out}.SLDPRT')
    round_shaft(d)
    save(d)
    features(d)
    return d

if __name__ == '__main__':
    out = sys.argv[1]
    with job() as j:
        d = final(j, out)
        log('volume', volume(d), 'bodies', bodies(d), 'errors', feature_errors(d))
        export(j.sw, d, WIP / f'{out}.stl'); save(d); close(j.sw, d)
