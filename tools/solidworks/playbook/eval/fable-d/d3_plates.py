"""D3: six adapter plates from one table. One script, two parts:

    python d3_plates.py one      # build P1..P6 from the table, export, write the table
    python d3_plates.py two      # open each saved part, EDIT it (dimensions, one sketch, one new chamfer), save as P?_b

Frame: disc on the Z axis, bottom face Z 0, hole angles from +X. mm.
Design intent, so that the parts can be changed later: the bottom face is the datum; the disc is a blind extrude up
from Z 0 (its depth is the thickness); bore and both hole rings are cut through all from the Z 0 plane; the
counterbores are a blind cut down from a plane at the top face.
"""
import json
import math
import sys

import numpy as np

from common import HERE, PICS, WIP, stl_check
from swkit import (BLIND, NUL, THRU_ALL, Sk, bbox, bodies, call, chamfer, close, edges_where, expect, export, extrude, face_info,
                   faces, feature_errors, job, log, new_part, open_doc, plane, save, save_as, single_body, volume)

OUT = WIP / 'd3'
MIN_WALL = 0.6

# ---- the table as given ------------------------------------------------------------------------------------------------
#        OD   T    bore  nA  dA   cA    nB  dB   cB     cbD   cbDepth
TABLE = {
    'P1': (70, 6.0, 30, 6, 3.4, 50, 4, 4.5, 60, 8.0, 3.0),
    'P2': (84, 6.0, 40, 6, 4.5, 62, 6, 4.5, 62, 8.0, 3.0),
    'P3': (96, 8.0, 52, 8, 3.4, 66, 4, 5.5, 84, 10.0, 4.0),
    'P4': (60, 5.0, 28, 4, 3.4, 40, 6, 4.5, 58, 8.0, 4.6),
    'P5': (120, 8.0, 60, 12, 4.5, 80, 6, 6.6, 104, 11.0, 5.0),
    'P6': (76, 6.0, 34, 6, 3.4, 46, 3, 4.5, 64, 8.0, 3.0),
}
KEYS = ('od', 't', 'bore', 'na', 'da', 'ca', 'nb', 'db', 'cb', 'cbd', 'cbdepth')


def spec(row, **over):
    s = dict(zip(KEYS, row), turn_a=0.0, turn_b=0.0, chamfer=0.0)
    s.update(over)
    return s


def centres(n, circle, turn):
    return [(circle / 2 * math.cos(math.radians(turn + 360.0 * k / n)), circle / 2 * math.sin(math.radians(turn + 360.0 * k / n)))
            for k in range(n)]


def walls(s):
    """Every wall of a plate from its numbers: (thinnest, {name: mm}). Negative means two features cut into each other."""
    a, b = centres(s['na'], s['ca'], s['turn_a']), centres(s['nb'], s['cb'], s['turn_b'])
    ra, rb, rc = s['da'] / 2, s['db'] / 2, s['cbd'] / 2
    w = {}
    w['A hole to A hole'] = min(math.dist(p, q) for i, p in enumerate(a) for q in a[i + 1:]) - 2 * ra if s['na'] > 1 else 99.0
    w['B counterbore to B counterbore'] = min(math.dist(p, q) for i, p in enumerate(b) for q in b[i + 1:]) - 2 * rc if s['nb'] > 1 else 99.0
    w['A hole to B counterbore'] = min(math.dist(p, q) for p in a for q in b) - ra - rc
    w['A hole to B hole'] = min(math.dist(p, q) for p in a for q in b) - ra - rb
    w['A hole to bore'] = s['ca'] / 2 - ra - s['bore'] / 2
    w['B hole to bore'] = s['cb'] / 2 - rb - s['bore'] / 2
    w['B counterbore to bore'] = s['cb'] / 2 - rc - s['bore'] / 2
    w['A hole to outside'] = s['od'] / 2 - s['ca'] / 2 - ra
    w['B hole to outside'] = s['od'] / 2 - s['cb'] / 2 - rb
    w['B counterbore to outside, at the top face'] = s['od'] / 2 - s['chamfer'] - s['cb'] / 2 - rc
    w['counterbore floor'] = s['t'] - s['cbdepth']
    name = min(w, key=w.get)
    return round(w[name], 3), name, {k: round(v, 3) for k, v in w.items()}


