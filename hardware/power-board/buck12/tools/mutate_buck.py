"""mutate_buck.py in.kicad_pcb out.kicad_pcb KIND (KiCad Python): a deliberately broken copy of the buck board for
tools/verify_selftest_buck.sh, which expects verify_buck.sh to fail on it. Nothing here is applied to the real board.
  dangle   a 2 mm COMP stub in free board area: a DRC type outside the allow-list (track_dangling)
  parity   C14's value changed: a schematic parity issue
  spen     an SP_EN track on B.Cu 1 mm below the VIN mirror: spacing_buck.py
  designed the HO track's bottom end moved 0.3 mm (the gate joint) and LO's In3 via moved: copper_buck.py MODE=check
  slot     a 1 mm no-fill rule area across the +12V neck at RS1 and across VOUT: pour_buck.py
  zone     the hot loop's GND plane (BUCK_GND_1) moved 100 mm, name kept: copper_buck.py MODE=check compares outlines
  neck     the 3cd770b neck back: no fill in the F.Cu VOUT pour's extension above RS1 (Y < 36.85) or in the B.Cu mirror
           past X 49, so F.Cu at X 50 is the 2.8 mm beside the SH12_P cut-out: pour_buck.py
  kelvin   RS1's N leg moved from In2 to In3: unpaired and on another layer: kelvin_buck.py
  hole     KO_H2 (the keep-out round the top-right M3 hole) deleted, so the fills reach the hole: holes_buck.py
  nospen   SP_EN's pads and copper moved to a net outside the E-stop class: spacing_buck.py has nothing to check"""
import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','schematic','tools'))
import pcbnew, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM; CU=stack.kicad_layers(pcbnew); O=(30.0,30.0)
def V(x,y): return pcbnew.VECTOR2I(IU(x+O[0]),IU(y+O[1]))
b=pcbnew.LoadBoard(sys.argv[1]); kind=sys.argv[3]; NETS={str(k):v for k,v in b.GetNetsByName().items()}
TR=list(b.GetTracks()); add=[]
def near(p,x,y): return abs(MM(p.x)-x-O[0])<0.02 and abs(MM(p.y)-y-O[1])<0.02
def track(net,L,a,c,w=0.2):
    t=pcbnew.PCB_TRACK(b); t.SetStart(V(*a)); t.SetEnd(V(*c)); t.SetWidth(IU(w)); t.SetLayer(L); t.SetNet(NETS[net]); add.append(t)
if kind=='dangle': track('/COMP',CU[0],(8.0,66.0),(10.0,66.0),0.25)   # (a GND stub would join the GND fill)
elif kind=='parity': next(f for f in b.GetFootprints() if f.GetReference()=='C14').SetValue('100nF 25V X7R')
elif kind=='spen': track('/SP_EN',CU[5],(23.0,40.2),(26.0,40.2),0.2)   # B.Cu, just below the VIN mirror's bottom edge (Y 39.2) at 0.6 mm
elif kind=='designed':
    t=next(t for t in TR if t.GetNetname()=='/HO' and t.GetClass()=='PCB_TRACK' and (near(t.GetEnd(),35.4,22.65) or near(t.GetStart(),35.4,22.65)))
    if near(t.GetEnd(),35.4,22.65): t.SetEnd(V(35.4,22.35))
    else: t.SetStart(V(35.4,22.35))
    v=next(t for t in TR if t.GetClass()=='PCB_VIA' and t.GetNetname()=='/LO' and near(t.GetPosition(),43.4,21.7)); v.SetPosition(V(43.6,21.7))
elif kind=='slot':
    for (x0,y0,x1,y1) in ((44.5,43.0,45.5,52.0),(44.5,36.0,45.5,43.0)):
        k=pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetDoNotAllowZoneFills(True); k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False)
        k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False); k.SetLayerSet(pcbnew.LSET.AllCuMask()); k.SetZoneName('SELFTEST_SLOT')
        o=k.Outline(); o.NewOutline()
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)): o.Append(V(x,y))
        add.append(k)
elif kind=='zone':
    z=next(z for z in b.Zones() if z.GetZoneName()=='BUCK_GND_1'); z.Move(pcbnew.VECTOR2I(IU(100),0))
elif kind=='neck':
    for L,(x0,y0,x1,y1) in ((CU[0],(47.0,34.0,52.6,36.85)),(CU[5],(49.0,34.0,52.6,43.0))):
        k=pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetDoNotAllowZoneFills(True); k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False)
        k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False); k.SetLayer(L); k.SetZoneName('SELFTEST_NECK'); o=k.Outline(); o.NewOutline()
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)): o.Append(V(x,y))
        add.append(k)
elif kind=='kelvin':
    for t in TR:
        if t.GetNetname()=='/SH12_N' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==CU[2]: t.SetLayer(CU[3])
elif kind=='hole':
    b.Remove(next(z for z in b.Zones() if z.GetZoneName()=='KO_H2'))
elif kind=='nospen':
    n=pcbnew.NETINFO_ITEM(b,'/SPEN_MOVED'); b.Add(n)
    for t in TR:
        if t.GetNetname()=='/SP_EN': t.SetNet(n)
    for p in b.GetPads():
        if p.GetNetname()=='/SP_EN': p.SetNet(n)
else: raise SystemExit('unknown KIND '+kind)
for t in add: b.Add(t)
b.Save(sys.argv[2]); print('mutated',kind)
