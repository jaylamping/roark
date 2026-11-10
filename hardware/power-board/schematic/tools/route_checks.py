#!/usr/bin/env python3
"""Stage 3 checks after the signal routing (LAYOUT_RULES.md), beyond KiCad's DRC:
  1. E-stop safety nets keep >= 1.5 mm to 54 V copper on every layer (the rule exists because 0.44 MOhm of leakage into
     UVLO enables bank B by itself).
  2. 54 V copper keeps >= 0.6 mm (outer) / 0.2 mm (inner) to every net of another voltage domain (IPC-2221B, 51-100 V).
  Net classes and domains: tools/domains.py (the router uses the same table). Copper entering a fine-pitch IC's courtyard
  (U1, U2, U7, U8) keeps 0.15 mm, as in the .kicad_dru. Pairs inside one footprint are listed
  separately: the package sets those, not the routing.
  3. Kelvin sense pairs: each SH*_P / SH*_N pair runs as a tight pair; reports the length of each leg and the share of
     the P leg that lies within 1.0 mm of the N leg.
  4. No 54 V track, via or pour on the inner layers under the latch block (tools/domains.py LATCH).
  5. No E-stop via inside a 54 V zone outline on any layer.
  6. The inner GND planes and fills (In1-In4) have tools/stack.py PLANE_CLEAR as their zone clearance.
Run with KiCad's Python: <kicad python> tools/route_checks.py <board.kicad_pcb>   (exit 1 on a routing violation)"""
import re,sys
import pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.FromMM
sys.path.insert(0,__import__('os').path.dirname(__file__)); import domains
ESTOP={n for n in map(str,b.GetNetsByName().keys()) if domains.is_estop(n)}
HV=domains.is_hv; dom=domains.dom; RIDES=domains.rides
import stack
stack.check_board(b)
LAYERS=stack.kicad_layers(pcbnew)
OUTER={pcbnew.F_Cu,pcbnew.B_Cu}
items=[]   # (net, layer, shape, label, footprint ref or None)
def fpref(it):
    f=it.GetParentFootprint() if hasattr(it,'GetParentFootprint') else None
    return f.GetReference() if f else None
for L in LAYERS:
    for p in b.GetPads():
        if p.IsOnLayer(L):   # an unflashed inner layer of a PTH pad keeps only its hole
            s=p.GetEffectiveShape(L) if p.FlashLayer(L) else p.GetEffectiveHoleShape()
            items.append((p.GetNetname(),L,s,f'{fpref(p)}.{p.GetNumber()}',fpref(p)))
    for t in b.GetTracks():
        if t.IsOnLayer(L):
            v=t.GetClass()=='PCB_VIA'
            s=t.GetEffectiveShape(L) if not v or t.FlashLayer(L) else t.GetEffectiveHoleShape()
            items.append((t.GetNetname(),L,s,'via' if v else 'track',None))
    for z in b.Zones():
        if z.IsOnLayer(L) and not z.GetIsRuleArea() and z.GetNetname():
            fp=z.GetFilledPolysList(L)
            if fp.OutlineCount(): items.append((z.GetNetname(),L,fp,f'zone {z.GetNetname()}',None))
# fine-pitch courtyards (the .kicad_dru rules fine_pitch_U1/U2/U7/U8): between copper that enters one of these courtyards
# (the IC's own pads, each pin's first escape segment) the rule is 0.15 mm, the package's own pad gap
FINE={}
for r in ('U1','U2','U7','U8'):
    f=b.FindFootprintByReference(r)
    if f: cb=f.GetCourtyard(pcbnew.F_CrtYd).BBox(); FINE[r]=(cb.GetLeft(),cb.GetRight(),cb.GetTop(),cb.GetBottom())
def incy(s,ref):
    A=box(s); return {r for r,(x0,x1,y0,y1) in FINE.items() if not (A[1]<x0 or A[0]>x1 or A[3]<y0 or A[2]>y1)}
def pos(s):
    bb=s.BBox(); c=bb.GetCenter(); return round(pcbnew.ToMM(c.x)-150,1),round(340-(pcbnew.ToMM(c.y)-100),1)
BB={}
def box(s):
    k=id(s)
    if k not in BB: bb=s.BBox(); BB[k]=(bb.GetLeft(),bb.GetRight(),bb.GetTop(),bb.GetBottom())
    return BB[k]
def collide(a,c,cl):
    A,C=box(a),box(c); g=mm(cl)
    if A[1]+g<C[0] or C[1]+g<A[0] or A[3]+g<C[2] or C[3]+g<A[2]: return False
    try: return a.Collide(c,mm(cl))
    except Exception:
        return c.Collide(a,mm(cl))
