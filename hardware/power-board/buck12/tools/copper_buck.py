"""copper_buck.py in.kicad_pcb out.kicad_pcb (KiCad Python): the buck board's designed copper.
  - pours: the power nets on F.Cu (VIN_P, VIN, the SW node, VOUT, +12V, the three fused outputs), mirrors on B.Cu for VIN_P
    (to J1's pins), VIN and VOUT, GND fills on F.Cu, In2, In3 and B.Cu, solid GND planes on In1 (under the hot loop: the
    loop closes through it, 0.21 mm below L1) and In4;
  - vias: GND under every capacitor and FET return, VIN in Q1's drain tab (heat to the B.Cu VIN mirror), the F/B mirror ties;
  - hand-laid tracks: the gate drive (HO on F.Cu straight down from pin 18 to Q1's gate beside the SW pin's track, LO on In3:
    U1's pin order and the FET gates cross once, LAYOUT_RULES), the SW pin's path to the SW node, the bootstrap loop (BST on
    In2), VCC, ILIM (In2, crossing LO once), the meters' Kelvin pairs (both legs on In2), and the current-carrying small nets
    (SP_SW1, SPARE_SW, SPARE_ON, the eFuse supplies).
Everything here is locked and named (zones BUCK_*); a re-run removes the previous set first. Board mm (page mm = board mm +
ORIGIN). MODE=check: exit 1 when the board's designed copper differs from this file."""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'..','..','schematic','tools'))
import pcbnew, stack
from blocks import key,pkey,make
IU,MM=pcbnew.FromMM,pcbnew.ToMM
CU=stack.kicad_layers(pcbnew); LAY={'F':CU[0],'1':CU[1],'2':CU[2],'3':CU[3],'4':CU[4],'B':CU[5]}
O=(30.0,30.0)
def p(x,y): return (round(x+O[0],4),round(y+O[1],4))
PLANE=stack.PLANE_CLEAR
# (name, net, layer, priority, clearance mm, polygon in board mm)
ZONES=[
 ('VIN_P_F','/VIN_P','F',3,0.2,[(9.4,4.3),(16.0,4.3),(16.0,7.0),(11.0,7.0),(11.0,11.0),(16.6,11.0),(17.8,12.2),(17.8,21.6),(1.5,21.6),(1.5,11.0),(9.4,11.0)]),   # stepped back from J1 pin 9 (SP_EN): 1.7 mm
 ('VIN_P_B','/VIN_P','B',3,0.2,[(9.4,4.3),(15.5,4.3),(15.5,21.6),(9.4,21.6)]),   # X <= 15.5: SP_EN (J1 pin 9) keeps 1.7 mm (tools/spacing_buck.py)
 ('VIN_F','/VIN','F',3,0.2,[(19.4,13.9),(29.0,13.9),(29.0,22.1),(34.3,22.1),(34.3,27.5),(29.0,27.5),(29.0,39.2),(11.0,39.2),(11.0,30.3),(19.4,30.3)]),
 ('VIN_B','/VIN','B',3,0.2,[(19.4,13.9),(29.0,13.9),(29.0,21.9),(34.3,21.9),(34.3,28.1),(29.0,28.1),(29.0,39.2),(11.0,39.2),(11.0,30.3),(19.4,30.3)]),
 ('SW_F','/SW','F',3,0.2,[(36.1,22.3),(41.2,22.3),(41.2,28.5),(43.6,30.7),(43.6,33.6),(34.0,33.6),(34.0,30.7),(34.95,28.5),(34.95,23.65),(36.1,23.65)]),
 ('VOUT_F','/VOUT','F',3,0.2,[(31.3,36.9),(47.0,36.9),(47.0,35.0),(52.6,35.0),(52.6,36.9),(53.6,36.9),(53.6,41.5),(49.3,41.5),(49.3,42.9),(31.3,42.9)]),   # up to Y 35 above RS1's SH12_P cut-out
 ('VOUT_B','/VOUT','B',3,0.2,[(31.3,36.9),(47.0,36.9),(47.0,35.0),(52.6,35.0),(52.6,42.9),(31.3,42.9)]),   # past RS1's sense cut-out (X 50), tied to F.Cu at X 50.6-51.8
 ('P12_F','/+12V','F',3,0.2,[(2.0,46.8),(48.9,46.8),(48.9,44.5),(52.4,44.5),(52.4,48.1),(49.3,48.1),(49.3,50.8),(41.0,50.8),(41.0,61.4),(2.0,61.4)]),
 ('JET_F','/+12V_JET','F',3,0.2,[(10.3,62.6),(12.9,62.6),(12.9,78.4),(10.3,78.4)]),
 ('PI_F','/+12V_PI','F',3,0.2,[(20.1,62.6),(22.7,62.6),(22.7,78.4),(20.1,78.4)]),
 ('FAN_F','/+12V_FAN','F',3,0.2,[(29.9,62.6),(32.5,62.6),(32.5,78.4),(29.9,78.4)]),
]+[(f'GND_{k}','GND',k,0,PLANE if k in '1234' else 0.2,[(0.0,0.0),(60.0,0.0),(60.0,85.0),(0.0,85.0)]) for k in 'F1234B']
SOLID=('GND_1','GND_4')   # the planes: solid, every via and pad joined in full
# pads joined in full to their pour (current or hot-loop paths); every other pad on a pour gets thermal relief
FULL={'Q1':'*','Q2':'1235','L1':'*','L2':'*','C2':'*','C1':'*','D1':'*','C3':'*','C4':'*','C5':'*','C6':'*','C7':'*','C8':'*',
      'C9':'*','C10':'*','C11':'*','C12':'*','C13':'*','RS1':'14','RS2':'14','C24':'*','D3':'*','F1':'*','F2':'*','F3':'*','C27':'*','D4':'*','D5':'*',
      'C15':'2','C22':'2','C23':'2','R3':'2'}   # (the last two: small GND pads that the fill reaches from one side only)
