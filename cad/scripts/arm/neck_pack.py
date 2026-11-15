"""Neck packing check for the arm's wiring items (2026-11-15, option C fuse question).
Cavity per Y plane (1 mm): inside our halves' outer outline, minus the halves, the RS02 ring, the vendor RS02 and the hub (E1, arm
frame), each grown by MARGIN. The 13 x 3.5 bundle reserve sits on the checked route from r 21.5 (theta 68). Items are boxes with
their long axis along Y (section a x b, either way round), placed on a 1 mm grid by random search, each clear of the cavity
walls (MARGIN) and of every item already placed.
    python neck_pack.py EXPORTS_DIR RS02FIT_DIR HUB_STL OUT_JSON VARIANT [TRIALS=400]      (under capped.py)
Trial 0 packs in list order, highest first; the rest pick random orders and random feasible spots."""
import json, sys
from pathlib import Path
import numpy as np, shapely, trimesh
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

HX, CZ = 170.49, 5.985875
E, FIT, HUB, OUT, VAR = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5]
W, T, MARGIN, TH = 13.0, 3.5, 0.5, 68.0
sys.path.insert(0, str(FIT))
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    from rs02_fit import CLOCK, place      # noqa: E402
parts = {n: trimesh.load(E / f'upper_arm_organic_{n}_left.STL') for n in ('front', 'back', 'rs02_ring')}
parts['rs02'] = place(CLOCK)
parts['hub'] = trimesh.load(HUB)

def secY(m, y):
    s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0]); g = Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e) >= 4: g = g.symmetric_difference(Polygon(e[:, [0, 2]]).buffer(0))
    return g.buffer(0)

YS = np.arange(300.0, 229.5, -1.0)
cav, area = {}, {}
for y in YS:
    hv = unary_union([secY(parts[n], y) for n in ('front', 'back')])
    skin = unary_union([Polygon(p.exterior) for p in (hv.geoms if isinstance(hv, MultiPolygon) else [hv]) if not p.is_empty])
    mat = unary_union([secY(m, y) for m in parts.values()])
    c = skin.difference(mat.buffer(MARGIN))
    cav[y] = c; area[y] = c.area

# bundle reserve on the checked route (cable_slack.py, rc 21.5: s_end -23, y1 298, L 53, tau 15)
def route(s_end=-23.0, y1=298.0, L=53.0, tau=15.0, rc=21.5):
    t = np.radians(TH); c = np.array([HX + rc * np.cos(t), CZ + rc * np.sin(t)]); psi0, prev, out = TH + 90.0, 0.0, {}
    for y in YS:
        f = 0.0 if y >= y1 else (1.0 if y <= y1 - L else 0.5 * (1 - np.cos(np.pi * (y1 - y) / L)))
        s, psi = s_end * f, psi0 + tau * f
        v = np.array([np.cos(np.radians(psi - 90.0)), np.sin(np.radians(psi - 90.0))]); c = c + (s - prev) * v; prev = s
        out[y] = affinity.translate(affinity.rotate(box(-W / 2, -T / 2, W / 2, T / 2), psi, origin=(0, 0)), c[0], c[1])
    return out
bund = route()

