"""Close short open connections the grid router left, with exact geometry (no raster): for each ratsnest edge still open,
try a few simple paths and keep the first that clears every other net by the project rules (tools/domains.py: 0.2 mm,
1.5 mm E-stop to 54 V) plus 0.02 mm:
  - on a layer both ends share: straight, the two L shapes and the two 45-degree doglegs;
  - otherwise (or if those fail) a via near each end (or the end itself if it is a via or on that layer) and the same
    shapes on In2, In3 or B.Cu between them; vias never on a pad, 0.4 mm from the edge, off the hole keep-outs.
GND zones are refilled afterwards, so they don't block; the L6 VBUS pour doesn't block vias (as SOFTV in grid_route.py).
SKIP (regex) nets are left for hand finishing; DIAG=<net> prints what blocks that net's simple paths and exits. A full
DRC afterwards is the authority (tools/route_stages.sh).
Run with KiCad's Python: <kicad python> tools/patch_route.py <in.kicad_pcb> <out.kicad_pcb> <drc.json of the input>"""
import os, re, sys, math, itertools
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import domains, stack
SKIP = re.compile(os.environ.get('SKIP', r'^$'))
MAXLEN = float(os.environ.get('MAXLEN', '25'))   # mm, longest edge tried
b = pcbnew.LoadBoard(sys.argv[1]); IU = pcbnew.FromMM; MM = pcbnew.ToMM
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
CU = stack.kicad_layers(pcbnew); OUTER = {CU[i] for i in stack.OUTER}; PLANES = {CU[i] for i in stack.GNDPLANE}
ROUT = [CU[i] for i in stack.ROUTABLE]
V = lambda x, y: pcbnew.VECTOR2I(IU(x), IU(y))
eb = b.GetBoardEdgesBoundingBox(); EX0, EY0, EX1, EY1 = MM(eb.GetX()) + 0.4, MM(eb.GetY()) + 0.4, MM(eb.GetRight()) - 0.4, MM(eb.GetBottom()) - 0.4
KO = [z for z in b.Zones() if z.GetIsRuleArea()]
CELL = 2.0
idx = {}   # (layer, cx, cy) -> [obstacle]
def cells(x0, y0, x1, y1):
    for cx in range(int(x0 // CELL), int(x1 // CELL) + 1):
        for cy in range(int(y0 // CELL), int(y1 // CELL) + 1): yield cx, cy
class Ob:
    __slots__ = ('net', 'shape', 'kind', 'soft')
    def __init__(s, net, shape, kind, soft=False): s.net, s.shape, s.kind, s.soft = net, shape, kind, soft
def add(L, net, shape, bb, kind, soft=False):
    o = Ob(net, shape, kind, soft)
    for c in cells(*bb): idx.setdefault((L,) + c, []).append(o)
def bbmm(bx): return MM(bx.GetX()), MM(bx.GetY()), MM(bx.GetRight()), MM(bx.GetBottom())
for p in b.GetPads():
    for L in CU:
        if p.IsOnLayer(L): add(L, p.GetNetname(), p.GetEffectiveShape(L), bbmm(p.GetBoundingBox()), 'pad')
for t in b.GetTracks():
    for L in CU:
        if t.IsOnLayer(L): add(L, t.GetNetname(), t.GetEffectiveShape(L), bbmm(t.GetBoundingBox()), 'via' if t.GetClass() == 'PCB_VIA' else 'track')
for z in b.Zones():
    if z.GetIsRuleArea() or z.GetNetname() == 'GND': continue   # GND fills refill round new copper; planes are GND
    for L in z.GetLayerSet().Seq():
        if L not in CU: continue
        ps = z.GetFilledPolysList(L)
        for i in range(ps.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
            for h in range(ps.HoleCount(i)): one.AddHole(ps.Hole(i, h))
            add(L, z.GetNetname(), one, bbmm(one.BBox()), 'zone', soft=(z.GetNetname() == '/VBUS' and L in OUTER))
def clr(a, bn, L):
    c = domains.clearance(a, bn, L in OUTER)
    return c + 0.02
def free(net, L, shape, bb, via=False):
    seen = set()
    for c in cells(*bb):
        for o in idx.get((L,) + c, ()):
            if id(o) in seen: continue
            seen.add(id(o))
            if via and o.kind == 'pad' and o.shape.Collide(shape, 0): return False   # no via in any pad
            if via and o.kind == 'via' and o.shape.Collide(shape, IU(0.3)): return False   # hole to hole, own net too
            if o.net == net or (via and o.soft): continue
            if o.shape.Collide(shape, IU(clr(net, o.net, L))):
                if DIAG: print('    blocked', b.GetLayerName(L), o.kind, o.net, round(clr(net, o.net, L), 2))
                return False
    return True
def width(n): return 0.25 if n == 'GND' or domains.is_hv(n) else 0.2
def seg_ok(net, L, a, c, w):
    if not all(EX0 <= x <= EX1 for x in (a[0], c[0])) or not all(EY0 <= y <= EY1 for y in (a[1], c[1])): return False
    sh = pcbnew.SHAPE_SEGMENT(V(*a), V(*c), IU(w))
    m = w / 2 + 1.6
    return free(net, L, sh, (min(a[0], c[0]) - m, min(a[1], c[1]) - m, max(a[0], c[0]) + m, max(a[1], c[1]) + m))
def via_ok(net, p):
    if not (EX0 <= p[0] <= EX1 and EY0 <= p[1] <= EY1): return False
    sh = pcbnew.SHAPE_CIRCLE(V(*p), IU(0.3))
    if any(z.Outline().Collide(sh) for z in KO): return False
    bb = (p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2)
    return all(free(net, L, sh, bb, via=True) for L in CU if L not in PLANES)
Z = os.environ.get('Z', '1') == '1'
DIAG = os.environ.get('DIAG')
def shapes(p, q):
    """candidate polylines from p to q"""
    (x0, y0), (x1, y1) = p, q; dx, dy = x1 - x0, y1 - y0; out = [[p, q]]
    if abs(dx) > 1e-6 and abs(dy) > 1e-6:
        out += [[p, (x1, y0), q], [p, (x0, y1), q]]
        d = min(abs(dx), abs(dy)); sx, sy = math.copysign(1, dx), math.copysign(1, dy)
        out += [[p, (x0 + sx * d, y0 + sy * d), q], [p, (x1 - sx * d, y1 - sy * d), q]]
    if Z:   # Z shapes through a channel offset up to 3 mm outside the ends' box, 0.25 mm steps
        lo, hi = min(x0, x1) - 3, max(x0, x1) + 3
        for k in range(int((hi - lo) / 0.25) + 1):
            xk = lo + 0.25 * k; out.append([p, (xk, y0), (xk, y1), q])
        lo, hi = min(y0, y1) - 3, max(y0, y1) + 3
        for k in range(int((hi - lo) / 0.25) + 1):
            yk = lo + 0.25 * k; out.append([p, (x0, yk), (x1, yk), q])
    return [[(round(x, 4), round(y, 4)) for x, y in s] for s in out]
def path_ok(net, L, pts, w): return all(seg_ok(net, L, a, c, w) for a, c in zip(pts, pts[1:]))
def plen(pts): return sum(math.dist(a, c) for a, c in zip(pts, pts[1:]))
def commit(net, items):
    """items: ('t', L, pts, w) or ('v', p)"""
    ni = b.FindNet(net)
    for it in items:
        if it[0] == 't':
            _, L, pts, w = it
            for a, c in zip(pts, pts[1:]):
                if math.dist(a, c) < 1e-4: continue
                t = pcbnew.PCB_TRACK(b); t.SetStart(V(*a)); t.SetEnd(V(*c)); t.SetWidth(IU(w)); t.SetLayer(L); t.SetNet(ni); b.Add(t)
                add(L, net, t.GetEffectiveShape(L), (min(a[0], c[0]) - 1, min(a[1], c[1]) - 1, max(a[0], c[0]) + 1, max(a[1], c[1]) + 1), 'track')
        else:
            p = it[1]; v = pcbnew.PCB_VIA(b); v.SetPosition(V(*p)); v.SetWidth(IU(0.6)); v.SetDrill(IU(0.3)); v.SetNet(ni); b.Add(v)
            for L in CU: add(L, net, v.GetEffectiveShape(L), (p[0] - 1, p[1] - 1, p[0] + 1, p[1] + 1), 'via')
DIRS = [(math.cos(a), math.sin(a)) for a in [k * math.pi / 4 for k in range(8)]]
def anchors(item, pos, net):
    """(point, layers it can be left on, may_drop) for one end of an edge"""
    p = (MM(pos.x), MM(pos.y))
    if item.GetClass() == 'PCB_VIA': return p, set(ROUT), False
    if item.GetClass() == 'PAD': return p, {L for L in ROUT if item.IsOnLayer(L)}, True
    if item.GetClass() in ('PCB_TRACK', 'PCB_ARC'): return p, {item.GetLayer()}, True
    return p, {L for L in ROUT if item.IsOnLayer(L)}, True   # zone
def try_edge(net, A, B):
    (pa, La, da), (pb, Lb, db) = A, B
    w = width(net); cand = []
    for L in La & Lb:
        for s in shapes(pa, pb): cand.append((plen(s), [('t', L, s, w)]))
    cand.sort(key=lambda c: c[0])
    for _, it in cand:
        if all(path_ok(net, x[1], x[2], x[3]) for x in it): return it
    # via ends: a via at the end itself, or 0.7-1.5 mm away with a stub on the end's layer
    def ends(p, Ls, drop):
        out = [(0.0, p, None)] if not drop else []
        if drop:
            for r in (0.75, 1.0, 1.3, 1.6):
                for dx, dy in DIRS:
                    q = (round(p[0] + dx * r, 3), round(p[1] + dy * r, 3)); out.append((r, q, (min(Ls, key=lambda L: CU.index(L)), [p, q])))
        return out
    EA = [e for e in ends(pa, La, da) if (e[2] is None or path_ok(net, e[2][0], e[2][1], w)) and via_ok(net, e[1])][:12]
    EB = [e for e in ends(pb, Lb, db) if (e[2] is None or path_ok(net, e[2][0], e[2][1], w)) and via_ok(net, e[1])][:12]
    cand = []
    for (ra, qa, sa), (rb, qb, sb) in itertools.product(EA, EB):
        for L in (CU[2], CU[3], CU[5], CU[0]):
            for s in shapes(qa, qb): cand.append((plen(s) + ra + rb + 2.0, sa, qa, sb, qb, L, s))
    cand.sort(key=lambda c: c[0])
    for _, sa, qa, sb, qb, L, s in cand[:int(os.environ.get('NCAND', '30000'))]:
        if path_ok(net, L, s, w):
            it = [('t', L, s, w)]
            if sa: it += [('t', sa[0], sa[1], w)]
            if sb: it += [('t', sb[0], sb[1], w)]
            it += [('v', qa), ('v', qb)]
            if math.dist(qa, qb) < 0.7: continue
            return it
    return None
import json
DRCJ = json.load(open(sys.argv[3]))
DESC = re.compile(r'^(Pad|PTH pad|Track|Via|Zone)\s*(\S*)\s*\[([^\]]*)\](?: of (\S+))?(?: on (\S+))?')
def zone_pt(net, Lname, other):
    """nearest point of the net's fill on that layer to the other end (vertices are dense enough on these pours)"""
    best = None
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net: continue
        L = b.GetLayerID(Lname)
        if not z.IsOnLayer(L): continue
        ps = z.GetFilledPolysList(L)
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            for k in range(o.PointCount()):
                q = (MM(o.CPoint(k).x), MM(o.CPoint(k).y)); d = math.dist(q, other)
                if best is None or d < best[0]: best = (d, q)
    return best[1] if best else None
def parse(it):
    m = DESC.match(it['description']); kind, num, net, ref, lay = m.groups(); p = (it['pos']['x'], it['pos']['y']); lay = (lay or '').rstrip(',')
    if kind in ('Pad', 'PTH pad'):
        f = b.FindFootprintByReference(ref); pad = [q for q in f.Pads() if q.GetNumber() == num][0]
        return net, (MM(pad.GetPosition().x), MM(pad.GetPosition().y)), {L for L in ROUT if pad.IsOnLayer(L)}, True
    if kind == 'Via': return net, p, set(ROUT), False
    if kind == 'Track':
        L = b.GetLayerID(lay.rstrip(','))
        best = None
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA' or t.GetNetname() != net or t.GetLayer() != L: continue
            for e in (t.GetStart(), t.GetEnd()):
                q = (MM(e.x), MM(e.y)); d = math.dist(q, p)
                if best is None or d < best[0]: best = (d, q)
        return net, best[1], {L}, True
    return net, ('ZONE', lay), {b.GetLayerID(lay)}, True
edges = []
for u in DRCJ['unconnected_items']:
    A, C = [parse(i) for i in u['items'][:2]]
    net = A[0]
    if SKIP.match(net): continue
    if isinstance(A[1], tuple) and A[1] and A[1][0] == 'ZONE' and isinstance(C[1], tuple) and C[1] and C[1][0] == 'ZONE': continue
    if A[1][0] == 'ZONE': A = (net, zone_pt(net, A[1][1], C[1]), A[2], A[3])
    if C[1][0] == 'ZONE': C = (net, zone_pt(net, C[1][1], A[1]), C[2], C[3])
    if A[1] is None or C[1] is None: continue
    d = math.dist(A[1], C[1])
    if d > MAXLEN: continue
    edges.append((d, net, (A[1], A[2], A[3]), (C[1], C[2], C[3])))
edges.sort(key=lambda e: e[0])
if DIAG:
    for d, net, A_, C_ in edges:
        if net == DIAG:
            print(net, A_, C_)
            for L in A_[1] & C_[1]:
                for sh in shapes(A_[0], C_[0])[:5]: print('  try', b.GetLayerName(L), sh); path_ok(net, L, sh, width(net))
            print('  via spots at A:', sum(via_ok(net, (A_[0][0] + dx * r, A_[0][1] + dy * r)) for r in (0.75, 1.0, 1.3, 1.6) for dx, dy in DIRS))
    sys.exit()
done = 0; left = []
for d, net, a, c in edges:
    it = try_edge(net, a, c)
    if it: commit(net, it); done += 1; print(f'  + {net} {d:.1f} mm: ' + ', '.join(f"{x[0]}" + (f"@{b.GetLayerName(x[1])}" if x[0] == 't' else '') for x in it))
    else: left.append(f'{net} ({d:.1f} mm)')
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
print(f'patch_route: {done} of {len(edges)} edges closed; left: {", ".join(left)}')
