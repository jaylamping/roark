"""u8_block.py in.kicad_pcb out.kicad_pcb (KiCad Python): the designed block of the bank A controller U8 (TPS48100).
U8 sits in a 7 mm column between bank A/B's tabs (SW_D, MID: 54 V) on the west and the absorber's ABS spine (54 V) on the
east, so its E-stop pins (EN_A, FLT_A) can't leave sideways at 1.5 mm. This script turns U8 so its logic row faces north
and its 54 V row south, and splits the column the same way:
  north of U8: the E-stop parts (R27, R28, TP13) and the logic passives (R36, C29, R37), reached straight from the pins on
               F.Cu, with no 54 V part or via beside them;
  south of U8: BST cap, gate resistors, MID tie, the sense resistors and their filter, VS_A's resistor and cap.
It (1) places those parts (page mm; tools/place.py calls place()), (2) rips the column's old copper, keeping the inner
runs that only pass through (GATE_A and SH_P from the west, RUN_A/FLT_A at the top, ABS_N), and (3) lays the designed
copper: the E-stop nets on F.Cu, the SH Kelvin pair on In2 down the middle of the column to R61/R62 (P west, N east),
the gate drive on F.Cu, GA2's last leg. finish_route.py closes what is left (GND vias, the decoupling GNDs)."""
import os,sys,math
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
CU=stack.kicad_layers(pcbnew); LAY={'F':CU[0],'2':CU[2],'3':CU[3],'B':CU[5]}
def V(p): return pcbnew.VECTOR2I(IU(p[0]),IU(p[1]))
# ref: (courtyard centre, pad 1 position or None)
PLACE={'U8':((171.07,149.6),(173.32,147.4)),
 'R28':((173.0,144.8),(173.0,145.625)),    # EN_A (down, at pins 1 and 3) - GND
 'R27':((171.4,144.8),(171.4,143.975)),    # RUN_A (up) - EN_A
 'R36':((169.8,144.6),(169.8,145.425)),  # ISCP_A (down, at pin 8) - GND
 'C29':((168.25,144.75),(168.25,145.525)), # TMR_A (down, at pin 9) - GND
 'R37':((168.25,141.7),(168.25,142.525)),  # TMR_A (down) - GND, above C29
 'TP13':((170.2,142.0),None),              # FLT_A, on its lane, 1.5 mm from Q9's tab
 'C28':((168.45,154.5),(167.5,154.5)),     # BST_A - MID, under pins 12/13
 'R35':((170.6,157.1),(170.6,156.275)),    # G1PD_A (up) - GATE_A
 'R30':((169.0,157.05),(169.0,157.875)),   # GATE_A (down) - MID (up, beside C28's MID pad)
 'R32':((169.6,159.95),(170.425,159.95)),  # GATE_A - GA2
 'C27':((173.5,154.6),(173.5,153.65)),     # VS_A (up, at pin 20) - GND
 'C46':((172.7,160.6),(173.475,160.6)),    # CSP_A - CSN_A, across the two lanes
 'R62':((171.75,163.2),(171.75,164.025)),  # SH_N (down) - CSN_A
 'R61':((172.3,165.6),(171.475,165.6)),    # SH_P - CSP_A
 'R29':((172.3,167.2),(171.475,167.2)),    # SH_P - VS_A
 'C40':((169.15,169.0),(168.2,169.0)),     # MID (at Q2's tab) - GND
 'TP11':((169.023,163.961),None),          # GATE_A, on the In3 run from the west
 'TP15':((173.6,169.6),None)}              # ABS
def place(fps,table=None):
    """put each footprint of the table (default: this block's PLACE) with its courtyard centre and pad 1 where given"""
    for ref,(c,p1) in (table or PLACE).items():
        fp=fps[ref]; best=None
        for rot in (0,90,180,270):
            fp.SetOrientationDegrees(rot); fp.SetPosition(V(c))
            bb=fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetCenter(); fp.Move(pcbnew.VECTOR2I(IU(c[0])-bb.x,IU(c[1])-bb.y))
            if p1 is None: best=(0,rot); break
            q=next(p for p in fp.Pads() if p.GetNumber()=='1').GetPosition(); d=math.hypot(MM(q.x)-p1[0],MM(q.y)-p1[1])
            if best is None or d<best[0]: best=(d,rot)
        fp.SetOrientationDegrees(best[1]); fp.SetPosition(V(c))
        bb=fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetCenter(); fp.Move(pcbnew.VECTOR2I(IU(c[0])-bb.x,IU(c[1])-bb.y))
        assert best[0]<0.06,(ref,best)
