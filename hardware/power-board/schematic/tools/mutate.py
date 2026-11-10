"""mutate.py in.kicad_pcb out.kicad_pcb KIND (KiCad Python): a deliberately broken copy of the routed board, for
tools/verify_selftest.sh, which then expects each check to fail on it. Nothing here is ever applied to the real board.
  rules   breaks route_checks.py's checks in one copy:
            1/2  an EN_A stub 0.13 mm from U8's GND pin 2 (a pair at the 0.2 mm rule, and inside U8's courtyard);
            3    SHL3_P's long In2 run moved 3 mm away from its N leg;
            4    a /GATE track (rides on VBUS, not on the 54 V list) on In2 under the latch block;
            7    G2's via in the MID mirror moved 0.3 mm (the count per net stays the same);
            8    three vias on /PRE_G, and GATE_A's via at TP11 moved 0.35 mm;
            9    a stale guard area ESTOP_GUARD_U8_1 at U8's old position;
            10   a BAT_CTL stub within 1.5 mm of MID_B and L_B copper.
  copper  breaks the copper checks: on port 2, R4's branch of the gate node pulled back to a tangent touch with the
          gate line (joint_check, port_template MODE=check); U8's FLT_A jog moved (u8_block MODE=check); a via of another net in the VBUS band and a 12 mm
          no-fill slot across the VBUS stem (pour_width).
  dangle  a dangling 2 mm /VCTL stub in free board area: a DRC type (track_dangling) outside verify_board.sh's allow-list."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
CU=stack.kicad_layers(pcbnew)
def V(p): return pcbnew.VECTOR2I(IU(p[0]),IU(p[1]))
b=pcbnew.LoadBoard(sys.argv[1]); kind=sys.argv[3]
TR=list(b.GetTracks()); add=[]; rm=[]
NETS={str(k):v for k,v in b.GetNetsByName().items()}   # read once: KiCad 10's FindNet can return another net after edits
def near(p,q,tol=0.02): return abs(MM(p.x)-q[0])<tol and abs(MM(p.y)-q[1])<tol
def track(net,L,a,c,w=0.2):
    t=pcbnew.PCB_TRACK(b); t.SetStart(V(a)); t.SetEnd(V(c)); t.SetWidth(IU(w)); t.SetLayer(L); t.SetNet(NETS[net]); add.append(t)
def via(net,p):
    v=pcbnew.PCB_VIA(b); v.SetPosition(V(p)); v.SetWidth(IU(.6)); v.SetDrill(IU(.3)); v.SetNet(NETS[net])
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(CU[0],CU[5]); add.append(v)
def find_via(net,p):
    v=[t for t in TR if t.GetClass()=='PCB_VIA' and t.GetNetname()==net and near(t.GetPosition(),p)]; assert len(v)==1,(net,p,len(v)); return v[0]
def find_track(net,L,a,c):
    v=[t for t in TR if t.GetClass()!='PCB_VIA' and t.GetNetname()==net and t.GetLayer()==L and ((near(t.GetStart(),a) and near(t.GetEnd(),c)) or (near(t.GetStart(),c) and near(t.GetEnd(),a)))]
    assert len(v)==1,(net,a,c,len(v)); return v[0]
refill=False
if kind=='rules':
    track('/EN_A',CU[0],(173.32,146.9),(173.20,146.9))
    t=find_track('/SHL3_P',CU[2],(161.35,208.7),(161.35,215.35)); t.SetStart(V((158.35,208.7))); t.SetEnd(V((158.35,215.35)))
    # a free spot on In2 under the latch block (a track laid across other copper takes that copper's net when saved)
    import domains
    x0,x1,y0,y1=domains.latch_page(); spot=None
    obst=[t.GetEffectiveShape(CU[2]) for t in TR if t.IsOnLayer(CU[2])]+[p.GetEffectiveShape(CU[2]) for p in b.GetPads() if p.IsOnLayer(CU[2])]
    for gy in range(int(y0)+2,int(y1)-2):
        for gx in range(int(x0)+2,int(x1)-3):
            sh=pcbnew.SHAPE_SEGMENT(V((gx,gy)),V((gx+1,gy)),IU(.2))
            if not any(o.Collide(sh,IU(.4)) for o in obst): spot=(gx,gy); break
        if spot: break
    track('/GATE',CU[2],spot,(spot[0]+1,spot[1]))
    find_via('/G2',(149.9,160.19)).SetPosition(V((150.2,160.19)))
    track('/BAT_CTL',CU[0],(115.6,140.1),(115.6,140.7))   # check 10: the latch supply 0.6 mm from R49's MID_B pad and 0.7 mm from L_B
    for p in ((120.0,300.0),(121.0,300.0),(122.0,300.0)): via('/PRE_G',p)
    find_via('/GATE_A',(168.55,164.75)).SetPosition(V((168.55,165.1)))
    k=pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetDoNotAllowZoneFills(True); k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False)
    k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False); k.SetLayer(CU[0]); k.SetZoneName('ESTOP_GUARD_U8_1')
    o=k.Outline(); o.NewOutline()
    for p in ((166.7,149.8),(171.3,149.8),(171.3,155.3),(166.7,155.3)): o.Append(V(p))
    add.append(k)
elif kind=='copper':
    t=find_track('/G_L2',CU[0],(130.1,195.7),(130.1,192.3))   # R4's branch of the gate node: end it 0.2 mm short of the gate line
    if near(t.GetStart(),(130.1,192.3)): t.SetStart(V((130.1,192.5)))
    else: t.SetEnd(V((130.1,192.5)))
    t=find_track('/FLT_A',CU[0],(171.32,146.35),(170.9,146.35)); t.SetStart(V((171.32,146.4))); t.SetEnd(V((170.9,146.4)))
    via('/I2C_SDA',(145.0,185.0))
    k=pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetDoNotAllowZoneFills(True); k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False)
    k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False); k.SetLayerSet(pcbnew.LSET.AllCuMask()); k.SetZoneName('SELFTEST_SLOT')
    o=k.Outline(); o.NewOutline()
    for p in ((138.0,199.9),(150.0,199.9),(150.0,200.6),(138.0,200.6)): o.Append(V(p))
    add.append(k); refill=True
elif kind=='dangle':
    track('/VCTL',CU[0],(160.0,262.0),(162.0,262.0),0.25)
else: raise SystemExit('unknown KIND '+kind)
for t in add: b.Add(t)
if refill: pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[2]); print('mutated',kind,'added',len(add))
