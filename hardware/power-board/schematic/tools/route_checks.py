#!/usr/bin/env python3
"""Stage 3 checks after the signal routing (LAYOUT_RULES.md), beyond KiCad's DRC:
  1. E-stop safety nets keep >= 1.5 mm to 54 V copper on every layer (the rule exists because 0.44 MOhm of leakage into
     UVLO enables bank B by itself).
  2. 54 V copper, and copper riding on 54 V, keeps tools/domains.py's clearance to every other net (0.2 mm coated;
     0.6 mm outer / 0.2 mm inner with MARENGO_COATED=0). Every pair is tested, the 0.2 mm ones too.
     No pair is allowed under 0.2 mm. Inside U1's courtyard (the .kicad_dru rule estop_at_U1) two F.Cu pads, tracks or
     vias keep 0.2 mm even when one is E-stop and the other 54 V: U1's UVLO pin sits 0.2 mm from its SH_P pin.
     "Inside" is tested on the real shapes against the courtyard polygon. A pour never gets this, and is tested in
     tiles, island by island.
     Pairs inside one footprint are listed separately: the package sets those, not the routing.
  3. Kelvin sense pairs: for each SH*_P / SH*_N pair, each leg from the shunt's sense pad to the IC pins it serves (a
     branch that ends at a filter or decoupling part is not counted), its length, and the share of both legs' length
     that runs within 1.0 mm, centre to centre on the same layer, of the other leg. Fails below tools/domains.py
     KELVIN_FLOOR.
  4. No track, via, pad or pour of a 54 V net, of a net riding on 54 V, or of the latch's supply chain (BAT_F, BAT_R,
     BAT_CTL) on the inner layers under the latch block (tools/domains.py LATCH).
  5. No E-stop via inside a 54 V zone outline on any layer.
  6. The inner GND planes and fills (In1-In4) have tools/stack.py PLANE_CLEAR as their zone clearance.
  7. Vias of another net inside a MID pour outline: only the ones at the coordinates in tools/domains.py MID_VIA_OK.
  8. Gate-drive nets take at most 2 vias; a net listed in tools/domains.py GATE_VIA_OK may have exactly its listed vias.
  9. The F.Cu E-stop guard areas (ESTOP_GUARD_*) are the set tools/estop_guards.py generates from the pads.
 10. The latch's 54 V supply chain keeps 1.5 mm to the leakage-sensitive E-stop nets (tools/domains.py): no pair closer.
Run with KiCad's Python: <kicad python> tools/route_checks.py <board.kicad_pcb>   (exit 1 on a violation)"""
import re,sys,math,collections
import pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.FromMM; MM=pcbnew.ToMM
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__))); import domains
ESTOP={n for n in map(str,b.GetNetsByName().keys()) if domains.is_estop(n)}
HV=domains.is_hv; dom=domains.dom; RIDES=domains.rides
import stack, estop_guards
stack.check_board(b)
LAYERS=stack.kicad_layers(pcbnew)
OUTER={pcbnew.F_Cu,pcbnew.B_Cu}
def page(p): return (round(MM(p.x),2),round(MM(p.y),2))
# U1's courtyard (the .kicad_dru rule estop_at_U1): the real courtyard polygon
FINE={}
for r in ('U1',):
    f=b.FindFootprintByReference(r)
    if f: FINE[r]=pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd))
FBOX={r:c.BBox() for r,c in FINE.items()}
def coll(a,c,cl):
    try: return a.Collide(c,cl)
    except Exception: return c.Collide(a,cl)
def enters(s,L):
    """the fine-pitch courtyards the shape itself touches on F.Cu (not its bounding box)"""
    if L!=pcbnew.F_Cu: return frozenset()
    bb=s.BBox(); return frozenset(r for r,c in FINE.items() if bb.Intersects(FBOX[r]) and coll(c,s,0))