def hand_volume(s):
    v = math.pi / 4 * (s['od'] ** 2 * s['t'] - s['bore'] ** 2 * s['t'] - s['na'] * s['da'] ** 2 * s['t'] - s['nb'] * s['db'] ** 2 * s['t']
                       - s['nb'] * (s['cbd'] ** 2 - s['db'] ** 2) * s['cbdepth'])
    c = s['chamfer']
    return v - math.pi * c * c * (s['od'] / 2 - c / 3)          # a c x c triangle swept round the top edge (Pappus)


# ---- the table checked BEFORE anything is built ------------------------------------------------------------------------
def decide_one():
    """Part one: each row as given, its walls, and what is built instead where the row cannot be made."""
    plan, problems = {}, []
    for name, row in TABLE.items():
        given = spec(row)
        thin, where, _ = walls(given)
        over, why = {}, []
        if name == 'P1':
            # ring A (r 25) and ring B (r 30) both have a hole at 0 and 180 degrees: the dia 3.4 hole cuts 0.7 mm into the dia 8 counterbore
            over['turn_b'] = 45.0
            why.append('ring B turned 45 degrees: at 0 and 180 degrees an A hole (r 25) cut 0.70 mm into a B counterbore (r 30); turned, the wall is 3.02 mm')
        if name == 'P2':
            over['turn_b'] = 30.0
            why.append('ring B turned 30 degrees: rings A and B are both 6 x dia 4.5 on the same dia 62 circle from 0 degrees, so the twelve holes were six; turned, the wall is 9.80 mm')
        if name == 'P4':
            over['od'] = 70.0
            over['cbdepth'] = 3.0
            why.append('outside dia 60 -> 70: ring B on dia 58 puts its dia 4.5 holes 1.25 mm and its dia 8 counterbores 3.0 mm through the dia 60 edge; '
                       'the bolt circle mates with something, so it is kept and the disc grows to leave 2.0 mm outside the counterbores (as P6 has)')
            why.append('counterbore depth 4.6 -> 3.0: 4.6 in a 5.0 plate leaves a 0.4 mm floor; 3.0 leaves 2.0 mm, and is the depth of the other three dia 8 counterbores')
        built = spec(row, **over)
        t2, w2, allw = walls(built)
        if thin < MIN_WALL:
            problems.append(dict(plate=name, part='one', what=f'{where}: {thin} mm as the table says', built='; '.join(why)))
        if t2 < MIN_WALL:
            raise SystemExit(f'{name}: still {t2} mm at {w2} after the change')
        plan[name] = dict(given=given, built=built, changed=bool(over), why=why, thinnest_as_given=[thin, where], walls=allw, thinnest=[t2, w2])
    return plan, problems


def decide_two(plan):
    """Part two: 1.5 thicker, counterbore floors kept from the bottom, 1 mm chamfer round the top outside edge,
    P3 ring A on dia 70. Checked the same way before anything is edited."""
    out, problems = {}, []
    for name, p in plan.items():
        s = dict(p['built'])
        s['t'] += 1.5
        s['cbdepth'] += 1.5                       # the floor stays where it is from the bottom
        s['chamfer'] = 1.0
        why = []
        if name == 'P3':
            s['ca'] = 70.0
        allw = walls(s)[2]
        if allw['A hole to B counterbore'] < MIN_WALL:
            problems.append(dict(plate=name, part='two', what=f'ring A on dia {s["ca"]:.0f} from 0 degrees: A hole to B counterbore {allw["A hole to B counterbore"]} mm '
                                 f'(an A hole at r {s["ca"] / 2:.0f} beside a dia {s["cbd"]:.0f} counterbore at r {s["cb"] / 2:.0f})',
                                 built=f'ring A also turned {180.0 / s["na"]} degrees, half its pitch'))
            s['turn_a'] = 180.0 / s['na']
            why.append(f'ring A moved to dia {s["ca"]:.0f} as asked AND turned {s["turn_a"]} degrees: left at 0 degrees it stands '
                       f'{allw["A hole to B counterbore"]} mm from the B counterbores; turned, {walls(s)[2]["A hole to B counterbore"]} mm')
        top = allw['B counterbore to outside, at the top face']
        if top < MIN_WALL:
            problems.append(dict(plate=name, part='two', what=f'1 mm chamfer: B counterbore to outside at the top face {top} mm (the counterbores stand '
                                 f'{round(top + 1.0, 3)} mm from the edge, so a 1 mm chamfer meets them in a knife edge)',
                                 built='chamfer 0.4 mm on this plate: 0.6 mm is left at the top face'))
            s['chamfer'] = round(top + 1.0 - MIN_WALL, 3)
            why.append(f'chamfer {s["chamfer"]} mm, not 1.0: the counterbores are {round(top + 1.0, 3)} mm from the outside, a 1 mm chamfer would leave '
                       f'{top} mm at the top face; {s["chamfer"]} leaves {MIN_WALL} mm')
        thin, where, _ = walls(s)
        if thin < MIN_WALL:
            raise SystemExit(f'{name}_b: still {thin} mm at {where}')
        t2, w2, allw = walls(s)
        out[name] = dict(built=s, why=p['why'] + why, changed=bool(p['why'] + why), walls=allw, thinnest=[t2, w2],
                         floor_z=round(p['built']['t'] - p['built']['cbdepth'], 3))
    return out, problems