def grid(x0,x1,y0,y1,dx,dy):
    out=[]; y=y0
    while y<=y1+1e-9:
        x=x0
        while x<=x1+1e-9: out.append((round(x,3),round(y,3))); x+=dx
        y+=dy
    return out
CAPS_IN=(18.1,21.5,24.9,28.3,31.7)   # C3-C7 centres (Y); their GND pads at X 25.02
VIAS=[
 # GND in the input ceramics' return pads (they sit inside the VIN pour: via in pad, filled and capped), C8, C1, C24, D3, TPV6
 *[('GND',(25.02,y+d)) for y in CAPS_IN for d in (-0.45,0.45)],('GND',(25.55,34.9)),('GND',(11.0,17.67)),
 ('GND',(12.0,48.0)),('GND',(13.4,48.0)),('GND',(21.7,49.0)),('GND',(22.6,49.0)),('GND',(26.0,54.0)),
 # GND: PGND at U1, C16's return, Q2's sources (right of its pins), the output caps' row, C2 and D1
 ('GND',(31.8,16.1)),('GND',(31.6,19.6)),
 *[('GND',v) for v in grid(44.0,45.2,24.1,26.9,1.2,1.4)],
 *[('GND',(x,46.1)) for x in (33.0,34.7,36.4,38.1,39.8,41.5,43.2,44.9,46.6)],
 *[('GND',v) for v in ((2.4,30.4),(2.4,32.6),(2.4,34.8),(6.9,30.4),(6.9,34.8),(4.6,25.4),(2.4,25.4),(6.8,25.4))],
 # VIN: Q1's drain tab (heat to the B.Cu mirror), the F/B ties along the caps, at C2 and at L1
 *[('/VIN',v) for v in grid(30.0,33.0,23.9,25.7,1.5,1.8)],
 *[('/VIN',(22.6,y)) for y in (16.0,19.0,22.0,25.0,28.0,31.0,34.0,37.0)],('/VIN',(19.0,36.3)),('/VIN',(20.4,22.8)),
 # VIN_P: F/B ties at C1 and L1
 *[('/VIN_P',v) for v in ((13.4,12.0),(15.0,12.0),(13.4,13.6),(14.4,20.6),(13.0,19.0))],
 # VOUT: F/B ties under the caps and at L2
 *[('/VOUT',(x,37.8)) for x in (32.4,44.9,46.6,48.3)],*[('/VOUT',(x,40.5)) for x in (32.0,45.0,48.4)],('/VOUT',(50.6,35.9)),('/VOUT',(51.8,35.9)),('/VOUT',(51.8,37.3)),
 # gate drive, bootstrap and ILIM vias
 ('/SH12_P',(50.23,39.87)),('/SH12_P',(54.6,36.6)),('/SH12_N',(52.77,46.73)),('/SH12_N',(55.6,36.5)),('GND',(57.3,36.7)),('/+3V3_PI',(58.2,37.0)),
 ('/SHSP_P',(56.27,59.53)),('/SHSP_P',(59.1,48.0)),('/SHSP_N',(53.73,52.67)),('/SHSP_N',(58.7,49.0)),('GND',(55.6,50.45)),('/+3V3_PI',(57.9,51.9)),
 ('/SP_EN',(41.6,51.4)),   # SP_EN's In2 run ends here (tracks below)
 ('GND',(37.08,4.25)),('GND',(50.4,48.6)),   # C23's return (U4's supply cap)   # C15's return: the analog row's F.Cu GND fill is an island there
 ('/LO',(32.75,16.25)),('/LO',(43.4,21.7)),('/BST',(34.6,16.35)),('/BST',(37.4,17.4)),('/ILIM',(42.4,19.5)),('/ILIM',(30.2,16.4)),
]
# hand-laid tracks: (net, layer, width, [points in board mm])
TRACKS=[
 # HO straight down from pin 18 to Q1's gate on F.Cu, the SW pin's track beside it (the pair), LO on In3 (it crosses HO)
 ('/HO','F',0.2,[(35.4,15.15),(35.4,16.6)]), ('/HO','F',0.5,[(35.4,16.6),(35.4,22.65)]),
 ('/SW','F',0.2,[(35.9,15.15),(35.9,15.55),(36.35,16.0)]), ('/SW','F',0.5,[(36.35,16.0),(36.35,22.6)]),
 ('/LO','F',0.2,[(32.9,15.15),(32.9,15.6),(32.75,16.25)]), ('/LO','3',0.65,[(32.75,16.25),(33.2,19.0),(43.4,21.7)]), ('/LO','F',0.5,[(43.4,21.7),(42.75,22.65)]),
 # bootstrap: BST on In2 under HO and SW to C17, R5 back to the SW track; ILIM's SW end
 ('/BST','F',0.2,[(34.9,15.15),(34.9,15.8),(34.6,16.1),(34.6,16.35)]), ('/BST','2',0.3,[(34.6,16.35),(37.4,17.4)]), ('/BST','F',0.3,[(37.4,17.4),(38.22,17.9)]),
 ('/BST_R','F',0.4,[(39.78,17.9),(39.83,19.9)]), ('/SW','F',0.4,[(38.17,19.9),(36.35,19.9)]),
 ('/SW','F',0.3,[(36.35,16.4),(42.4,16.4),(42.4,16.77)]), ('/SW','F',0.5,[(42.6,30.4),(46.5,29.7)]),
 ('GND','F',0.3,[(37.08,3.0),(37.08,4.25)]),
 # VCC to C16 and PGND to its via and C16's return
 ('/VCC','F',0.2,[(33.4,15.15),(33.4,15.7)]), ('/VCC','F',0.25,[(33.4,15.7),(33.75,16.05),(33.75,17.6),(34.1,17.9)]),
 ('GND','F',0.2,[(32.4,15.15),(32.4,15.45),(31.95,15.9)]), ('GND','F',0.3,[(31.95,15.9),(31.8,16.1),(32.2,17.7)]),
 # ILIM: R6 to U1 pin 11 on In2 at Y 18.3, between BST (In2) and LO (In3): it crosses LO once and never runs over it; C18 at the pin
 ('/ILIM','F',0.2,[(42.4,18.42),(42.4,19.5)]), ('/ILIM','2',0.2,[(42.4,19.5),(41.2,18.3),(31.0,18.3),(30.2,17.5),(30.2,16.4)]),
 ('/ILIM','F',0.2,[(30.2,16.4),(30.2,15.38)]), ('/ILIM','F',0.2,[(30.2,15.38),(31.3,14.25),(32.0,14.25)]),
 # eFuse supplies (4 A class) from the +12V pour
 ('/+12V','F',0.8,[(41.0,58.9),(44.3,58.9),(44.3,57.0)]), ('/+12V','F',0.5,[(44.3,57.0),(45.05,57.0)]), ('/+12V','F',0.6,[(33.05,61.0),(33.05,67.0),(36.2,67.0)]), ('/+12V','F',0.5,[(36.2,67.0),(37.05,67.0)]), ('/+12V','F',0.5,[(33.05,64.6),(34.225,64.6)]),
 ('/+12V','F',0.5,[(36.2,67.0),(36.2,69.4),(36.75,69.8)]),
 # SPARE_ON eFuse enable divider (R16 from +12V, R17 to GND) above the feed
 ('/SPON_EN','F',0.2,[(35.775,62.8),(35.775,66.25),(37.05,66.25)]),
 # meters: Kelvin pairs from the shunts' sense pads (via in pad), both legs on In2 (between the In1 GND plane and the In3 GND fill),
 # 0.6 mm centre to centre from where they meet to the vias at the meter's pins (tools/kelvin_buck.py measures the pairing);
 # the meters' GND, bus and supply pins fanned out to vias
 ('/SH12_P','2',0.2,[(50.23,39.87),(53.3,39.87),(53.3,37.9),(54.6,36.6)]), ('/SH12_P','F',0.2,[(54.6,36.6),(55.0,37.0),(55.0,38.3)]),
 ('/SH12_N','2',0.2,[(52.77,46.73),(53.9,45.6),(53.9,38.2),(55.6,36.5)]), ('/SH12_N','F',0.2,[(55.6,36.5),(55.5,36.9),(55.5,38.3)]),
 ('GND','F',0.2,[(56.5,38.3),(56.5,37.3),(57.0,36.9),(57.3,36.7)]),
 ('/+3V3_PI','F',0.2,[(57.0,38.3),(57.0,37.7),(57.9,37.7),(58.2,37.0)]),
 ('/SHSP_N','2',0.2,[(53.73,52.67),(58.1,52.67),(58.7,52.07),(58.7,49.0)]), ('/SHSP_N','F',0.2,[(58.7,49.0),(57.6,49.0)]),
 ('/SHSP_P','2',0.2,[(56.27,59.53),(59.3,56.5),(59.3,48.6),(59.1,48.0)]), ('/SHSP_P','F',0.2,[(59.1,48.0),(58.1,48.0),(57.6,48.5)]),
 ('/SPARE_SW','F',0.2,[(56.6,49.5),(54.6,49.5),(54.6,51.6),(55.0,52.0),(55.0,52.3)]), ('GND','F',0.2,[(56.8,50.0),(56.2,50.0),(55.6,50.45)]),
 ('/+3V3_PI','F',0.2,[(57.6,50.5),(57.9,50.5),(57.9,51.9)]),
 # SP_EN (E-stop class, tools/hv_buck.py SP_MIN 1.7 mm from 54 V copper): J1 pin 9 on In2 below J1's row, down the corridor
 # between the VIN via column (X 22.6) and Q1's drain vias (X 30), diagonally under the output caps to U3's enable (R14)
 ('/SP_EN','2',0.2,[(18.0,8.68),(18.0,9.4),(19.2,10.6),(25.6,10.6),(26.3,11.3),(26.3,38.5),(33.85,44.95),(33.85,47.25),(38.0,51.4),(41.6,51.4)]),   # straight down through the output caps' GND via row
 ('/SP_EN','F',0.2,[(41.6,51.4),(41.675,53.5)]), ('/SP_EN','F',0.2,[(41.675,53.5),(44.425,56.25),(45.05,56.25)]),
 # SP_SW1: U3 out to C27, D4 and RS2; SPARE_SW: RS2 down the right edge to J5; SPARE_ON: U5 out between D5's pads to J6
 ('/SP_SW1','F',0.25,[(46.95,57.25),(48.0,57.25)]), ('/SP_SW1','F',1.0,[(48.0,57.25),(48.0,63.6)]), ('/SP_SW1','F',1.0,[(48.0,61.3),(52.4,61.3),(54.36,59.4)]),
 ('/SPARE_SW','F',1.2,[(55.64,53.12),(58.3,53.12),(58.3,69.0),(57.6,69.7),(52.92,69.7)]),
 ('/SPARE_ON','F',0.25,[(38.95,67.25),(40.0,67.25)]), ('/SPARE_ON','F',1.0,[(40.0,67.25),(40.0,76.5),(41.0,77.5)]), ('/SPARE_ON','F',0.8,[(40.0,72.6),(39.0,72.6)]),
]
def zone_items(b,nets):
    out=[]
    for name,net,L,prio,cl,poly in ZONES:
        z=pcbnew.ZONE(b); z.SetLayer(LAY[L]); z.SetNet(nets[net]); z.SetZoneName('BUCK_'+name); z.SetAssignedPriority(prio)
        z.SetLocalClearance(IU(cl)); z.SetMinThickness(IU(0.25)); z.SetThermalReliefGap(IU(0.3)); z.SetThermalReliefSpokeWidth(IU(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if name in SOLID else pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        o=z.Outline(); o.NewOutline()
        for x,y in poly: o.Append(IU(x+O[0]),IU(y+O[1]))
        z.SetLocked(True); out.append(z)
    return out
def prims():
    out=[('v',n,p(*xy)) for n,xy in VIAS]
    for net,L,w,pts in TRACKS:
        out+=[('t',net,LAY[L],p(*a),p(*c),w) for a,c in zip(pts,pts[1:])]
    return out
OWNED=lambda t: t.IsLocked()   # the designed copper is the locked copper; the router's is not
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); mode=os.environ.get('MODE','stamp')
    nets={str(k):v for k,v in b.GetNetsByName().items()}
    want={pkey(q):q for q in prims()}
    if mode=='check':
        have={key(t):t for t in b.GetTracks() if OWNED(t)}
        miss=[q for k,q in want.items() if k not in have]; stale=[k for k in have if k not in want]
        # zones by what they are, not by name: net, layer, priority, clearance and outline (to 0.001 mm, any start point)
        def zsig(net,L,prio,cl,pts):
            pts=[(round(x,3),round(y,3)) for x,y in pts]; k=pts.index(min(pts)); pts=pts[k:]+pts[:k]
            return (net,L,prio,round(cl,3),tuple(pts))
        zwant={zsig(net,LAY[L],prio,cl,[(x+O[0],y+O[1]) for x,y in poly]):'BUCK_'+name for name,net,L,prio,cl,poly in ZONES}
        zhave={}
        for z in b.Zones():
            if z.GetIsRuleArea(): continue
            o=z.Outline().Outline(0)
            pts=[(MM(o.CPoint(i).x),MM(o.CPoint(i).y)) for i in range(o.PointCount())]
            zhave[zsig(z.GetNetname(),z.GetLayer(),z.GetAssignedPriority(),MM(z.GetLocalClearance() or 0),pts)]=z.GetZoneName()
        zmiss=[n for s,n in zwant.items() if s not in zhave]; zstale=[n for s,n in zhave.items() if s not in zwant]
        for q in miss: print('   designed copper missing:',q[1],q[2:])
        for k in stale: print('   designed copper stale:',k)
        for n in zmiss: print('   designed zone missing or changed (net, layer, priority, clearance or outline):',n)
        for n in zstale: print('   zone not in copper_buck.py:',n)
        print(f'buck copper check: {len(miss)} missing, {len(stale)} stale; zones {len(zhave)} on the board, {len(zwant)} designed, {len(zmiss)} missing or changed, {len(zstale)} not designed')
        sys.exit(1 if miss or stale or zmiss or zstale else 0)
    old=[z for z in b.Zones() if z.GetZoneName().startswith('BUCK_')]+[t for t in b.GetTracks() if OWNED(t)]
    new=zone_items(b,nets)+[make(b,q,nets) for q in prims()]
    for t in old: b.Remove(t)
    for t in new:
        if t.GetClass()!='ZONE': t.SetLocked(True)
        b.Add(t)
    for f in b.GetFootprints():
        sel=FULL.get(f.GetReference())
        for pd in f.Pads():
            if sel and (sel=='*' or pd.GetNumber() in sel): pd.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
    print('zones',len(ZONES),'vias and tracks',len(new)-len(ZONES),'(replaced',len(old),')')