items=[]   # (net, layer, shape, label, footprint ref or None, courtyards entered)
def fpref(it):
    f=it.GetParentFootprint() if hasattr(it,'GetParentFootprint') else None
    return f.GetReference() if f else None
TILE=mm(8)
def islands(ps):
    """the fill's islands; a big island is cut into 8 mm tiles, so a collision test runs against a few hundred vertices
    instead of the whole pour (the tiles of one island abut, which changes nothing for clearances to other nets)"""
    for i in range(ps.OutlineCount()):
        one=pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
        for h in range(ps.HoleCount(i)): one.AddHole(ps.Hole(i,h))
        bb=one.BBox()
        if bb.GetWidth()<=TILE and bb.GetHeight()<=TILE: yield one; continue
        y=bb.GetTop()
        while y<bb.GetBottom():
            x=bb.GetLeft()
            while x<bb.GetRight():
                cell=pcbnew.SHAPE_POLY_SET(); cell.NewOutline()
                for px,py in ((x,y),(x+TILE,y),(x+TILE,y+TILE),(x,y+TILE)): cell.Append(px,py)
                cell.BooleanIntersection(one)
                for k in range(cell.OutlineCount()):
                    t=pcbnew.SHAPE_POLY_SET(); t.AddOutline(cell.Outline(k))
                    for h in range(cell.HoleCount(k)): t.AddHole(cell.Hole(k,h))
                    yield t
                x+=TILE
            y+=TILE
for L in LAYERS:
    for p in b.GetPads():
        if p.IsOnLayer(L):   # an unflashed inner layer of a PTH pad keeps only its hole
            s=p.GetEffectiveShape(L) if p.FlashLayer(L) else p.GetEffectiveHoleShape()
            items.append((p.GetNetname(),L,s,f'{fpref(p)}.{p.GetNumber()}',fpref(p),enters(s,L)|({fpref(p)} if fpref(p) in FINE and L==pcbnew.F_Cu else set())))
    for t in b.GetTracks():
        if t.IsOnLayer(L):
            v=t.GetClass()=='PCB_VIA'
            s=t.GetEffectiveShape(L) if not v or t.FlashLayer(L) else t.GetEffectiveHoleShape()
            items.append((t.GetNetname(),L,s,'via' if v else 'track',None,enters(s,L)))
    for z in b.Zones():
        if z.IsOnLayer(L) and not z.GetIsRuleArea() and z.GetNetname():
            for one in islands(z.GetFilledPolysList(L)):   # a pour never gets the courtyard clearance
                items.append((z.GetNetname(),L,one,f'zone {z.GetNetname()}',None,frozenset()))
def pos(s): return page(s.BBox().GetCenter())
BB={}
def box(s):
    k=id(s)
    if k not in BB: bb=s.BBox(); BB[k]=(bb.GetLeft(),bb.GetRight(),bb.GetTop(),bb.GetBottom())
    return BB[k]
def collide(a,c,cl):
    A,C=box(a),box(c); g=mm(cl)
    if A[1]+g<C[0] or C[1]+g<A[0] or A[3]+g<C[2] or C[3]+g<A[2]: return False
    return coll(a,c,mm(cl))