# ---- measuring a finished plate ----------------------------------------------------------------------------------------
def ang(c):
    a = math.degrees(math.atan2(c['y'], c['x'])) % 360
    return 0.0 if a > 359.995 else round(a, 2)


def measure(d, s):
    """Every hole of the finished solid: centre, diameter, Z range; then the walls from those measured numbers."""
    cyl = []
    for f in faces(d):
        i = face_info(f)
        if i['kind'] == 'cyl':
            b = i['box']
            cyl.append(dict(x=(b[0] + b[3]) / 2, y=(b[1] + b[4]) / 2, r=i['r'], z0=b[2], z1=b[5]))
    centre = [c for c in cyl if math.hypot(c['x'], c['y']) < 0.01]
    off = [c for c in cyl if math.hypot(c['x'], c['y']) >= 0.01]
    od = max(centre, key=lambda c: c['r'])
    bore = min(centre, key=lambda c: c['r'])
    a = [c for c in off if abs(c['r'] - s['da'] / 2) < 0.01 and abs(math.hypot(c['x'], c['y']) - s['ca'] / 2) < 0.01]
    bh = [c for c in off if abs(c['r'] - s['db'] / 2) < 0.01 and abs(math.hypot(c['x'], c['y']) - s['cb'] / 2) < 0.01 and c not in a]
    cb = [c for c in off if abs(c['r'] - s['cbd'] / 2) < 0.01]
    if s['da'] == s['db'] and s['ca'] == s['cb']:          # P2: same size on the same circle; the B holes are the ones under a counterbore
        both = a
        bh = [c for c in both if any(math.hypot(c['x'] - q['x'], c['y'] - q['y']) < 0.01 for q in cb)]
        a = [c for c in both if c not in bh]
    got = dict(od=round(2 * od['r'], 3), bore=round(2 * bore['r'], 3), thick=round(bbox(d)[5] - bbox(d)[2], 3),
               n_a=len(a), n_b=len(bh), n_cb=len(cb),
               a_angles=sorted(ang(c) for c in a), b_angles=sorted(ang(c) for c in cb),
               a_circle=sorted({round(2 * math.hypot(c['x'], c['y']), 3) for c in a}),
               b_circle=sorted({round(2 * math.hypot(c['x'], c['y']), 3) for c in cb}),
               a_dia=sorted({round(2 * c['r'], 3) for c in a}), b_dia=sorted({round(2 * c['r'], 3) for c in bh}),
               cb_dia=sorted({round(2 * c['r'], 3) for c in cb}),
               floor_z=sorted({round(c['z0'], 3) for c in cb}), cb_top_z=sorted({round(c['z1'], 3) for c in cb}),
               a_z=sorted({(round(c['z0'], 3), round(c['z1'], 3)) for c in a}))
    want_a = sorted(round((s['turn_a'] + 360.0 * k / s['na']) % 360, 2) for k in range(s['na']))
    want_b = sorted(round((s['turn_b'] + 360.0 * k / s['nb']) % 360, 2) for k in range(s['nb']))
    ok = (got['od'] == s['od'] and got['bore'] == s['bore'] and abs(got['thick'] - s['t']) < 1e-3 and got['n_a'] == s['na']
          and got['n_b'] == s['nb'] and got['n_cb'] == s['nb'] and got['a_circle'] == [s['ca']] and got['b_circle'] == [s['cb']]
          and got['a_dia'] == [s['da']] and got['b_dia'] == [s['db']] and got['cb_dia'] == [s['cbd']]
          and np.allclose(got['a_angles'], want_a, atol=0.02) and np.allclose(got['b_angles'], want_b, atol=0.02)
          and got['floor_z'] == [round(s['t'] - s['cbdepth'], 3)])
    # walls from the measured holes
    pa, pb = [(c['x'], c['y']) for c in a], [(c['x'], c['y']) for c in cb]
    w = [min(math.dist(p, q) for p in pa for q in pb) - s['da'] / 2 - got['cb_dia'][0] / 2,
         got['od'] / 2 - s['chamfer'] - max(math.hypot(*q) for q in pb) - got['cb_dia'][0] / 2,
         min(math.hypot(*q) for q in pa) - s['da'] / 2 - got['bore'] / 2, got['floor_z'][0],
         got['od'] / 2 - max(math.hypot(*q) for q in pa) - s['da'] / 2, min(math.hypot(*q) for q in pb) - got['cb_dia'][0] / 2 - got['bore'] / 2]
    if len(pa) > 1:
        w.append(min(math.dist(p, q) for i, p in enumerate(pa) for q in pa[i + 1:]) - s['da'])
    if len(pb) > 1:
        w.append(min(math.dist(p, q) for i, p in enumerate(pb) for q in pb[i + 1:]) - got['cb_dia'][0])
    got['min_wall_measured'] = round(min(w), 3)
    got['as_specified'] = bool(ok)
    return got