# items: name, section a x b, length along Y, allowed Y window (top, bottom)
ITEMS = {
  'today': [('holder_M14_drop_5A', 15, 10, 38), ('holder_S4_segment_5A', 15, 10, 38), ('plug_break_XT30+GH', 12, 11, 32),
            ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
  'C_all3': [('holder_10A_optionC', 16, 11, 70), ('holder_M14_drop_5A', 15, 10, 38), ('holder_S4_segment_5A', 15, 10, 38),
             ('plug_break_XT30+GH', 12, 11, 32), ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
  'C_replace_S4': [('holder_10A_optionC', 16, 11, 70), ('holder_M14_drop_5A', 15, 10, 38), ('plug_break_XT30+GH', 12, 11, 32),
                   ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
  'C_holder_only': [('holder_10A_optionC_body', 16, 11, 40)],
  'decided_big': [('holder_10A_body_plus2', 18, 13, 42), ('plug_break_XT30+GH', 12, 11, 32), ('M14_splice_lump', 8, 8, 40),
                  ('RS02_cable_dia7', 7, 7, 30)],
  'decided': [('holder_10A_body', 16, 11, 40), ('plug_break_XT30+GH', 12, 11, 32), ('M14_splice_lump', 8, 8, 40),
              ('RS02_cable_dia7', 7, 7, 30)],
  'decided_spades': [('fuse_spade_crimps', 11, 5, 30), ('plug_break_XT30+GH', 12, 11, 32), ('M14_splice_lump', 8, 8, 40),
                     ('RS02_cable_dia7', 7, 7, 30)],
  'C_replace_S4_body_nobreak': [('holder_10A_optionC_body', 16, 11, 40), ('holder_M14_drop_5A', 15, 10, 38),
                                ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
  'today_nobreak': [('holder_M14_drop_5A', 15, 10, 38), ('holder_S4_segment_5A', 15, 10, 38), ('M14_splice_lump', 8, 8, 40),
                    ('RS02_cable_dia7', 7, 7, 30)],
  'C_all3_body': [('holder_10A_optionC_body', 16, 11, 40), ('holder_M14_drop_5A', 15, 10, 38), ('holder_S4_segment_5A', 15, 10, 38),
                  ('plug_break_XT30+GH', 12, 11, 32), ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
  'C_replace_S4_body': [('holder_10A_optionC_body', 16, 11, 40), ('holder_M14_drop_5A', 15, 10, 38), ('plug_break_XT30+GH', 12, 11, 32),
                        ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
  'C_all3_body_nobreak': [('holder_10A_optionC_body', 16, 11, 40), ('holder_M14_drop_5A', 15, 10, 38), ('holder_S4_segment_5A', 15, 10, 38),
                  ('M14_splice_lump', 8, 8, 40), ('RS02_cable_dia7', 7, 7, 30)],
}[VAR]
YTOP, YBOT = 298.0, 231.0
xs, zs = np.arange(140.0, 205.0, 1.0), np.arange(-38.0, 50.0, 1.0)
cand = np.array([(x, z) for x in xs for z in zs])
ylist = [y for y in YS if YBOT <= y <= YTOP]
# static masks: inside the cavity and clear of the bundle reserve, for every Y plane, item and orientation
static = {}
for name, a, b, L in ITEMS:
    for rot, (w, h) in enumerate(((a, b), (b, a))):
        base = box(-w / 2, -h / 2, w / 2, h / 2)
        rects = np.array([affinity.translate(base, x, z) for x, z in cand])
        per = {y: shapely.contains(cav[y], rects) & ~shapely.intersects(rects, bund[y].buffer(MARGIN)) for y in ylist}
        for y0 in ylist:
            span = [y for y in ylist if y0 - L < y <= y0]
            if len(span) >= L:
                static[(name, rot, y0)] = (np.logical_and.reduce([per[y] for y in span]), w, h)
out = dict(variant=VAR, margin=MARGIN, cavity_mm2={int(y): round(area[y]) for y in YS if y % 5 == 0})
rng = np.random.default_rng(1)
N = int(sys.argv[6]) if len(sys.argv) > 6 else 400
best, wins = None, 0
for trial in range(N):
    order = list(ITEMS) if trial == 0 else [ITEMS[k] for k in rng.permutation(len(ITEMS))]
    done = []
    for name, a, b, L in order:
        opts = []
        for (nm, rot, y0), (m, w, h) in static.items():
            if nm != name: continue
            ok = m.copy()
            for d in done:
                if d['y_bot'] <= y0 and y0 - L + 1 <= d['y_top']:      # overlapping in Y
                    ok &= (np.abs(cand[:, 0] - d['x']) >= (w + d['w']) / 2 + MARGIN) | (np.abs(cand[:, 1] - d['z']) >= (h + d['h']) / 2 + MARGIN)
            for j in np.nonzero(ok)[0]: opts.append((y0, rot, j, w, h))
        if not opts: break
        y0, rot, j, w, h = opts[rng.integers(len(opts))] if trial else max(opts, key=lambda o: o[0])
        done.append(dict(name=name, w=w, h=h, length=L, y_top=float(y0), y_bot=float(y0 - L + 1), x=float(cand[j][0]), z=float(cand[j][1]),
                         from_hub_end_face_Y302=round(302.0 - y0, 1)))
    if len(done) == len(ITEMS):
        wins += 1
        if best is None: best = done
    elif best is None and (not out.get('partial') or len(done) > len(out['partial'])):
        out['partial'] = done
out.update(trials=N, all_items_placed_in=wins, example=best)
print(VAR, 'all items placed in', wins, 'of', N, 'random trials')
for d in (best or out.get('partial', [])): print('  ', d['name'], f"{d['w']}x{d['h']}x{d['length']}", 'Y', d['y_bot'], '-', d['y_top'], 'X', d['x'], 'Z', d['z'])
OUT.write_text(json.dumps(out, indent=1)); print('cavity', out['cavity_mm2'])
