#!/usr/bin/env python3
"""Stage 2d, before signal routing: a GND via beside every front-side GND pad it can reach, so Freerouting has little GND left.
In1 is solid GND (and In2/L4 GND fills where they are free), so each GND pad needs only a via and a short stub. Pads that
already have a GND via within reach (power-stage via grids, in-pad vias) are skipped. Each via goes to the nearest free
spot within 1.6 mm of the pad edge (0.25 mm grid): 0.25 mm from every other net on F.Cu and B.Cu (0.6 mm from 54 V copper, tools/domains.py), off every hole, and
outside other nets' pours on every layer it passes through. The stub is 0.25 mm wide and must clear other nets' pads.
Pads it can't serve (mostly fine-pitch IC pins) are listed; Freerouting connects those (GND is routable, never on In1).
Run with KiCad's Python, in place: <kicad python> tools/gnd_fanout.py <board.kicad_pcb>"""
import os,sys
import pcbnew
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import domains
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.FromMM
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
G=b.FindNet('GND'); g=G.GetNetCode()
PADS=[p for p in b.GetPads()]; TRK=[t for t in b.GetTracks()]
ZONES=[(z,L,z.GetFilledPolysList(L)) for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode()!=g for L in z.GetLayerSet().Seq()
       if L in (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)]
CL=mm(0.25)
OUTER=(pcbnew.F_Cu,pcbnew.B_Cu)
import functools
@functools.lru_cache(None)
def cl(net,L):
    """clearance to another net's copper: 0.25 mm, or the 54 V rule (tools/domains.py, 0.6 mm on the outer layers) + 0.05"""
    c=domains.clearance('GND',net,L in OUTER); return CL if c<=0.2 else mm(c+0.05)
KO=[z for z in b.Zones() if z.GetIsRuleArea()]   # hole keep-outs (tools/place.py)
def clear(item,layers):
    s0=item.GetEffectiveShape(pcbnew.F_Cu)
    if any(z.Outline().Collide(s0) for z in KO): return False
    for L in layers:
        s=item.GetEffectiveShape(L)
        for p in PADS:
            if p.GetNetCode()!=g and p.IsOnLayer(L) and s.Collide(p.GetEffectiveShape(L),cl(p.GetNetname(),L)): return False
            if p.HasHole() and s.Collide(p.GetEffectiveHoleShape(),CL): return False
        for t in TRK:
            if t.GetNetCode()!=g and t.IsOnLayer(L) and s.Collide(t.GetEffectiveShape(L),cl(t.GetNetname(),L)): return False
        for z,zl,fp in ZONES:
            if zl==L and fp.OutlineCount() and fp.Collide(s,cl(z.GetNetname(),L)): return False
    return True
VL=(pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)   # In1 is GND everywhere
def has_via(p):
    c=p.GetPosition(); r=max(p.GetSize(pcbnew.F_Cu).x,p.GetSize(pcbnew.F_Cu).y)//2+mm(1.0)
    return any(t.GetClass()=='PCB_VIA' and t.GetNetCode()==g and (t.GetPosition()-c).EuclideanNorm()<=r for t in TRK)
done=0; skip=0; fail=[]
for p in PADS:
    if p.GetNetCode()!=g or not p.IsOnLayer(pcbnew.F_Cu) or p.HasHole(): continue
    if has_via(p): skip+=1; continue
    c=p.GetPosition(); hw=p.GetSize(pcbnew.F_Cu).x//2; hh=p.GetSize(pcbnew.F_Cu).y//2
    if int(p.GetOrientationDegrees())%180: hw,hh=hh,hw
    best=None
    for i in range(-14,15):
        for j in range(-14,15):
            q=pcbnew.VECTOR2I(c.x+i*mm(0.25),c.y+j*mm(0.25))
            dx=max(0,abs(q.x-c.x)-hw); dy=max(0,abs(q.y-c.y)-hh)
            d=(dx*dx+dy*dy)**0.5
            if d<mm(0.55) or d>mm(1.6): continue   # outside the pad (no via-in-pad: hand assembly), close to it
            if best and d>=best[0]: continue
            v=pcbnew.PCB_VIA(b); v.SetPosition(q); v.SetDrill(mm(0.3)); v.SetWidth(mm(0.6)); v.SetNet(G)
            if any(t.GetClass()=='PCB_VIA' and (t.GetPosition()-q).EuclideanNorm()<mm(0.8) for t in TRK): continue   # any via, GND too: hole-to-hole
            if not clear(v,VL): continue
            tr=pcbnew.PCB_TRACK(b); tr.SetStart(c); tr.SetEnd(q); tr.SetWidth(mm(0.25)); tr.SetLayer(pcbnew.F_Cu); tr.SetNet(G)
            if not clear(tr,(pcbnew.F_Cu,)): continue
            best=(d,v,tr)
    if best:
        _,v,tr=best; b.Add(v); b.Add(tr); TRK+=[v,tr]; done+=1
    else: fail.append(f'{p.GetParentFootprint().GetReference()}.{p.GetNumber()}')