def row_of(name, d, s, sw, stem):
    hv = hand_volume(s)
    v = volume(d)
    expect(f'{stem} volume against the hand value', v, hv, 0.002)
    expect(f'{stem} rebuild errors', len(feature_errors(d)), 0, 0)
    got = measure(d, s)
    if not got['as_specified']:
        raise SystemExit(f'{stem}: the solid is not what was decided: {got} against {s}')
    bx = bbox(d)
    export(sw, d, OUT / f'{stem}.stl')
    chk = stl_check(OUT / f'{stem}.stl', v, bx)
    thin, where, _ = walls(s)
    if abs(thin - got['min_wall_measured']) > 0.01:
        raise SystemExit(f'{stem}: wall from the numbers {thin} but from the solid {got["min_wall_measured"]}')
    return dict(volume_mm3=round(v, 2), hand_volume_mm3=round(hv, 2), diff_pct=round(100 * (v - hv) / hv, 4), mass_g=round(v * 1.19e-3, 2),
                bodies=len(bodies(d)), stl_watertight=chk['watertight'], stl_shells=chk['shells'], stl_volume_ok=chk['volume_ok'],
                stl_box_ok=chk['box_ok'], min_wall_mm=thin, min_wall_where=where, min_wall_measured_mm=got['min_wall_measured'],
                bbox=[round(x, 3) for x in bx], measured=got)


# ---- part one: build ---------------------------------------------------------------------------------------------------
def build(j, name, s):
    d = new_part(j.sw, OUT / f'{name}.SLDPRT')
    r, t = s['od'] / 2, s['t']
    with Sk(d, plane(d, 'Z', 0.0, ''), 'DISC') as k:
        k.circle((0, 0, 0), r)
    extrude(d, k.feat, 'DISC', t, mode=BLIND, want=(2, +1, 0.0), expect_dv=math.pi * r * r * t)
    with Sk(d, plane(d, 'Z', 0.0, ''), 'BORE') as k:
        k.circle((0, 0, 0), s['bore'] / 2)
    extrude(d, k.feat, 'BORE', t, cut=True, mode=THRU_ALL, expect_dv=math.pi * s['bore'] ** 2 / 4 * t)
    with Sk(d, plane(d, 'Z', 0.0, ''), 'RING_A') as k:
        for x, y in centres(s['na'], s['ca'], s['turn_a']):
            k.circle((x, y, 0), s['da'] / 2)
    extrude(d, k.feat, 'RING_A', t, cut=True, mode=THRU_ALL, expect_dv=s['na'] * math.pi * s['da'] ** 2 / 4 * t)
    with Sk(d, plane(d, 'Z', 0.0, ''), 'RING_B') as k:
        for x, y in centres(s['nb'], s['cb'], s['turn_b']):
            k.circle((x, y, 0), s['db'] / 2)
    extrude(d, k.feat, 'RING_B', t, cut=True, mode=THRU_ALL, expect_dv=s['nb'] * math.pi * s['db'] ** 2 / 4 * t)
    save(d)
    with Sk(d, plane(d, 'Z', t, 'TOP_P'), 'CBORE') as k:
        for x, y in centres(s['nb'], s['cb'], s['turn_b']):
            k.circle((x, y, t), s['cbd'] / 2)
    extrude(d, k.feat, 'CBORE', s['cbdepth'], cut=True, mode=BLIND, want=(2, -1, t),
            expect_dv=s['nb'] * math.pi * (s['cbd'] ** 2 - s['db'] ** 2) / 4 * s['cbdepth'])
    single_body(d)
    save(d)
    return d