bad=[]; pkg=[]; leak=[]; npairs=collections.Counter()
byL={L:[i for i in items if i[1]==L] for L in LAYERS}
for L in LAYERS:
    # every pair of different nets where one side is 54 V (or rides on 54 V) or E-stop: the rule from tools/domains.py
    hot=[i for i in byL[L] if RIDES(i[0]) or i[0] in ESTOP]
    G=5000000   # 5 mm buckets
    bk={}
    for it in byL[L]:
        x0,x1,y0,y1=box(it[2])
        for gx in range(x0//G,x1//G+1):
            for gy in range(y0//G,y1//G+1): bk.setdefault((gx,gy),[]).append(it)
    for m,_,h,lab2,ref2,cy2 in hot:
        x0,x1,y0,y1=box(h); r=mm(1.5); cand={}
        for gx in range((x0-r)//G,(x1+r)//G+1):
            for gy in range((y0-r)//G,(y1+r)//G+1):
                for it in bk.get((gx,gy),()): cand[id(it)]=it
        for n,_,s_,lab,ref,cy in cand.values():
            if n==m or ((RIDES(n) or n in ESTOP) and (n,lab,id(s_))<(m,lab2,id(h))): continue   # each hot-hot pair once
            if domains.latch_leak(m,n) and collide(h,s_,1.5-0.001): leak.append((b.GetLayerName(L),m,lab2,pos(h),n,lab,pos(s_)))
            cl=domains.clearance(m,n,L in OUTER)
            if cy&cy2: cl=min(cl,0.2)
            npairs[cl]+=1
            if not collide(h,s_,cl-0.001): continue
            rec=(b.GetLayerName(L),m,lab2,pos(h),n,lab,pos(s_),f'<{cl} mm')
            (pkg if ref and ref==ref2 else bad).append(rec)
print('1/2. clearance violations (routing):',len(bad),' pairs tested by rule (mm):',dict(sorted(npairs.items())))
for r in bad: print('   ',r)
print('   inside one footprint (package-set, review only):',len(pkg))
for r in pkg[:20]: print('   ',r)
# ---- 4. no 54 V copper, and none riding on 54 V, on the inner layers under the latch block (tools/domains.py LATCH):
# tracks, vias, pads (a through-hole pad's barrel is inner copper) and pours
lx0,lx1,ly0,ly1=domains.latch_page()
LR=pcbnew.BOX2I(pcbnew.VECTOR2I(mm(lx0),mm(ly0)),pcbnew.VECTOR2L(mm(lx1-lx0),mm(ly1-ly0))); LRS=pcbnew.SHAPE_RECT(LR)
latch=[(b.GetLayerName(L),n,lab,pos(s_)) for L in LAYERS if L not in OUTER for n,_,s_,lab,ref,cy in byL[L]
       if (RIDES(n) or n in domains.LATCH_SUPPLY) and s_.BBox().Intersects(LR) and coll(s_,LRS,0)]
print('4. 54 V, 54 V-riding or latch-supply inner copper (track, via, pad, pour) under the latch block:',len(latch))
for r in latch: print('   ',r)
# ---- 5. no E-stop via inside a 54 V zone outline on any layer: the refill clears 1.5 mm round it, but the via then sits
# in a hole in the 54 V pour with no ground guard between (LAYOUT_RULES, E-stop rule)
esv=[]
for t in b.GetTracks():
    if t.GetClass()!='PCB_VIA' or t.GetNetname() not in ESTOP: continue
    for z in b.Zones():
        if z.GetIsRuleArea() or not HV(z.GetNetname()): continue
        if any(z.IsOnLayer(L) for L in LAYERS) and z.Outline().Contains(t.GetPosition()):
            esv.append((t.GetNetname(),z.GetNetname(),b.GetLayerName(z.GetFirstLayer()),page(t.GetPosition())))
print('5. E-stop vias inside a 54 V zone outline:',len(esv))
for r in esv: print('   ',r)
# ---- 6. the inner GND planes and fills carry stack.PLANE_CLEAR as their zone clearance (solid under the via rows)
def zclr(z):
    c=z.GetLocalClearance()
    c=c.value() if hasattr(c,'value') else c
    return round(MM(c or 0),3)
pl=[(b.GetLayerName(z.GetFirstLayer()),zclr(z)) for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='GND'
    and z.GetFirstLayer() in LAYERS[1:-1] and zclr(z)!=stack.PLANE_CLEAR]
print(f'6. inner GND zones not at {stack.PLANE_CLEAR} mm clearance:',len(pl))
for r in pl: print('   ',r)
# ---- 7. vias of another net inside a MID pour outline: only the documented ones, each at its coordinates
mz=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='/MID']
VIAS=[(t.GetNetname(),page(t.GetPosition()),t.GetPosition()) for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
inmid=[(n,p) for n,p,q in VIAS if n!='/MID' and any(z.Outline().Contains(q) for z in mz)]
mbad=[(n,p,'not a listed exception') for n,p in inmid if not domains.via_listed(p,domains.MID_VIA_OK,n)]
print('7. vias of other nets inside a MID pour outline:',dict(sorted(collections.Counter(n for n,p in inmid).items())),'not at a listed position:',len(mbad))
for r in mbad: print('   ',r)
# ---- 8. gate-drive nets: at most GATE_VIAS_MAX vias; a net in GATE_VIA_OK may have its listed vias and no others
gv=collections.defaultdict(list)
for n,p,q in VIAS:
    if re.match(domains.GATE_RE,n): gv[n].append(p)
gbad=[]
for n,ps in sorted(gv.items()):
    if len(ps)<=domains.GATE_VIAS_MAX: continue
    off=[p for p in ps if not domains.via_listed(p,domains.GATE_VIA_OK,n)]
    if n not in domains.GATE_VIA_OK: gbad.append((n,len(ps),'vias, allowed',domains.GATE_VIAS_MAX))
    elif off or len(ps)>len(domains.GATE_VIA_OK[n]): gbad.append((n,len(ps),'vias; not at a listed position:',off))
print(f'8. gate-drive nets over their via allowance ({domains.GATE_VIAS_MAX}; {", ".join(sorted(domains.GATE_VIA_OK))}: their listed vias):',len(gbad))
for r in gbad: print('   ',r)
# ---- 9. the E-stop guard areas are the generated set
gw,gs=estop_guards.diff(b)
print('9. E-stop guard areas: missing or misplaced',len(gw),'stale',len(gs))
for r in gw: print('    missing/misplaced',r)
for r in gs: print('    stale',r)
# ---- 10. the latch's own 54 V supply chain against the leakage-sensitive E-stop nets (tools/domains.py): none within
# 1.5 mm (the same pairs also fail checks 1/2 through domains.clearance; this line names them as a group)
lbad=[('latch supply pairs',len(leak),'over the ceiling',domains.LEAK_PAIRS_MAX)] if len(leak)>domains.LEAK_PAIRS_MAX else []
print(f'10. latch supply (BAT_F, BAT_R, BAT_CTL) within 1.5 mm of a leakage-sensitive E-stop net: {len(leak)} item pairs (allowed {domains.LEAK_PAIRS_MAX})',dict(sorted(collections.Counter((r[1],r[4]) for r in leak).items())))
for r in leak[:20]: print('   ',r)
if __import__('os').environ.get('LEAK_LIST'):
    for r in leak: print('   ',r)
bad+=latch+esv+pl+mbad+gbad+gw+gs+lbad
# ---- 3. Kelvin pairs
def ptseg(p,a,c):
    dx,dy=c[0]-a[0],c[1]-a[1]; ll=dx*dx+dy*dy
    f=0 if ll==0 else max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/ll))
    return math.hypot(p[0]-a[0]-f*dx,p[1]-a[1]-f*dy)
tr={}
for t in b.GetTracks():
    if t.GetClass()=='PCB_TRACK': tr.setdefault(t.GetNetname(),[]).append((t.GetLayer(),(MM(t.GetStart().x),MM(t.GetStart().y)),(MM(t.GetEnd().x),MM(t.GetEnd().y))))
PADS_BY_NET={}
for p_ in b.GetPads(): PADS_BY_NET.setdefault(p_.GetNetname(),[]).append(p_)
def sense_path(net):
    """the net's tracks that lie on the way from a shunt's sense pad (RS*) to an IC's pin (U*): the Kelvin leg itself.
    Branches that end at a filter or decoupling part (C20 on SH9_P, the port's R0/C2) are not part of the pair
    ("branching only at the ICs"). Shortest paths over the track graph; a track end on another track's middle joins it."""
    import heapq
    T=tr[net]; R=lambda q:(round(q[0],2),round(q[1],2)); adj={}
    def edge(u,v,w,i):
        adj.setdefault(u,[]).append((v,w,i)); adj.setdefault(v,[]).append((u,w,i))
    for i,(L,s_,e_) in enumerate(T): edge(R(s_),R(e_),math.dist(s_,e_),i)
    for i,(L,s_,e_) in enumerate(T):          # T-joins
        for q in (s_,e_):
            for j,(L2,s2,e2) in enumerate(T):
                if j!=i and L2==L and ptseg(q,s2,e2)<0.02 and R(q) not in (R(s2),R(e2)):
                    edge(R(q),R(s2),math.dist(q,s2),j); edge(R(q),R(e2),math.dist(q,e2),j)
    src=[]; dst=[]
    for pd in PADS_BY_NET.get(net,[]):
        ref=pd.GetParentFootprint().GetReference(); node=('pad',ref,pd.GetNumber())
        for u in list(adj):
            if isinstance(u[0],float) and pd.HitTest(pcbnew.VECTOR2I(mm(u[0]),mm(u[1]))): edge(node,u,0.0,-1)
        if ref.startswith('RS'): src.append(node)
        elif ref.startswith('U') or ref in domains.KELVIN_ENDS.get(net,()): dst.append(node)
    dist={u:0.0 for u in src}; prev={}; heap=[(0.0,repr(u),u) for u in src]; heapq.heapify(heap)
    while heap:
        d,_,u=heapq.heappop(heap)
        if d>dist.get(u,1e30): continue
        for v,w,i in adj.get(u,()):
            if d+w<dist.get(v,1e30)-1e-9: dist[v]=d+w; prev[v]=(u,i); heapq.heappush(heap,(d+w,repr(v),v))
    used=set()
    for t in dst:
        while t in prev: u,i=prev[t]; used.add(i); t=u
    used.discard(-1)
    return [T[i] for i in sorted(used)] if used else T
def near(A,B):
    """(length of A, length of A within 1.0 mm centre to centre of B on the same layer), sampled every 0.25 mm"""
    tot=nr=0.0
    for L,s,e in A:
        ln=math.dist(s,e); tot+=ln; k=max(1,int(ln/0.25))
        for i in range(k):
            q=(s[0]+(e[0]-s[0])*(i+0.5)/k,s[1]+(e[1]-s[1])*(i+0.5)/k)
            if any(L2==L and ptseg(q,s2,e2)<=1.0 for L2,s2,e2 in B): nr+=ln/k
    return tot,nr
print('3. Kelvin pairs, sense pad to IC pin: leg lengths (mm); share of each leg, and of both together, within 1.0 mm of the other leg; floor')
kbad=[]
for n in sorted(tr):
    m=re.match(r'(/SH\w*)_P$',n)
    if not m or m.group(1)+'_N' not in tr: continue
    P,Nn=sense_path(n),sense_path(m.group(1)+'_N'); lp,np_=near(P,Nn); ln,nn=near(Nn,P); both=100*(np_+nn)/max(lp+ln,1e-9)
    fl=domains.KELVIN_FLOOR.get(m.group(1))
    if fl is None: kbad.append((m.group(1),'no floor in domains.KELVIN_FLOOR'))
    elif both<fl: kbad.append((m.group(1),f'{both:.1f} % paired, floor {fl} %'))
    print(f'   {m.group(1)}: P {lp:.1f}, N {ln:.1f}; P {100*np_/max(lp,1e-9):.0f} %, N {100*nn/max(ln,1e-9):.0f} %, both {both:.1f} %; floor {fl}')
print('   Kelvin pairs under their floor:',len(kbad))
for r in kbad: print('   ',r)
bad+=kbad
sys.exit(1 if bad else 0)