WIN=(167.2,174.7,139.0,170.6)
LOCAL={'/'+n for n in 'ISCP_A TMR_A VS_A BST_A CSP_A CSN_A G1PD_A EN_A'.split()}
KEEPVIA={(170.65,140.55),(169.75,140.75),(168.55,158.85),(168.55,164.75)}   # RUN_A, FLT_A, GATE_A (two)
def inwin(p): return WIN[0]<=MM(p.x)<=WIN[1] and WIN[2]<=MM(p.y)<=WIN[3]
def xy(p): return (round(MM(p.x),2),round(MM(p.y),2))
def rip(b):
    kill=[]
    for t in list(b.GetTracks()):
        n=t.GetNetname(); via=t.GetClass()=='PCB_VIA'; s=t.GetStart(); e=t.GetEnd()
        if n in LOCAL: kill.append(t); continue
        if not (inwin(s) or inwin(e)): continue
        if via:
            if xy(s) not in KEEPVIA: kill.append(t)
            continue
        L=t.GetLayer()
        if L in (CU[0],CU[5]):
            if n=='/GATE_A' and (xy(s)==(168.55,164.75) or xy(e)==(168.55,164.75)): continue   # stub to TP11
            kill.append(t); continue
        # inner layers: cut the SH pair where it turned into the old block, and GA2's old last leg
        if n=='/SH_P' and min(MM(s.y),MM(e.y))>=147.6 and max(MM(s.x),MM(e.x))>169.4: kill.append(t)
        elif n=='/SH_N' and min(MM(s.y),MM(e.y))>=147.1: kill.append(t)
        elif n=='/GA2' and max(MM(s.x),MM(e.x))>167.2: kill.append(t)
        elif n in ('/MID','/ABS','/GND','GND'): kill.append(t)
    return kill