# ---- part two: edit --------------------------------------------------------------------------------------------------
def tree(d):
    """[(name, type, id, created)] of the features after the origin: how to tell an edited part from a rebuilt one."""
    out, f = [], d.FirstFeature
    while f is not None:
        if f.Name in ('DISC_SK', 'DISC', 'BORE_SK', 'BORE', 'RING_A_SK', 'RING_A', 'RING_B_SK', 'RING_B', 'TOP_P', 'CBORE_SK', 'CBORE', 'TOP_CHAMFER'):
            out.append([f.Name, f.GetTypeName2, int(_member(f, 'GetID')), str(_member(f, 'DateCreated'))])
        f = f.GetNextFeature
    return out


def _member(o, name, *a):
    """o.name or o.name(*a). swkit.call() cannot be used when the member returns a COM object: a late-bound object is
    itself callable, so call() calls the RESULT and gets "Member not found" (first run of part two, 2026-11-13)."""
    v = getattr(o, name)
    if hasattr(v, '_oleobj_') or not callable(v):       # an object, or a plain value (a second failed run: an int)
        return v
    return v(*a)


def set_dim(d, feat_name, old_mm, new_mm):
    """Change the one driving dimension of a feature that now reads old_mm to new_mm. Returns the dimension's name.

    First by name (D1@<feature>), then by walking the feature's display dimensions; the value it reads now must be
    old_mm, so a wrong dimension cannot be changed by mistake."""
    f = d.FeatureByName(feat_name)
    if f is None:
        raise SystemExit(f'no feature {feat_name}')
    found, seen = [], []
    dim = d.Parameter(f'D1@{feat_name}')
    if dim is not None:
        found.append(dim)
    else:
        dd = _member(f, 'GetFirstDisplayDimension')
        while dd is not None:
            found.append(dd.GetDimension2(0))
            dd = f.GetNextDisplayDimension(dd)
    for dim in found:
        val = dim.SystemValue * 1e3
        seen.append((dim.FullName, round(val, 4)))
        if abs(val - old_mm) < 1e-6:
            try:
                dim.SystemValue = new_mm / 1e3
            except Exception as ex:      # noqa: BLE001 - logged, and the other documented call is tried
                log(f'{feat_name}: SystemValue could not be set ({str(ex)[:80]}); trying SetSystemValue3')
                dim.SetSystemValue3(new_mm / 1e3, 2, NUL)        # 2 = all configurations
            if abs(dim.SystemValue * 1e3 - new_mm) > 1e-6:
                raise SystemExit(f'{feat_name}: dimension {dim.FullName} did not take {new_mm}')
            log(f'{feat_name}: {dim.FullName} {old_mm} -> {new_mm}')
            return f'{dim.FullName}: {old_mm} -> {new_mm}'
    raise SystemExit(f'{feat_name}: no dimension reads {old_mm}; it has {seen}')


