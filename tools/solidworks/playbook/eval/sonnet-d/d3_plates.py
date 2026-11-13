"""D3: six adapter plates from one table (part one), then the change by editing the saved parts (part two).

    python d3_plates.py one      # check the table, build P1..P6, export, measure, write d3_part1.json
    python d3_plates.py two      # open each P*.SLDPRT, edit, save as P*_b, measure, write d3_part2.json

Frame: disc on the Z axis, Z 0 to the thickness. Hole angles from +X. Ring A holes through; ring B: through hole plus a
counterbore from the top whose FLOOR is at a fixed Z measured from the bottom (so a thicker plate keeps the floor).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks")
from swkit import *   # noqa

OUT = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\cad\_wip\sw-eval\sonnet-d\d3")
RES = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d")
MIN_WALL = 0.6          # printable minimum (07-done.md); I aim for 1.0 and report anything under it
AIM_WALL = 1.0

# name: (OD, T, bore, (nA, dA, cA), (nB, dB, cB, dcb, depth))
TABLE = {
    'P1': (70, 6, 30, (6, 3.4, 50), (4, 4.5, 60, 8.0, 3.0)),
    'P2': (84, 6, 40, (6, 4.5, 62), (6, 4.5, 62, 8.0, 3.0)),
    'P3': (96, 8, 52, (8, 3.4, 66), (4, 5.5, 84, 10.0, 4.0)),
    'P4': (60, 5, 28, (4, 3.4, 40), (6, 4.5, 58, 8.0, 4.6)),
    'P5': (120, 8, 60, (12, 4.5, 80), (6, 6.6, 104, 11.0, 5.0)),
    'P6': (76, 6, 34, (6, 3.4, 46), (3, 4.5, 64, 8.0, 3.0)),
}


def features(spec, offA=0.0, offB=0.0):
    """Planar circles (kind, cx, cy, r) seen from the top: bore, A holes, B holes, B counterbores, plus the outside R."""
    od, t, bore, (nA, dA, cA), (nB, dB, cB, dcb, dep) = spec
    f = [('bore', 0.0, 0.0, bore / 2)]
    for i in range(nA):
        a = math.radians(offA + 360.0 * i / nA)
        f.append(('A', cA / 2 * math.cos(a), cA / 2 * math.sin(a), dA / 2))
    for i in range(nB):
        a = math.radians(offB + 360.0 * i / nB)
        f.append(('Bh', cB / 2 * math.cos(a), cB / 2 * math.sin(a), dB / 2))
        f.append(('Bcb', cB / 2 * math.cos(a), cB / 2 * math.sin(a), dcb / 2))
    return f


def walls(spec, offA=0.0, offB=0.0, chamfer=0.0):
    """Smallest wall between any two features and to the outside, from the design numbers: (mm, which pair).

    A counterbore and the through hole of the same position are one feature. The chamfer matters only at the top face, where
    it removes material outside R - chamfer: the top-face wall to the outside is R - chamfer - (edge of the furthest circle).
    """
    od = spec[0]
    f = features(spec, offA, offB)
    worst = (1e9, '')
    for i, a in enumerate(f):
        for b in f[i + 1:]:
            if a[0] == 'Bh' and b[0] == 'Bcb' and a[1:3] == b[1:3]:
                continue
            g = math.hypot(a[1] - b[1], a[2] - b[2]) - a[3] - b[3]
            if g < worst[0]:
                worst = (g, f'{a[0]}@({a[1]:.1f},{a[2]:.1f}) to {b[0]}@({b[1]:.1f},{b[2]:.1f})')
    for a in f[1:]:
        g = od / 2 - (math.hypot(a[1], a[2]) + a[3])
        gt = g - (chamfer if a[0] in ('Bcb', 'A', 'Bh') else 0.0) if a[0] == 'Bcb' else g
        for gg, nm in ((g, 'outside'), (gt, 'outside at the chamfered top')):
            if gg < worst[0]:
                worst = (gg, f'{a[0]}@({a[1]:.1f},{a[2]:.1f}) to {nm}')
    return worst


def _pair_gaps(spec, offB, offA=0.0):
    f = features(spec, offA, offB)
    out = []
    for i, a in enumerate(f):
        for b in f[i + 1:]:
            if a[0] == 'Bh' and b[0] == 'Bcb' and a[1:3] == b[1:3]:
                continue
            out.append(math.hypot(a[1] - b[1], a[2] - b[2]) - a[3] - b[3])
    return out


def check(name, spec, chamfer=0.0):
    """Look at the row before anything is built. Returns (built spec, offB, list of problems with what was done)."""
    od, t, bore, A, B = spec
    probs = []
    nB, dB, cB, dcb, dep = B
    # 1. a ring that breaks through the rim, or leaves less than the aim wall
    rim = od / 2 - (cB / 2 + dcb / 2)
    if rim < MIN_WALL:
        newc = 2 * (od / 2 - AIM_WALL * 1.5 - dcb / 2)
        probs.append(dict(what=f'{name} ring B counterbores (Ø{dcb} on Ø{cB}) reach r {cB / 2 + dcb / 2} against the plate radius {od / 2}',
                          number=f'wall {rim:.2f} mm', built=f'ring B on Ø{newc:g} instead of Ø{cB}'))
        cB = newc
        B = (nB, dB, cB, dcb, dep)
    # 2. a counterbore that leaves a floor thinner than 1 mm
    floor = t - dep
    if floor < AIM_WALL:
        newdep = t - 1.2
        probs.append(dict(what=f'{name} counterbore depth {dep} in a {t} mm plate', number=f'floor {floor:.2f} mm',
                          built=f'depth {newdep:.1f} (floor 1.2 mm)'))
        dep = newdep
        B = (nB, dB, cB, dcb, dep)
    spec = (od, t, bore, A, B)
    # 3. ring A and ring B identical
    if A[0] == B[0] and A[1] == B[1] and A[2] == B[2]:
        probs.append(dict(what=f'{name} ring B has the same count, hole and circle as ring A ({A[0]} x Ø{A[1]} on Ø{A[2]})',
                          number='holes coincide: zero wall', built='ring B turned by half the pitch, 30 degrees; probably a copy error in the table'))
    # 4. choose the turn of ring B that gives the biggest wall; keep 0 when 0 already gives at least the aim
    w0 = walls(spec, 0.0, 0.0, chamfer)[0]
    offB = 0.0
    same = A[0] == B[0] and A[1] == B[1] and A[2] == B[2]
    if w0 < AIM_WALL or same:
        # candidate turns: multiples of 15 degrees inside one pitch of ring B. Judge by the gaps between features (the wall to the
        # outside does not depend on the turn), then take the smallest turn among equals.
        def gap(o):
            return min(g for g in (_pair_gaps(spec, o)))
        cand = [(round(gap(o), 3), -o, o) for o in np.arange(0.0, 360.0 / nB + 1e-9, 15.0)]
        best = max(cand)
        offB = float(best[2])
        if not same:
            probs.append(dict(what=f'{name} rings A and B as listed (both start at 0 degrees)',
                              number=f'wall {w0:.2f} mm ({walls(spec, 0, 0, chamfer)[1]})',
                              built=f'ring B turned {offB:g} degrees, smallest wall between features {best[0]:.2f} mm'))
    return spec, offB, probs


def build_plate(j, name, spec, offB):
    od, t, bore, (nA, dA, cA), (nB, dB, cB, dcb, dep) = spec
    d = new_part(j.sw, OUT / f'{name}.SLDPRT')
    R = od / 2
    # disc from the Z 0 plane upwards: blind, so that a later change of thickness keeps the bottom at Z 0
    with Sk(d, plane(d, 'Z', 0.0, 'BASE_P'), 'BASE') as s:
        s.circle((0, 0, 0), R)
    extrude(d, s.feat, 'BASE', t, mode=BLIND, want=(2, +1, 0.0), expect_dv=math.pi * R ** 2 * t)
    with Sk(d, plane(d, 'Z', t / 2, 'BORE_P'), 'BORE') as s:
        s.circle((0, 0, t / 2), bore / 2)
    extrude(d, s.feat, 'BORE', t + 4, cut=True, mode=MID, expect_dv=math.pi * (bore / 2) ** 2 * t)
    with Sk(d, plane(d, 'Z', t / 2, 'RINGA_P'), 'RINGA') as s:
        for _, x, y, r in [f for f in features(spec) if f[0] == 'A']:
            s.circle((x, y, t / 2), r)
    extrude(d, s.feat, 'RINGA', t + 4, cut=True, mode=MID, expect_dv=nA * math.pi * (dA / 2) ** 2 * t)
    with Sk(d, plane(d, 'Z', t / 2, 'RINGB_P'), 'RINGB') as s:
        for _, x, y, r in [f for f in features(spec, 0, offB) if f[0] == 'Bh']:
            s.circle((x, y, t / 2), r)
    extrude(d, s.feat, 'RINGB', t + 4, cut=True, mode=MID, expect_dv=nB * math.pi * (dB / 2) ** 2 * t)
    zf = t - dep         # counterbore floor, measured from the bottom, and the plane the cut starts from
    with Sk(d, plane(d, 'Z', zf, 'CB_P'), 'CB') as s:
        for _, x, y, r in [f for f in features(spec, 0, offB) if f[0] == 'Bcb']:
            s.circle((x, y, zf), r)
    # cut upward from the floor, through the top: BLIND with the side chosen by want
    extrude(d, s.feat, 'CB', 100.0, cut=True, mode=BLIND, want=(2, +1, zf),
            expect_dv=nB * (math.pi * (dcb / 2) ** 2 - math.pi * (dB / 2) ** 2) * dep)
    save(d)
    return d


def hand_volume(spec, offB, dt=0.0, chamfer=0.0):
    od, t, bore, (nA, dA, cA), (nB, dB, cB, dcb, dep) = spec
    t2 = t + dt
    v = math.pi / 4 * (od ** 2 - bore ** 2) * t2 - nA * math.pi / 4 * dA ** 2 * t2 - nB * math.pi / 4 * dB ** 2 * t2
    v -= nB * math.pi / 4 * (dcb ** 2 - dB ** 2) * (dep + dt)       # counterbore: floor stays at t - dep from the bottom
    if chamfer:
        v -= 0.5 * chamfer ** 2 * 2 * math.pi * (od / 2 - chamfer / 3)
    return v


def measure(d, spec, offB, dt=0.0, chamfer=0.0):
    """Measure holes, bore, counterbores on the finished solid; recompute the smallest wall from the MEASURED numbers."""
    od, t, bore, (nA, dA, cA), (nB, dB, cB, dcb, dep) = spec
    t2 = t + dt
    out = {}
    cyl = [(face_info(f)) for f in faces(d)]
    cyl = [i for i in cyl if i['kind'] == 'cyl']
    circles = []
    for i in cyl:
        cx, cy = (i['box'][0] + i['box'][3]) / 2, (i['box'][1] + i['box'][4]) / 2
        circles.append((round(i['r'], 3), round(cx, 3), round(cy, 3), round(i['box'][2], 3), round(i['box'][5], 3)))
    out['cyl_faces'] = len(cyl)
    # full cylinders may be one face with a seam; centres come from the box of the face (full circle) so they are right
    meas = []
    for r, cx, cy, z0, z1 in circles:
        meas.append(('outside' if abs(r - od / 2) < 1e-3 else 'cyl', cx, cy, r, z0, z1))
    out['circles'] = meas
    # distances from the measured circles
    holes = [m for m in meas if m[0] == 'cyl' and (m[1] ** 2 + m[2] ** 2) > 1e-6]
    bore_ok = [m for m in meas if m[0] == 'cyl' and (m[1] ** 2 + m[2] ** 2) < 1e-6]
    wmin = 1e9
    where = ''
    for i, a in enumerate(holes):
        for b in holes[i + 1:]:
            if a[1:3] == b[1:3]:
                continue
            g = math.hypot(a[1] - b[1], a[2] - b[2]) - a[3] - b[3]
            if g < wmin:
                wmin, where = g, f'{a[1:4]} to {b[1:4]}'
    for a in holes:
        g = od / 2 - (math.hypot(a[1], a[2]) + a[3])
        if g < wmin:
            wmin, where = g, f'{a[1:4]} to outside'
        for bo in bore_ok:
            g = math.hypot(a[1], a[2]) - a[3] - bo[3]
            if g < wmin:
                wmin, where = g, f'{a[1:4]} to bore'
    out['min_wall_mm'] = round(wmin, 3)
    out['min_wall_where'] = where
    out['bore_r_measured'] = [m[3] for m in bore_ok]
    return out


def table_row(name, d, spec, offB, dt, chamfer, stl_path, changed, why):
    import trimesh
    v = volume(d)
    hv = hand_volume(spec, offB, dt, chamfer)
    mesh = trimesh.load(stl_path)
    m = measure(d, spec, offB, dt, chamfer)
    row = dict(volume_mm3=round(v, 2), hand_volume_mm3=round(hv, 2), vol_error_pct=round(100 * (v - hv) / hv, 3),
               mass_g=round(v * 1.19e-3, 2), bodies=len(bodies(d)), stl_watertight=bool(mesh.is_watertight),
               stl_volume_mm3=round(float(mesh.volume), 2), min_wall_mm=m['min_wall_mm'], min_wall_where=m['min_wall_where'],
               changed=changed, why=why, box=[round(x, 3) for x in bbox(d)], rebuild_errors=feature_errors(d))
    return row, m


def part_one():
    res = {}
    with job() as j:
        for name, spec in TABLE.items():
            built, offB, probs = check(name, spec)
            log(name, 'problems:', probs, 'offB', offB)
            t0 = time_ns()
            d = build_plate(j, name, built, offB)
            single_body(d)
            od, t = built[0], built[1]
            b = bbox(d)
            expect(f'{name} radius', b[3], od / 2, 0.01)
            expect(f'{name} top', b[5], t, 0.01)
            expect(f'{name} bottom', b[2], 0.0, 0.01)
            save(d)
            export(j.sw, d, OUT / f'{name}.stl')
            row, m = table_row(name, d, built, offB, 0.0, 0.0, OUT / f'{name}.stl', bool(probs), '; '.join(p['built'] for p in probs))
            row['problems'] = probs
            row['turn_ring_B_deg'] = offB
            row['spec_built'] = [built[0], built[1], built[2], list(built[3]), list(built[4])]
            row['measured'] = m
            row['features_to_check'] = len(m['circles'])
            res[name] = row
            log(name, json.dumps({k: row[k] for k in ('volume_mm3', 'hand_volume_mm3', 'vol_error_pct', 'min_wall_mm', 'stl_watertight', 'bodies')}))
            close(j.sw, d)
    (RES / 'd3_part1.json').write_text(json.dumps(res, indent=1, default=float))
    print('PART ONE DONE')


def time_ns():
    import time
    return time.time()


# ---- part two: edit the saved parts ------------------------------------------------------------------------------

def edit_sketch_circles(d, sketch_feature, circles, t_mid):
    """Replace the circles of an existing sketch by the given (x, y, r) in model mm on the plane Z = t_mid. Edits in place."""
    d.ClearSelection2(True)
    f = d.FeatureByName(sketch_feature)
    f.Select2(False, 0)
    d.EditSketch()
    sk = d.GetActiveSketch2
    for seg in call(sk, 'GetSketchSegments'):
        seg.Select4(True, NUL)
    d.EditDelete()
    sk = d.GetActiveSketch2
    T = sk.ModelToSketchTransform.ArrayData
    d.SketchManager.AddToDB = True
    for x, y, r in circles:
        X, Y, Z = x * m, y * m, t_mid * m
        w = X * T[2] + Y * T[5] + Z * T[8] + T[11]
        if abs(w) > 1e-6:
            raise Failed(f'sketch plane is {w / m:.3f} mm away from Z={t_mid}')
        u = X * T[0] + Y * T[3] + Z * T[6] + T[9]
        v = X * T[1] + Y * T[4] + Z * T[7] + T[10]
        if d.SketchManager.CreateCircleByRadius(u, v, 0, r * m) is None:
            raise Failed('circle not drawn in the edited sketch')
    d.SketchManager.AddToDB = False
    d.InsertSketch2(True)
    d.ForceRebuild3(False)


def part_two():
    p1 = json.loads((RES / 'd3_part1.json').read_text())
    res = {}
    with job() as j:
        for name in TABLE:
            row1 = p1[name]
            sp = row1['spec_built']
            spec = (sp[0], sp[1], sp[2], tuple(sp[3]), tuple(sp[4]))
            offB = row1['turn_ring_B_deg']
            od, t, bore, A, B = spec
            probs2 = []
            dt, ch, offA = 1.5, 1.0, 0.0
            spec_new = spec
            if name == 'P3':
                spec_new = (od, t, bore, (A[0], A[1], 70.0), B)
            # the change can create new problems: check the new numbers before touching the part
            rim = od / 2 - (B[2] / 2 + B[3] / 2)
            if rim - ch < MIN_WALL:
                ch = round(rim - MIN_WALL, 2)
                probs2.append(dict(what=f'{name}: a 1 mm chamfer meets the counterbores (they come to {rim:.2f} mm from the outside edge)',
                                   number=f'top wall {rim - 1.0:.2f} mm', built=f'chamfer {ch} mm instead of 1.0 (top wall 0.6 mm)'))
            if name == 'P3':
                w_same = walls(spec_new, 0.0, offB, ch)
                if w_same[0] < AIM_WALL:
                    best = max(((round(min(_pair_gaps(spec_new, offB, o)), 3), -o, o) for o in np.arange(0.0, 360.0 / A[0] + 1e-9, 2.5)))
                    best = (best[0], best[2])
                    offA = float(best[1])
                    probs2.append(dict(what='P3 ring A on the dia 70 circle with both rings starting at 0 degrees',
                                       number=f'wall {w_same[0]:.2f} mm ({w_same[1]})', built=f'ring A turned {offA:g} degrees, wall {best[0]:.2f} mm'))
            log(name, 'part two problems', probs2)
            d = open_doc(j.sw, OUT / f'{name}.SLDPRT')
            v_before = volume(d)
            # 1. thickness: change the depth dimension of the BASE extrude of the saved part
            par = d.Parameter('D1@BASE')
            if par is None:
                raise Failed(f'{name}: no dimension D1@BASE')
            par.SystemValue = (t + dt) * m
            d.ForceRebuild3(False)
            b = bbox(d)
            expect(f'{name} new top', b[5], t + dt, 0.01)
            expect(f'{name} bottom unchanged', b[2], 0.0, 0.01)
            # 2. P3: the circles of the RINGA sketch move from dia 66 to dia 70 (edit the sketch in place)
            if name == 'P3':
                circ = [(x, y, r) for k, x, y, r in features(spec_new, offA, offB) if k == 'A']
                edit_sketch_circles(d, 'RINGA_SK', circ, t / 2)
            # 3. chamfer the top outside edge
            R, tt = od / 2, t + dt
            edges = edges_where(d, lambda p: abs(p[2] - tt) < 0.01 and abs(math.hypot(p[0], p[1]) - R) < 0.02)
            expect(f'{name} top outside edges', len(edges), 1, 0)
            v1 = volume(d)
            chamfer(d, edges, ch, 'TOP_CHAMFER')
            expect(f'{name} chamfer removed mm3', v1 - volume(d), 0.5 * ch ** 2 * 2 * math.pi * (R - ch / 3), 0.01)
            single_body(d)
            expect(f'{name} rebuild errors', len(feature_errors(d)), 0, 0)
            save_as(d, OUT / f'{name}_b.SLDPRT')
            export(j.sw, d, OUT / f'{name}_b.stl')
            ch_changed = bool(probs2)
            row, mm = table_row(name, d, spec_new, offB, dt, ch, OUT / f'{name}_b.stl', ch_changed, '; '.join(p['built'] for p in probs2))
            # hand value uses ring A turned by offA (same volume); measured circles in the edited part
            row['problems'] = probs2
            row['chamfer_mm'] = ch
            row['turn_ring_A_deg'] = offA
            row['thickness_mm'] = t + dt
            row['counterbore_floor_z_mm'] = round(t - B[4], 3)
            fl = sorted({c[4] for c in mm['circles'] if c[3] > 0 and abs(c[3] - B[3] / 2) < 1e-3})
            row['counterbore_floor_z_measured'] = fl
            row['volume_before_edit_mm3'] = round(v_before, 2)
            row['measured'] = mm
            res[name] = row
            log(name, json.dumps({k: row[k] for k in ('volume_mm3', 'hand_volume_mm3', 'vol_error_pct', 'min_wall_mm', 'stl_watertight')}))
            close(j.sw, d)
    (RES / 'd3_part2.json').write_text(json.dumps(res, indent=1, default=float))
    print('PART TWO DONE')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    {'one': part_one, 'two': part_two}[sys.argv[1]]()
