"""find_spot.py board.kicad_pcb REF X0 Y0 X1 Y1 NEARX NEARY [EXCLUDE_REF ...] (KiCad Python, page mm)
Search free spots for one footprint inside a box: every STEP mm (default 0.5) and 0/90/180/270 deg, its courtyard (+0.25 mm) must
clear every other footprint's courtyard (EXCLUDE_REF ones ignored), its pads must not sit inside a 54 V zone outline when
they carry an E-stop net, and must keep domains.clearance (1.5 mm E-stop to 54 V) to locked copper. Unlocked tracks and
vias the pads would hit are counted (they get ripped and re-routed). Prints the 10 best spots: fewest hits, then
nearest to (NEARX, NEARY). Nothing is changed."""
import sys,os,math,pcbnew
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import domains
b=pcbnew.LoadBoard(sys.argv[1]); ref=sys.argv[2]; X0,Y0,X1,Y1,NX,NY=map(float,sys.argv[3:9]); EXC=set(sys.argv[9:])|{ref}
F,I=pcbnew.FromMM,pcbnew.ToMM
fp=next(f for f in b.GetFootprints() if f.GetReference()==ref)
others=[f for f in b.GetFootprints() if f.GetReference() not in EXC]
cys=[]
for f in others:
    c=f.GetCourtyard(pcbnew.F_CrtYd)
    if c.OutlineCount(): cys.append((f.GetReference(),c))
STEP=float(os.environ.get('STEP','0.5'))
BOX=pcbnew.BOX2I(pcbnew.VECTOR2I(F(X0-4),F(Y0-4)),pcbnew.VECTOR2L(F(X1-X0+8),F(Y1-Y0+8)))
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Intersects(BOX)]
others=[f for f in others if f.GetBoundingBox(False).Intersects(BOX)]
cys=[(r,c) for r,c in cys if c.BBox().Intersects(BOX)]
hvz=[z for z in b.Zones() if not z.GetIsRuleArea() and domains.is_hv(z.GetNetname())]
res=[]
y=Y0
while y<=Y1:
    x=X0
    while x<=X1:
        for rot in (0,90,180,270):
            fp.SetPosition(pcbnew.VECTOR2I(F(x),F(y))); fp.SetOrientationDegrees(rot)
            c=fp.GetCourtyard(pcbnew.F_CrtYd)
            ok=True
            for r,oc in cys:
                if c.Collide(oc.Outline(0),F(.25)) if oc.OutlineCount() else False: ok=False; break
            if not ok: continue
            hits=0
            for p in fp.Pads():
                n=p.GetNetname(); sh=p.GetEffectivePolygon(pcbnew.F_Cu,pcbnew.ERROR_INSIDE)
                if domains.is_estop(n) and any(z.Outline().Contains(p.GetPosition()) for z in hvz): ok=False; break
                for t in tracks:
                    if t.GetNetname()==n: continue
                    if t.GetClass()!='PCB_VIA' and t.GetLayer()!=pcbnew.F_Cu: continue
                    cl=domains.clearance(n,t.GetNetname(),True)
                    if sh.Collide(t.GetEffectiveShape(pcbnew.F_Cu),F(cl)):
                        if t.IsLocked(): ok=False; break
                        hits+=1
                if not ok: break
                for f in others:
                    for q in f.Pads():
                        if q.GetNetname()!=n and q.IsOnLayer(pcbnew.F_Cu) and sh.Collide(q.GetEffectiveShape(pcbnew.F_Cu),F(domains.clearance(n,q.GetNetname(),True))): ok=False; break
                    if not ok: break
                if not ok: break
            if ok: res.append((hits,round(math.dist((x,y),(NX,NY)),2),x,y,rot))
        x=round(x+STEP,3)
    y=round(y+STEP,3)
res.sort()
print(ref,'spots',len(res))
for r in res[:10]: print('  hits',r[0],'dist',r[1],'at',r[2],r[3],'rot',r[4])