def redraw_circles(d, sketch_name, pts, r):
    """Edit an existing sketch in place: delete its circles and draw new ones (model mm, on the sketch plane)."""
    d.ClearSelection2(True)
    sk = d.FeatureByName(sketch_name)
    if sk is None or not sk.Select2(False, 0):
        raise SystemExit(f'no sketch {sketch_name}')
    d.EditSketch()
    act = d.GetActiveSketch2
    T = act.ModelToSketchTransform.ArrayData
    segs = call(act, 'GetSketchSegments') or []
    d.ClearSelection2(True)
    for seg in segs:
        seg.Select4(True, NUL)
    d.EditDelete()
    d.SketchManager.AddToDB = True
    for x, y, z in pts:
        x, y, z = x / 1e3, y / 1e3, z / 1e3
        u, v = x * T[0] + y * T[3] + z * T[6] + T[9], x * T[1] + y * T[4] + z * T[7] + T[10]
        if abs(x * T[2] + y * T[5] + z * T[8] + T[11]) > 1e-9:
            raise SystemExit(f'{sketch_name}: point off the sketch plane')
        if d.SketchManager.CreateCircleByRadius(u, v, 0, r / 1e3) is None:
            raise SystemExit(f'{sketch_name}: circle not drawn')
    d.SketchManager.AddToDB = False
    d.InsertSketch2(True)
    log(f'{sketch_name}: {len(segs)} segments deleted, {len(pts)} circles drawn')
    return len(segs)


def edit(j, name, old, new):
    d = open_doc(j.sw, OUT / f'{name}.SLDPRT')
    before = tree(d)
    v0 = volume(d)
    save_as(d, OUT / f'{name}_b.SLDPRT')           # the open document is now P?_b; P? on disk is untouched
    edits = [set_dim(d, 'DISC', old['t'], new['t']),
             set_dim(d, 'TOP_P', old['t'], new['t']),
             set_dim(d, 'CBORE', old['cbdepth'], new['cbdepth'])]
    if (new['ca'], new['turn_a']) != (old['ca'], old['turn_a']):
        n = redraw_circles(d, 'RING_A_SK', [(x, y, 0.0) for x, y in centres(new['na'], new['ca'], new['turn_a'])], new['da'] / 2)
        edits.append(f'RING_A_SK: {n} circles redrawn on dia {new["ca"]} turned {new["turn_a"]}')
    d.ForceRebuild3(False)
    v1 = volume(d)
    r, t = new['od'] / 2, new['t']
    top = edges_where(d, lambda p: abs(p[2] - t) < 1e-3 and abs(math.hypot(p[0], p[1]) - r) < 1e-3)
    expect(f'{name}_b top outside edge', len(top), 1, 0)
    chamfer(d, top, new['chamfer'], 'TOP_CHAMFER')
    expect(f'{name}_b chamfer volume', v1 - volume(d), math.pi * new['chamfer'] ** 2 * (r - new['chamfer'] / 3), 0.01)
    single_body(d)
    save(d)
    after = tree(d)
    same = [a[:3] for a in after if a[0] != 'TOP_CHAMFER'] == [b[:3] for b in before] and \
           [a[3] for a in after if a[0] != 'TOP_CHAMFER'] == [b[3] for b in before]
    return d, dict(edits=edits, tree_before=before, tree_after=after, same_features_same_ids_same_creation_time=bool(same),
                   volume_before=round(v0, 2))


if __name__ == '__main__':
    part = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    plan, problems1 = decide_one()
    plan2, problems2 = decide_two(plan)
    if part == 'check':
        print(json.dumps(dict(plan=plan, problems=problems1, plan2=plan2, problems2=problems2), indent=1))
        raise SystemExit
    res = {}
    with job() as j:
        for name in TABLE:
            if part == 'one':
                s = plan[name]['built']
                log(f'---- {name}: {s}')
                d = build(j, name, s)
                res[name] = dict(row_of(name, d, s, j.sw, name), changed=plan[name]['changed'], why=plan[name]['why'],
                                 thinnest_as_the_table_says=plan[name]['thinnest_as_given'], built=s)
            else:
                old, new = plan[name]['built'], plan2[name]['built']
                log(f'---- {name}_b: {new}')
                d, how = edit(j, name, old, new)
                row = row_of(name, d, new, j.sw, name + '_b')
                res[name] = dict(row, changed=plan2[name]['changed'], why=plan2[name]['why'],
                                 counterbore_floor_z_mm=row['measured']['floor_z'][0], floor_z_before=plan2[name]['floor_z'], built=new, how=how)
                if abs(res[name]['counterbore_floor_z_mm'] - plan2[name]['floor_z']) > 1e-3:
                    raise SystemExit(f'{name}_b: the counterbore floor moved')
            save(d)
            close(j.sw, d)
            (HERE / f'd3_part_{part}.json').write_text(json.dumps(dict(plates=res, problems=problems1 if part == 'one' else problems2), indent=1))
    print('DONE d3', part, flush=True)