ITEMS=[
 # ---- E-stop and logic row (north), F.Cu
 ('t','/EN_A','F',[(173.32,147.0),(173.32,146.5),(173.1,145.9)]), ('t','/EN_A','F',[(172.32,147.0),(172.32,146.5),(172.6,145.9)]),
 ('t','/EN_A','F',[(171.4,145.625),(173.0,145.625)]),
 ('t','/FLT_A','F',[(171.32,147.0),(171.32,146.4),(170.9,146.4),(170.6,146.1),(170.6,141.4),(169.95,140.9),(169.75,140.75)]),
 ('t','/RUN_A','F',[(170.65,140.55),(171.4,141.3),(171.4,143.7)]),
 ('t','/TMR_A','F',[(169.32,147.0),(169.32,146.5),(168.9,146.1),(168.4,145.8)]),
 ('t','/TMR_A','F',[(167.9,145.525),(167.4,145.525),(167.4,142.9),(167.8,142.525),(168.0,142.525)]),
 ('t','/ISCP_A','F',[(169.82,147.0),(169.82,145.6)]),
 ('t','GND','F',[(168.82,147.9),(168.82,150.2)]), ('v','GND',(168.82,150.2)),
 ('t','GND','F',[(170.32,147.9),(170.82,147.9)]), ('t','GND','F',[(170.82,147.9),(170.9,149.2)]), ('v','GND',(170.9,149.2)),
 ('t','GND','F',[(172.82,147.9),(172.82,149.0)]), ('v','GND',(172.82,149.0)),
 # ---- 54 V row (south)
 ('t','/VS_A','F',[(173.32,151.3),(173.32,150.2)]), ('v','/VS_A',(173.32,150.2)), ('t','/VS_A','F',[(173.32,152.3),(173.4,153.4)]),
 ('t','/VS_A','2',[(173.32,150.2),(173.75,150.65),(173.75,167.6),(173.9,168.1)]), ('v','/VS_A',(173.9,168.1)), ('t','/VS_A','F',[(173.9,168.1),(173.35,167.4)]),
 ('t','/CSN_A','F',[(171.82,152.3),(171.82,162.4)]),
 ('t','/CSP_A','F',[(172.32,152.3),(172.32,159.5),(173.0,160.2),(173.3,160.4)]), ('t','/CSP_A','F',[(173.2,160.9),(173.2,164.6),(173.125,165.4)]),
 ('t','/GATE_A','F',[(170.82,152.3),(170.82,152.9),(171.4,153.5),(171.4,157.6),(171.05,157.925),(170.9,157.925)]),
 ('t','/GATE_A','F',[(170.6,157.925),(170.5,159.6)]), ('t','/GATE_A','F',[(170.2,157.925),(169.3,157.875)]),
 ('t','/GATE_A','F',[(168.55,158.85),(168.85,158.1)]),
 ('t','/G1PD_A','F',[(170.32,152.3),(170.32,153.0),(170.6,153.3),(170.6,156.1)]),
 ('t','/MID','F',[(169.82,152.3),(169.82,153.4),(169.6,154.0)]), ('t','/MID','F',[(169.3,155.0),(169.1,156.0)]),
 ('t','/MID','F',[(168.7,156.225),(167.2,156.225)]), ('t','/MID','F',[(168.0,169.0),(166.6,169.0)]),
 ('t','/BST_A','F',[(169.32,152.3),(169.32,152.9),(168.3,153.92),(167.8,154.1)]),
 # ---- SH Kelvin pair, In2: from the old diagonal down the column
 ('t','/SH_P','2',[(169.15,147.65),(169.6,148.35),(169.6,165.2),(170.0,165.6),(170.35,165.6)]), ('v','/SH_P',(170.35,165.6)),
 ('t','/SH_P','2',[(169.35,160.95),(169.6,160.95)]),
 ('t','/SH_P','F',[(170.35,165.6),(171.3,165.6)]), ('t','/SH_P','F',[(171.475,165.6),(171.475,167.2)]),
 ('t','/SH_N','2',[(169.55,147.15),(170.0,147.8),(170.0,163.5),(170.45,163.95),(170.75,164.1)]), ('v','/SH_N',(170.75,164.1)),
 ('t','/SH_N','F',[(170.75,164.1),(171.4,164.05)]),
 # ---- GA2's last leg and the ABS test point
 ('t','/GA2','2',[(167.15,155.75),(167.95,156.55),(167.95,157.0)]), ('v','/GA2',(167.95,157.0)),
 ('t','/GA2','F',[(167.95,157.0),(167.9,159.4),(168.5,159.95)]),
 ('t','/ABS','F',[(173.6,169.6),(174.6,168.6),(175.4,166.6)],0.25),
]
def lay(b):
    new=[]
    for it in ITEMS:
        ni=b.FindNet(it[1]); assert ni,it[1]
        if it[0]=='v':
            v=pcbnew.PCB_VIA(b); v.SetPosition(V(it[2])); v.SetWidth(IU(.6)); v.SetDrill(IU(.3)); v.SetNet(ni)
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(CU[0],CU[5]); new.append(v)
        else:
            w=it[4] if len(it)>4 else (.25 if it[1] in ('GND','/MID') else .2)
            for a,c in zip(it[3],it[3][1:]):
                t=pcbnew.PCB_TRACK(b); t.SetStart(V(a)); t.SetEnd(V(c)); t.SetWidth(IU(w)); t.SetLayer(LAY[it[2]]); t.SetNet(ni); new.append(t)
    for t in new: t.SetLocked(True); b.Add(t)
    return len(new)
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); fps={f.GetReference():f for f in b.GetFootprints()}
    place(fps); kill=rip(b); print('placed',len(PLACE),'ripping',len(kill),flush=True)
    for t in kill: b.Remove(t)
    if os.environ.get('ROUTE','1')=='1': print('laid',lay(b))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
