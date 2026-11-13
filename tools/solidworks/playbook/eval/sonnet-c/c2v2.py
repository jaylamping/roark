"""C2 v2: a domed elbow boss (the six screw heads sit in Ø7 pockets) that the shaft grows out of; shaft from two silhouettes + fillet."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *
from c2sil import curves, closed_edges

# (z, a half width X, y0, y1)
KEYS = [(-24, 15.0, -4, 11.5), (-30, 17.0, -4.5, 10.0), (-40, 17.5, -5.5, 10.0), (-55, 17.0, -6.5, 10.8), (-80, 15, -8.5, 11.5),
        (-105, 13.5, -9, 11.0), (-132, 12.8, -11, 11.5), (-155, 14.5, -15, 15), (-176, 16.5, -21, 21), (-200, 15, -22, 22),
        (-208, 14, -22, 22)]
DOME = [(15.0, 12.0), (20.0, 12.0), (25.0, 11.2), (29.0, 8.8), (32.0, 5.0)]     # (radius, top y) the +Y face rises to

def build(j, path, keys=KEYS):
    fa, fy0, fy1 = curves(keys)
    zs = [-24.0] + [-v for v in np.arange(30.0, 200.0, 12.0)] + [-200.0, -206.0]
    d = new_part(j.sw, path)
    # 1. the shaft alone, so its corner loop is a closed free edge that can be rounded with a big radius
    R = [(float(fa(-z)), 0.0, z) for z in zs]
    bottom = [(12.0, 0.0, -210.5), (7.5, 0.0, -213.0), (0.0, 0.0, -213.8)]
    pts = [(0.0, 0.0, -24.0)] + R + bottom + [(-x, y, z) for x, y, z in reversed(R + bottom[:-1])]
    with Sk(d, plane(d, 'Y', 0, 'XZ_P'), 'XZ_SIL') as s:
        s.spline(pts)
    extrude(d, s.feat, 'SHAFT', 70.0, mode=MID)
    right = [(0.0, float(fy1(-z)), z) for z in zs] + [(0.0, 20.0, -210.0), (0.0, 12.0, -213.5)]
    left = [(0.0, float(fy0(-z)), z) for z in zs] + [(0.0, -20.0, -210.0), (0.0, -12.0, -213.5)]
    prof = [(0.0, float(fy1(24.0)), -12.0)] + right + [(0.0, 0.0, -216.0)] + list(reversed(left)) + [(0.0, float(fy0(24.0)), -12.0)]
    with Sk(d, plane(d, 'X', 0, 'YZ_P'), 'YZ_SIL') as s:
        s.spline(prof, closed=False)
        box = [prof[0], (0.0, 40.0, -12.0), (0.0, 40.0, -235.0), (0.0, -40.0, -235.0), (0.0, -40.0, -12.0), prof[-1]]
        s.poly(box, closed=False)
    extrude(d, s.feat, 'YZ_CUT', 140.0, cut=True, mode=MID)
    save(d)
    return d

def add_disc(d):
    with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
        s.circle((0, 0, 0), 33.0)
    extrude(d, s.feat, 'DISC', 8.0, mode=MID)
    top = [(0.0, y, r) for r, y in DOME]
    with Sk(d, plane(d, 'X', 0, 'DOME_P'), 'DOME') as s:
        s.centerline((0, -10, 0), (0, 20, 0))
        s.poly([(0, 3.5, 32.0), (0, 3.5, 15.0), (0, 12.0, 15.0)], closed=False)
        s.spline(top, closed=False)
        s.poly([(0, 5.0, 32.0), (0, 3.5, 32.0)], closed=False)
    revolve(d, s.feat, 'DOME')
    save(d)

def long_edges(d, zmid=-60.0):
    """Edges whose middle point is below zmid: the corner chains of the shaft, not the short seams at the dome."""
    out = []
    for b in solid_bodies(d):
        for e in (call(b, 'GetEdges') or []):
            cp = e.GetCurveParams3
            mid = e.GetCurve.Evaluate2((cp.UMinValue + cp.UMaxValue) / 2, 0)
            if mid[2] * 1e3 < zmid:
                out.append(e)
    return out

def pockets(d):
    with Sk(d, plane(d, 'Y', 9.0, 'POCK_P'), 'POCKETS') as s:
        for k in range(6):
            a = math.radians(60 * k)
            s.circle((25 * math.cos(a), 9.0, 25 * math.sin(a)), 3.5)
    extrude(d, s.feat, 'POCKETS', 10.0, cut=True, mode=MID)       # Y 4 .. 14, clear of material

def final(j, out):
    d = build(j, WIP / f'{out}.SLDPRT')
    e = closed_edges(d)
    log('loop edges', len(e))
    log('shaft round', fillet(d, e, (8.0, 7.0, 6.0, 5.0, 4.0), 'SHAFT_R'))
    save(d)
    add_disc(d)
    single_body(d)
    # concave seam where the shaft side meets the disc rim: edges along Y near |x|~17, z~-28
    e = edges_where(d, lambda p: abs(abs(p[0]) - 17.0) < 1.5 and -31.0 < p[2] < -25.0 and -4.2 < p[1] < 4.2)
    log('seam edges', len(e), [list(np.round(np.array(x.GetCurveParams3.StartPoint[:3]) * 1e3, 1)) for x in e])
    if e:
        log('seam round', fillet(d, e, (2.0, 1.5, 1.0, 0.6), 'SEAM_R'))
    save(d)
    # keep the motor's space clear: nothing below the mating plane within R 36 of the elbow axis
    with Sk(d, plane(d, 'Y', -12.0, 'MOTOR_P'), 'MOTOR') as sk:
        sk.circle((0, -12.0, 0), 36.0)
    v0 = volume(d)
    try:
        extrude(d, sk.feat, 'MOTOR_CLEAR', 16.0, cut=True, mode=MID, min_dv=0.0)
    except Failed as ex:
        log('motor clear cut did nothing', ex)
    log('motor clearance cut removed', v0 - volume(d))
    pockets(d)
    features(d, passage_y=2.5)
    return d

if __name__ == '__main__':
    out = sys.argv[1]
    with job() as j:
        d = final(j, out)
        log('volume', volume(d), 'bodies', bodies(d), 'errors', feature_errors(d))
        export(j.sw, d, WIP / f'{out}.stl'); save(d); close(j.sw, d)
