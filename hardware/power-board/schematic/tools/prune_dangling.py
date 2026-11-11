"""prune_dangling.py in.kicad_pcb out.kicad_pcb DRC_JSON NET_REGEX (KiCad Python): starting from each track end that the
KiCad DRC report lists as dangling (track_dangling) on the matching nets, walk back along the chain and remove unlocked
tracks while the point they leave from has nothing else on it (no other same-net track end or mid-segment, via, pad or
zone fill). Stops at the first junction, so it only clears a route whose pad moved away. Locked copper is kept."""
import sys,re,json,pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); d=json.load(open(sys.argv[3])); rx=re.compile(sys.argv[4]); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
F=pcbnew.FromMM; A=F(.005)
ALL=[t for t in b.GetTracks() if rx.search(t.GetNetname())]; byu={t.m_Uuid.AsString():t for t in ALL}
PADS=[p for f in b.GetFootprints() for p in f.Pads() if rx.search(p.GetNetname())]
ZON=[z for z in b.Zones() if not z.GetIsRuleArea() and rx.search(z.GetNetname())]
gone=set()
def ondist(o,p):
    a,c=o.GetStart(),o.GetEnd(); dx,dy=c.x-a.x,c.y-a.y; L2=dx*dx+dy*dy
    u=0 if L2==0 else max(0,min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/L2))
    return ((a.x+u*dx-p.x)**2+(a.y+u*dy-p.y)**2)**.5
def others_at(t,p,L):
    n=t.GetNetname(); out=[]
    for o in ALL:
        if o is t or id(o) in gone or o.GetNetname()!=n: continue
        if o.GetClass()=='PCB_VIA':
            if o.HitTest(p,A): out.append(o)
        elif o.GetLayer()==L and ondist(o,p)<F(.001): out.append(o)   # on its centreline (end or T-junction)
    pad=any(pd.GetNetname()==n and pd.IsOnLayer(L) and pd.HitTest(p,A) for pd in PADS)
    zone=any(z.GetNetname()==n and z.IsOnLayer(L) and z.HitTestFilledArea(L,p) for z in ZON)
    return out,pad or zone
for v in d['violations']:
    if v['type']!='track_dangling': continue
    for it in v['items']:
        t=byu.get(it['uuid'])
        if t is None or t.IsLocked() or id(t) in gone: continue
        # walk from the end that still touches something (the other end is the dangling one)
        s_,fs=others_at(t,t.GetStart(),t.GetLayer()); e_,fe=others_at(t,t.GetEnd(),t.GetLayer())
        if (s_ or fs) and (e_ or fe): continue
        far=t.GetStart() if (s_ or fs) else t.GetEnd()
        while True:
            gone.add(id(t)); L=t.GetLayer()
            nxt,fixed=others_at(t,far,L)
            if fixed or len(nxt)!=1 or nxt[0].GetClass()=='PCB_VIA' or nxt[0].IsLocked(): break
            o=nxt[0]
            if o.GetStart()!=far and o.GetEnd()!=far: break   # T-junction onto a live segment
            others,fx=others_at(o,far,L)
            if fx or [x for x in others if id(x) not in gone]: break
            t=o; far=o.GetEnd() if o.GetStart()==far else o.GetStart()
for t in ALL:
    if id(t) in gone: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('pruned',len(gone))
