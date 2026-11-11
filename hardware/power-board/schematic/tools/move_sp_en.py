"""move_sp_en.py in.kicad_pcb out.kicad_pcb (KiCad Python): put R38 and D43 (the SP_EN feed: RUN -> R38 -> SP_ENR -> D43
-> SP_EN to J24) in the latch block as tools/place.py asks (SP_ENR is an E-stop net, domains.py), at free spots found by
tools/find_spot.py: R38 at page (107.5, 166.0) 0 deg, D43 at (111.0, 170.0) 90 deg. Removes all SP_ENR copper, the
unlocked SP_EN copper, and the unlocked RUN copper left dangling at R38's old pad, so finish_route.py can route them
again. No other footprint moves; locked copper is kept."""
import sys,os,pcbnew
F,I=pcbnew.FromMM,pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1])
fps={f.GetReference():f for f in b.GetFootprints()}
oldpads={(p.GetNetname(),(p.GetPosition().x,p.GetPosition().y)) for r in ('R38','D43') for p in fps[r].Pads()}
for r,x,y,rot in (('R38',107.5,166.0,0),('D43',111.0,170.0,90)):
    fps[r].SetPosition(pcbnew.VECTOR2I(F(x),F(y))); fps[r].SetOrientationDegrees(rot)
tracks=list(b.GetTracks()); dead=set()
lockedsp=[t for t in tracks if t.GetNetname() in ('/SP_ENR','/SP_EN') and t.IsLocked()]
assert not lockedsp, f'locked SP_EN/SP_ENR copper: {len(lockedsp)}'
for t in tracks:
    if t.GetNetname() in ('/SP_ENR','/SP_EN'): dead.add(id(t))
def pts(t): return [(t.GetPosition().x,t.GetPosition().y)] if t.GetClass()=='PCB_VIA' else [(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)]
pads=[p for f in b.GetFootprints() for p in f.Pads()]
def onpad(n,p,lay=None):
    v=pcbnew.VECTOR2I(*p); return any(pd.GetNetname()==n and (lay is None or pd.IsOnLayer(lay)) and pd.HitTest(v) for pd in pads)
front=[(n,p) for n,p in oldpads if n=='/RUN']
while front:
    n,p=front.pop()
    live=[t for t in tracks if id(t) not in dead and t.GetNetname()==n and p in pts(t)]
    for t in live:
        if t.IsLocked(): continue
        if t.GetClass()=='PCB_VIA':
            if len({o.GetLayer() for o in live if o is not t})>=2 or onpad(n,p): continue
        else:
            if [o for o in live if o is not t and (o.GetClass()=='PCB_VIA' or o.GetLayer()==t.GetLayer())] or onpad(n,p,t.GetLayer()): continue
        dead.add(id(t)); front+=[(n,q) for q in pts(t) if q!=p]
byid={id(t):t for t in tracks}
from collections import Counter
print('removed',dict(Counter(byid[i].GetNetname() for i in dead)))
for i in dead: b.Remove(byid[i])
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
