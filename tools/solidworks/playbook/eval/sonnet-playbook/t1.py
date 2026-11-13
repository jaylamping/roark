import json, math, sys
from pathlib import Path
WT = r"J:\code\roark-wt\sw-eval-sonnet"
sys.path.insert(0, WT + r"\tools\solidworks")
from swkit import *
OUT = Path(WT) / 'cad' / '_wip' / 'sw-eval' / 'sonnet-playbook'
R = Path(__file__).parent

def build(d, sharp=False):
    with Sk(d, plane(d, 'Z', 3.0, 'BASE_P'), 'BASE') as s:
        s.rect((0, 0, 3.0), (80, 50, 3.0))
    extrude(d, s.feat, 'BASE', 6.0, mode=MID, expect_dv=80 * 50 * 6)
    with Sk(d, plane(d, 'Z', 26.0, 'UPR_P'), 'UPRIGHT') as s:
        s.rect((0, 0, 26.0), (6, 50, 26.0))
    extrude(d, s.feat, 'UPRIGHT', 40.0, mode=MID, expect_dv=6 * 50 * 40)
    expect('bodies after upright', len(bodies(d)), 1, 0)
    fil = 0.0
    if not sharp:
        e = edges_where(d, lambda p: abs(p[0] - 6) < 0.01 and abs(p[2] - 6) < 0.01)
        expect('inside corner edges', len(e), 1, 0)
        if fillet(d, e, (4.0,), 'INSIDE_R4') != 4.0:
            raise Failed('inside fillet failed')
        fil = (1 - math.pi / 4) * 16 * 50
        expect('fillet volume', volume(d), 36000 + fil, 0.001)
    # base holes
    with Sk(d, plane(d, 'Z', 3.0, 'BH_P'), 'BASEHOLES') as s:
        for x, y in ((25, 10), (25, 40), (65, 10), (65, 40)):
            s.circle((x, y, 3.0), 2.75)
    extrude(d, s.feat, 'BASEHOLES', 20.0, cut=True, mode=MID, expect_dv=4 * math.pi * 2.75 ** 2 * 6)
    # bore + bolt holes in upright (axis along X)
    with Sk(d, plane(d, 'X', 3.0, 'UH_P'), 'BORE') as s:
        s.circle((3.0, 25, 28), 11.0)
        for a in (45, 135, 225, 315):
            s.circle((3.0, 25 + 15.5 * math.cos(math.radians(a)), 28 + 15.5 * math.sin(math.radians(a))), 1.7)
    extrude(d, s.feat, 'BORE', 20.0, cut=True, mode=MID, expect_dv=math.pi * 11 ** 2 * 6 + 4 * math.pi * 1.7 ** 2 * 6)
    # corner rounds
    e = edges_where(d, lambda p: abs(p[0] - 80) < 0.01 and (abs(p[1]) < 0.01 or abs(p[1] - 50) < 0.01))
    # vertical corner edges: along Z, so z spans 0..6 (exclude the top/bottom edges along Y? those have x=80 and varying y)
    e = [x for x in e]
    v = edges_where(d, lambda p: abs(p[0] - 80) < 0.01 and (abs(p[1]) < 0.01 or abs(p[1] - 50) < 0.01))
    expect('base corner edges', len(v), 2, 0)
    if fillet(d, v, (5.0,), 'BASE_CORNERS_R5') != 5.0:
        raise Failed('base corners failed')
    t = edges_where(d, lambda p: abs(p[2] - 46) < 0.01 and (abs(p[1]) < 0.01 or abs(p[1] - 50) < 0.01))
    expect('upright top corner edges', len(t), 2, 0)
    if fillet(d, t, (5.0,), 'UPR_TOP_R5') != 5.0:
        raise Failed('upright top failed')
    return fil

def hand(sharp=False):
    v = 36000 + (0 if sharp else (1 - math.pi / 4) * 16 * 50)
    v -= 4 * math.pi * 2.75 ** 2 * 6
    v -= math.pi * 121 * 6 + 4 * math.pi * 1.7 ** 2 * 6
    v -= 4 * (1 - math.pi / 4) * 25 * 6      # 2 base corners (h 6) + 2 top corners (length 6)
    return v

if __name__ == '__main__':  # noqa
    res = {}
    with job() as j:
        d = new_part(j.sw, OUT / 'bracket.SLDPRT')
        build(d)
        expect('rebuild errors', len(feature_errors(d)), 0, 0)
        single_body(d)
        save(d)
        hv = hand()
        vol = volume(d)
        expect('volume vs hand', vol, hv, 0.005)
        b = bbox(d)
        for k, w in enumerate((0, 0, 0, 80, 50, 46)):
            expect(f'box[{k}]', b[k], w, 0.01)
        export(j.sw, d, OUT / 'bracket.step')
        export(j.sw, d, OUT / 'bracket.stl')
        res = dict(volume_mm3=vol, hand_volume_mm3=hv, mass_g=vol * 1.19e-3, bbox_mm=[round(x, 3) for x in b], bodies=len(bodies(d)))
        close(j.sw, d)
    import trimesh
    m = trimesh.load(OUT / 'bracket.stl')
    res['stl_watertight'] = bool(m.is_watertight)
    res['stl_volume_mm3'] = float(m.volume)
    res['stl_bounds'] = m.bounds.round(3).tolist()
    res['stl_shells'] = len(m.split())
    print('STEP units:', 'SI_UNIT(.MILLI.,.METRE.)' in (OUT / 'bracket.step').read_text(errors='ignore'))
    print(res)
    (R / 't1_result.json').write_text(json.dumps(res, indent=1))