# second pass for what's left (mostly fine-pitch IC pins boxed in by their neighbours):
#  - a GND pin next to another GND pin of the same part (within 1.3 mm) joins it pad to pad, if that one has a via;
#  - otherwise a dog-leg: out of the pad along the pin's axis, away from the part's centre (0.5-2.5 mm past the pad
#    edge), then to a via within 1.6 mm of that point
def served(p):
    return has_via(p) or any(t.GetClass()=='PCB_TRACK' and t.GetNetCode()==g and (t.GetStart()==p.GetPosition() or t.GetEnd()==p.GetPosition()) for t in TRK)
for k in range(3):   # repeat: a pin joined to a served neighbour serves the next one
    left=[]
    for ref in fail:
        r,n=ref.split('.'); f=b.FindFootprintByReference(r); p=next(q for q in f.Pads() if q.GetNumber()==n)
        c=p.GetPosition(); ok=False
        for q in f.Pads():
            if q is p or q.GetNetCode()!=g or (q.GetPosition()-c).EuclideanNorm()>mm(1.3) or not served(q): continue
            tr=pcbnew.PCB_TRACK(b); tr.SetStart(c); tr.SetEnd(q.GetPosition()); tr.SetWidth(mm(0.2)); tr.SetLayer(pcbnew.F_Cu); tr.SetNet(G)
            if clear(tr,(pcbnew.F_Cu,)): b.Add(tr); TRK.append(tr); ok=True; break
        if not ok and k==2:
            fc=f.GetPosition(); d=c-fc; L=max(1.0,(d.x*d.x+d.y*d.y)**0.5)
            ax=(1,0) if abs(d.x)>=abs(d.y) else (0,1); sg=1 if (d.x if ax[0] else d.y)>0 else -1
            ext=(p.GetSize(pcbnew.F_Cu).x if ax[0] else p.GetSize(pcbnew.F_Cu).y)//2
            if int(p.GetOrientationDegrees())%180: ext=(p.GetSize(pcbnew.F_Cu).y if ax[0] else p.GetSize(pcbnew.F_Cu).x)//2
            best=None
            for e in range(2,11):
                m=pcbnew.VECTOR2I(c.x+sg*ax[0]*(ext+e*mm(0.25)),c.y+sg*ax[1]*(ext+e*mm(0.25)))
                t1=pcbnew.PCB_TRACK(b); t1.SetStart(c); t1.SetEnd(m); t1.SetWidth(mm(0.2)); t1.SetLayer(pcbnew.F_Cu); t1.SetNet(G)
                if not clear(t1,(pcbnew.F_Cu,)): break
                for i in range(-6,7):
                    for j in range(-6,7):
                        q=pcbnew.VECTOR2I(m.x+i*mm(0.25),m.y+j*mm(0.25)); dd=(i*i+j*j)**0.5+e
                        if best and dd>=best[0]: continue
                        if any(t.GetClass()=='PCB_VIA' and (t.GetPosition()-q).EuclideanNorm()<mm(0.8) for t in TRK): continue
                        if any(pp.IsOnLayer(pcbnew.F_Cu) and pp.HitTest(q,mm(0.3)) for pp in f.Pads()): continue
                        v=pcbnew.PCB_VIA(b); v.SetPosition(q); v.SetDrill(mm(0.3)); v.SetWidth(mm(0.6)); v.SetNet(G)
                        if not clear(v,VL): continue
                        t2=pcbnew.PCB_TRACK(b); t2.SetStart(m); t2.SetEnd(q); t2.SetWidth(mm(0.2)); t2.SetLayer(pcbnew.F_Cu); t2.SetNet(G)
                        if (i or j) and not clear(t2,(pcbnew.F_Cu,)): continue
                        best=(dd,t1,v,t2 if (i or j) else None)
            if best:
                for it in best[1:]:
                    if it: b.Add(it); TRK.append(it)
                ok=True
        if not ok: left.append(ref)
    fail=left
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[1])
print(f'GND fanout: {done} vias added, {skip} pads already had one, {len(fail)} not served: {fail}')
