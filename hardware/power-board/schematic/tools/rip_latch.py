"""rip_latch.py in.kicad_pcb out.kicad_pcb (KiCad Python): remove unlocked 54 V inner tracks and vias touching the latch block
(domains.LATCH), then walk outward from the cut ends removing the unlocked tracks/vias of those nets left dangling, so
finish_route.py / finish_shove.py can re-route the connections on the outer layers"""
import sys,pcbnew
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__))); import domains
b=pcbnew.LoadBoard(sys.argv[1]); x0,x1,y0,y1=domains.latch_page(); mm=pcbnew.FromMM
R=pcbnew.BOX2I(pcbnew.VECTOR2I(mm(x0),mm(y0)),pcbnew.VECTOR2L(mm(x1-x0),mm(y1-y0)))
OUT={pcbnew.F_Cu,pcbnew.B_Cu}
pads=[p for fp in b.GetFootprints() for p in fp.Pads()]
def pts(t): return [(t.GetPosition().x,t.GetPosition().y)] if t.GetClass()=='PCB_VIA' else [(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)]
tracks=list(b.GetTracks()); dead=set(); front=[]
for t in tracks:
    n=t.GetNetname()
    if not domains.is_hv(n) or t.IsLocked() or not t.GetBoundingBox().Intersects(R): continue
    if t.GetClass()!='PCB_VIA' and t.GetLayer() in OUT: continue
    dead.add(id(t)); front+= [(n,p) for p in pts(t)]
first=len(dead)
byid={id(t):t for t in tracks}
def onpad(n,p,lay=None):
    v=pcbnew.VECTOR2I(*p)
    return any(pd.GetNetname()==n and (lay is None or pd.IsOnLayer(lay)) and pd.HitTest(v) for pd in pads)
while front:
    n,p=front.pop()
    live=[t for t in tracks if id(t) not in dead and t.GetNetname()==n and p in pts(t)]
    for t in live:
        if t.IsLocked(): continue
        if t.GetClass()=='PCB_VIA':
            others=[o for o in live if o is not t]
            if len({o.GetLayer() for o in others})>=2 or onpad(n,p): continue
        else:
            # track end at p: dangling if nothing else alive there on its layer (or a via) and no pad
            others=[o for o in live if o is not t and (o.GetClass()=='PCB_VIA' or o.GetLayer()==t.GetLayer())]
            if others or onpad(n,p,t.GetLayer()): continue
        dead.add(id(t)); front+=[(n,q) for q in pts(t) if q!=p]
nets=sorted({byid[i].GetNetname() for i in dead})
for i in dead: b.Remove(byid[i])
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
print('removed in latch',first,'plus dangling',len(dead)-first,'nets',nets)