bad=[]; pkg=[]
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
    for m,_,h,lab2,ref2 in hot:
        x0,x1,y0,y1=box(h); r=mm(1.5); cand={}
        for gx in range((x0-r)//G,(x1+r)//G+1):
            for gy in range((y0-r)//G,(y1+r)//G+1):
                for it in bk.get((gx,gy),()): cand[id(it)]=it
        for n,_,s_,lab,ref in cand.values():
            if n==m or ((RIDES(n) or n in ESTOP) and (n,lab)<(m,lab2)): continue   # each hot-hot pair once
            cl=domains.clearance(m,n,L in OUTER)
            ca=({ref2} if ref2 in FINE else set())|(incy(h,None) or set()); cc=({ref} if ref in FINE else set())|(incy(s_,None) or set())
            if ca&cc: cl=min(cl,0.15)
            if cl<=0.2 or not collide(h,s_,cl-0.001): continue
            rec=(b.GetLayerName(L),m,lab2,n,lab,pos(s_),f'<{cl} mm')
            (pkg if ref and ref==ref2 else bad).append(rec)
print('1/2. clearance violations (routing):',len(bad))
for r in bad: print('   ',r)
print('   inside one footprint (package-set, review only):',len(pkg))
for r in pkg[:20]: print('   ',r)
# ---- 4. no 54 V copper on the inner layers under the latch block (LAYOUT_RULES; tools/domains.py LATCH)
lx0,lx1,ly0,ly1=domains.latch_page()
LR=pcbnew.BOX2I(pcbnew.VECTOR2I(mm(lx0),mm(ly0)),pcbnew.VECTOR2L(mm(lx1-lx0),mm(ly1-ly0)))
latch=[(b.GetLayerName(L),n,lab,pos(s_)) for L in LAYERS if L not in OUTER for n,_,s_,lab,ref in byL[L]
       if HV(n) and not ref and s_.BBox().Intersects(LR) and (lab.startswith('zone') or s_.Collide(pcbnew.SHAPE_RECT(LR),0))]
print('4. 54 V inner copper under the latch block:',len(latch))
for r in latch: print('   ',r)
# ---- 5. no E-stop via inside a 54 V zone outline on any layer: the refill clears 1.5 mm round it, but the via then sits
# in a hole in the 54 V pour with no ground guard between (LAYOUT_RULES, E-stop rule)
esv=[]
for t in b.GetTracks():
    if t.GetClass()!='PCB_VIA' or t.GetNetname() not in ESTOP: continue
    for z in b.Zones():
        if z.GetIsRuleArea() or not HV(z.GetNetname()): continue
        if any(z.IsOnLayer(L) for L in LAYERS) and z.Outline().Contains(t.GetPosition()):
            esv.append((t.GetNetname(),z.GetNetname(),b.GetLayerName(z.GetFirstLayer()),pos(t.GetEffectiveShape(pcbnew.F_Cu))))
print('5. E-stop vias inside a 54 V zone outline:',len(esv))
for r in esv: print('   ',r)
# ---- 6. the inner GND planes and fills carry stack.PLANE_CLEAR as their zone clearance (solid under the via rows)
def zclr(z):
    c=z.GetLocalClearance()
    c=c.value() if hasattr(c,'value') else c
    return round(pcbnew.ToMM(c or 0),3)
pl=[(b.GetLayerName(z.GetFirstLayer()),zclr(z)) for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='GND'
    and z.GetFirstLayer() in LAYERS[1:-1] and zclr(z)!=stack.PLANE_CLEAR]
print(f'6. inner GND zones not at {stack.PLANE_CLEAR} mm clearance:',len(pl))
for r in pl: print('   ',r)
bad+=latch+esv+pl
# ---- Kelvin pairs
tr={}
for t in b.GetTracks():
    if t.GetClass()=='PCB_TRACK': tr.setdefault(t.GetNetname(),[]).append(t)
print('3. Kelvin pairs: leg lengths (mm), share of P within 1.0 mm of N')
for n in sorted(tr):
    m=re.match(r'(/SH\w*)_P$',n)
    if not m or m.group(1)+'_N' not in tr: continue
    P,Nn=tr[n],tr[m.group(1)+'_N']; lp=sum(pcbnew.ToMM(t.GetLength()) for t in P); ln=sum(pcbnew.ToMM(t.GetLength()) for t in Nn)
    near=0.0
    for t in P:
        s=t.GetStart(); e=t.GetEnd(); k=max(1,int(pcbnew.ToMM(t.GetLength())/0.25))
        for i in range(k):
            q=pcbnew.VECTOR2I(int(s.x+(e.x-s.x)*(i+0.5)/k),int(s.y+(e.y-s.y)*(i+0.5)/k))
            if any(u.GetEffectiveShape(u.GetLayer()).Collide(q,mm(1.0)+u.GetWidth()//2) for u in Nn if u.GetLayer()==t.GetLayer()):
                near+=pcbnew.ToMM(t.GetLength())/k
    print(f'   {m.group(1)}: P {lp:.1f}, N {ln:.1f}, paired {100*near/max(lp,1e-9):.0f} %')
sys.exit(1 if bad else 0)
