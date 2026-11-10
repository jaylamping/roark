"""latch_block.py in.kicad_pcb out.kicad_pcb (KiCad Python): the latch block's supply chain as a designed block.
The latch's own supply (BAT -> F1 -> BAT_F -> R59 22R -> BAT_R -> D8 -> BAT_CTL -> C39, U2) is at 54 V. Placed by the
packer, R59 and D8 stood in the middle of the latch logic, courtyard to courtyard with Q5 (L_B), R48 (MID_B) and the
RUN_B track, and L_B ran 17 mm south past U2's BAT_CTL pins to R16, R17 and C7. Leakage of 0.5 to 20 MOhm from 54 V
into L_B, MID_B, RUN_A or RUN_B pushes the latch toward "run" (LAYOUT_RULES.md, "Leakage from the latch supply"), so
those nets keep 1.5 mm to the chain (tools/domains.py LEAK_SENSITIVE). This script splits the block:
  south of the logic (page Y 173.7-181.8, free until now): R59 and D8, next to F1. BAT_F and BAT_R are 4 mm long and
        stay there. BAT_CTL runs north on F.Cu in one lane (X 114.6) to C39 and U2's pins 5 and 8, with no via.
  at Q5 (the place R59 and D8 left): R16, R17 and C7, so L_B is a 5 mm net round Q5's base and R12.
It (1) places those parts and R49 (MID_B's pull-down, moved up beside R48) (tools/place.py calls place()), (2) rips the chain's nets, L_B and MID_B everywhere, and
the unlocked F.Cu tracks and vias of other nets inside the two areas, and (3) lays the chain and L_B. finish_route.py
re-routes MID_B and whatever else was ripped, to the same 1.5 mm rule.
MODE=check / MODE=sync as in u8_block.py."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, stack, blocks
from blocks import make,key,pkey
IU,MM=pcbnew.FromMM,pcbnew.ToMM
CU=stack.kicad_layers(pcbnew)
# ref: (courtyard centre, pad 1 position)
PLACE={'R59':((114.9,179.8),(117.863,179.8)),    # BAT_F (east, at F1's BAT_F pad) - BAT_R (west)
       'D8':((113.9,175.5),(115.9,175.5)),       # BAT_CTL (east, the lane north starts here) - BAT_R (west, above R59's)
       'R17':((113.7,143.8),(113.7,144.625)),    # L_B (south, straight above Q5's base) - GND
       'C7':((112.1,143.8),(112.1,144.575)),     # L_B (south) - GND
       'R16':((113.0,141.2),(112.175,141.2)),    # RUN (west) - L_B (east)
       'R49':((114.9,138.9),(115.725,138.9))}    # MID_B (east, 3.6 mm from R48's) - GND: it stood south-east, boxed in between
                                                 # the BAT_CTL lane and C1's BAT pad
# Every part of tools/place.py's 'latch' group at its position on the routed board (written by reading the board, after
# the six parts above were moved): the packer placed them once, and with six parts taken out of its list it would pack
# the rest differently. place.py leaves the whole group to place() below. Each entry: courtyard centre, pad 1, rotation.
PLACE_ALL={'U2':((111.550,154.930),(109.400,153.955),0), 'C5':((104.520,160.040),(103.045,160.040),0), 'R7':((103.700,162.810),(102.875,162.810),0),
 'R8':((107.100,169.490),(106.275,169.490),0), 'TP1':((103.719,166.800),(103.717,166.800),0), 'J20':((104.750,136.800),(106.600,132.425),270),
 'R9':((111.600,135.240),(109.287,135.240),0), 'D3':((111.920,131.470),(109.920,131.470),0), 'R10':((107.250,145.900),(107.250,146.725),90),
 'R11':((107.250,149.300),(107.250,150.125),90), 'C6':((107.250,152.700),(107.250,153.475),90), 'R12':((117.750,146.840),(117.750,147.665),90),
 'Q4':((110.350,147.200),(109.412,146.250),0), 'Q5':((114.650,147.200),(113.713,146.250),0), 'R13':((117.750,150.240),(117.750,151.065),90),
 'R14':((117.635,159.800),(117.635,160.625),90), 'R15':((117.635,163.200),(117.635,164.025),90), 'R16':((113.000,141.200),(112.175,141.200),0),
 'R17':((113.700,143.800),(113.700,144.625),90), 'C7':((112.100,143.800),(112.100,144.575),90), 'TP2':((109.924,158.620),(109.923,158.620),90),
 'F1':((115.405,183.496),(114.005,183.496),0), 'C39':((114.165,159.920),(112.690,159.920),0), 'D8':((113.900,175.500),(115.900,175.500),180),
 'D9':((103.970,147.920),(103.970,149.920),90), 'D10':((117.010,132.070),(117.010,133.720),90), 'D11':((104.570,156.850),(102.920,156.850),0),
 'R59':((114.900,179.800),(117.862,179.800),180), 'C42':((116.920,135.840),(115.970,135.840),0), 'D14':((104.695,183.516),(103.045,183.516),0),
 'R48':((116.810,143.240),(116.810,144.152),90), 'R49':((114.900,138.900),(115.725,138.900),180), 'R50':((115.690,166.840),(115.690,167.665),90),
 'Q10':((110.350,151.040),(109.412,150.090),0), 'Q11':((104.150,153.560),(103.213,152.610),0), 'D16':((110.085,183.516),(108.435,183.516),0),
 'R57':((103.700,169.490),(102.875,169.490),0), 'R58':((117.470,138.940),(117.470,139.852),90), 'Q14':((114.650,151.040),(113.713,150.090),0),
 'D22':((116.270,155.530),(116.270,157.180),90), 'TP7':((109.770,162.707),(109.770,162.707),90), 'TP16':((106.621,163.081),(106.623,163.081),0),
 'R38':((107.500,166.000),(106.675,166.000),0), 'D43':((111.000,170.000),(111.000,171.650),90)}
def place(fps):
    """PLACE_ALL's entries carry the board's rotation as a third value: a part whose pad 1 lies at its courtyard centre
    (a test point) can't be turned by pad 1, so it gets that rotation directly; PLACE's six parts override"""
    for ref,(c,p1,rot) in PLACE_ALL.items():
        if ref in PLACE: continue
        if p1 is None or (abs(p1[0]-c[0])<0.05 and abs(p1[1]-c[1])<0.05):
            fps[ref].SetOrientationDegrees(rot); blocks.place_fp(fps[ref],c,None)
        else: blocks.place_fp(fps[ref],c,p1,tol=0.08)
    for ref,(c,p1) in PLACE.items(): blocks.place_fp(fps[ref],c,p1)
OWN={'/BAT_F','/BAT_R','/BAT_CTL','/L_B'}           # laid here in full
RIPALL=OWN|{'/MID_B'}                                # MID_B is re-routed by finish_route.py to the 1.5 mm rule
AREAS=((107.8,119.3,172.6,182.2),(108.3,116.2,137.1,145.4),   # X0, X1, Y0, Y1: where the moved parts land,
       (112.0,116.2,153.5,173.0),(116.2,118.6,144.6,148.6))   # BAT_CTL's lane to C39 and U2, and L_B's leg to R12
def inarea(p): return any(a[0]<=MM(p.x)<=a[1] and a[2]<=MM(p.y)<=a[3] for a in AREAS)
def rip(b):
    kill=[]
    for t in list(b.GetTracks()):
        n=t.GetNetname(); via=t.GetClass()=='PCB_VIA'
        if n in RIPALL: kill.append(t); continue
        if t.IsLocked(): continue
        if via:
            if inarea(t.GetPosition()): kill.append(t)
        elif t.GetLayer()==CU[0] and (inarea(t.GetStart()) or inarea(t.GetEnd())): kill.append(t)
    return kill
ITEMS=[
 # ---- the supply chain, south
 ('t','/BAT_F','F',[(116.805,183.496),(116.805,182.4),(117.863,181.3),(117.863,179.8)]),
 ('t','/BAT_R','F',[(111.937,179.8),(111.937,177.5),(111.9,176.9),(111.9,175.5)]),
 # ---- BAT_CTL: one F.Cu lane north, west of R50, across the place R16/C7/R17 left, into C39 and U2's pins 5 and 8
 ('t','/BAT_CTL','F',[(115.9,175.5),(115.9,173.9),(114.6,172.6),(114.6,162.4),(113.4,161.2),(112.69,160.6),(112.69,159.92)]),
 ('t','/BAT_CTL','F',[(112.69,159.92),(112.69,158.3),(113.7,157.2),(113.7,155.905)]),
 ('t','/BAT_CTL','F',[(113.7,155.905),(115.0,155.905),(115.0,153.955),(113.7,153.955)]),
 # ---- L_B round Q5's base
 ('t','/L_B','F',[(113.7,144.625),(113.713,146.25)]),
 ('t','/L_B','F',[(112.1,144.575),(113.7,144.625)]),
 ('t','/L_B','F',[(113.825,141.2),(114.8,141.2),(114.8,144.625),(113.7,144.625)]),
 ('t','/L_B','F',[(113.713,146.25),(114.5,146.1),(117.75,146.015)]),
]
LAY={'F':CU[0],'2':CU[2],'3':CU[3],'B':CU[5]}
def prims():
    out=[]
    for it in ITEMS:
        if it[0]=='v': out.append(('v',it[1],it[2]))
        else: out+=[('t',it[1],LAY[it[2]],a,c,it[4] if len(it)>4 else .2) for a,c in zip(it[3],it[3][1:])]
    return out
def diff(b):
    """(ITEMS primitives missing from the board, copper of the block's own nets that ITEMS doesn't have)"""
    want={pkey(p):p for p in prims()}; have={}
    for t in b.GetTracks(): have.setdefault(key(t),t)
    return [p for q,p in want.items() if q not in have],[t for q,t in have.items() if q not in want and t.GetNetname() in OWN]
def sync(b,dry=False):
    missing,stale=diff(b)
    for p in missing: print('   latch block missing:',p[1],[b.GetLayerName(p[2])]+list(p[3:]) if p[0]=='t' else p[2])
    for t in stale: print('   latch block stale:',key(t)[1],key(t)[2:])
    if not dry:
        nets={n:b.FindNet(n) for n in OWN}; new=[make(b,p,nets) for p in missing]
        for t in stale: b.Remove(t)
        for t in new: t.SetLocked(True); b.Add(t)
    return len(missing),len(stale)
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); fps={f.GetReference():f for f in b.GetFootprints()}
    mode=os.environ.get('MODE','stamp')
    if mode in ('check','sync'):
        m,s_=sync(b,dry=mode=='check'); print(f'latch block {mode}: {m} primitives missing, {s_} stale')
        if mode=='sync': pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
        sys.exit(1 if mode=='check' and (m or s_) else 0)
    nets={n:b.FindNet(n) for n in OWN}; new=[make(b,p,nets) for p in prims()]   # read before the first Remove
    kill=rip(b); place(fps); print('placed',len(PLACE),'ripping',len(kill),flush=True)
    for t in kill: b.Remove(t)
    for t in new: t.SetLocked(True); b.Add(t)
    print('laid',len(new)); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
