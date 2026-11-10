"""port_template.py in.kicad_pcb out.kicad_pcb [PORTS=1,2,...] (KiCad Python): the designed port block.
The six limb ports are one block at 17.5 mm pitch (left ports turned 180 degrees). This script (1) places every small
part of a port at its template position, (2) rips the port's own signal copper and whatever else lies in the control
column, and (3) lays the designed escape of the eFuse (TPS48111) and meter (INA237): pin stubs, the under-body via
slots, the Kelvin pair, the gate drive and the V_L tap. Template coordinates are port 1's page mm; T() maps them to the
other ports. What the template leaves (the runs from its vias to parts outside the block) is closed by finish_route.py.
tools/place.py holds the same part positions (PFIX), so a rebuild lands on this placement."""
import os,sys,re,math
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, domains, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
CU=stack.kicad_layers(pcbnew); F,I2,I3,B=CU[0],CU[2],CU[3],CU[5]
PORT={1:('RS2','U11','C21','U19','Q15',68,50,23),2:('RS3','U12','C22','U20','Q16',78,55,26),3:('RS4','U13','C23','U21','Q17',88,60,29),
      4:('RS5','U14','C24','U22','Q18',98,65,32),5:('RS6','U15','C25','U23','Q19',108,70,35),6:('RS7','U16','C26','U24','Q20',118,75,38)}
def T(k,p):
    """template (port 1 page mm) -> port k page mm"""
    row=(k-1)//2
    return (p[0],p[1]+17.5*row) if k%2 else (300-p[0],390.5-p[1]+17.5*row)
def V(p): return pcbnew.VECTOR2I(IU(p[0]),IU(p[1]))
# ---- placement: role -> (centre, pad 1 position), template mm
PLACE={'R0':((160.275,195.295),(160.275,196.12)),   # SHL_P - CSP, P pad down beside C2's, CSP pad up at the lower lane
       'R1':((160.275,192.245),(160.275,193.07)),   # ISCP - SHL_N, N pad up, ISCP pad down at the upper lane
       'R2':((190.445,195.065),(189.62,195.065)),   # IWRN - GND
       'R3':((190.445,196.615),(189.62,196.615)),   # TMR - GND
       'R4':((169.0,195.295),(169.0,196.12)),       # GPU - G, G pad up beside R5's
       'R5':((169.0,192.245),(169.0,191.42)),       # GPD - G, GPD pad up at the pin channel
       'R6':((184.1,187.9),(183.275,187.9)),       # GC - GND, above C4
       'C0':((187.285,188.025),(187.285,188.8)),    # TMR
       'C1':((190.445,191.965),(189.67,191.965)),   # BST - V_L
       'C2':((160.2,198.6),(160.2,197.65)),         # SHL_P - GND, at the Kelvin pair's corner
       'C3':((190.565,188.845),(190.565,190.32)),   # drain cap
       'C4':((184.1,189.9),(183.15,189.9)),         # GC - GND, beside D0
       'D0':((184.115,192.385),(182.465,192.385)),  # G - GC diode
       'CD':((166.2,202.8),(166.975,202.8))}        # meter 3V3 decoupling under its VS pin
FPS={}; PADS=[]
def load(b):
    """snapshot the footprints and pads first: KiCad 10's lookups can fail after BOARD.Remove/Add"""
    FPS.update({f.GetReference():f for f in b.GetFootprints()}); PADS.extend(b.GetPads())
def refs(k):
    rs,ina,cd,u,q,r0,c0,d0=PORT[k]
    d={f'R{i}':f'R{r0+i}' for i in range(7)}; d.update({f'C{i}':f'C{c0+i}' for i in range(5)}); d.update(D0=f'D{d0}',D1=f'D{d0+1}',D2=f'D{d0+2}',CD=cd,RS=rs,INA=ina,U=u,Q=q)
    return d
def place(b,k):
    R=refs(k); moved=[]
    for role,(c,p1) in PLACE.items():
        fp=FPS[R[role]]; c_=T(k,c); p_=T(k,p1); best=None
        for rot in (0,90,180,270):
            fp.SetOrientationDegrees(rot); fp.SetPosition(V(c_))
            bb=fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetCenter(); fp.Move(pcbnew.VECTOR2I(IU(c_[0])-bb.x,IU(c_[1])-bb.y))
            q=next(p for p in fp.Pads() if p.GetNumber()=='1').GetPosition(); d=math.hypot(MM(q.x)-p_[0],MM(q.y)-p_[1])
            if best is None or d<best[0]: best=(d,rot)
        fp.SetOrientationDegrees(best[1]); fp.SetPosition(V(c_))
        bb=fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetCenter(); fp.Move(pcbnew.VECTOR2I(IU(c_[0])-bb.x,IU(c_[1])-bb.y))
        assert best[0]<0.06,(R[role],best)
        moved.append(fp)
    return moved
# ---- rip: the port's own nets everywhere; every net's copper in the control column and in the part field right of the FET
def portnets(k): return re.compile(rf'^/((EN|INP|CSP|ISCP|IWRN|TMR|GC|BST|GPU|GPD|G)_L{k}|SHL{k}_[PN])$')
WIN=(158.4,192.9,186.45,204.05)   # the port block, template mm
def Tinv(k,p):
    row=(k-1)//2; y=p[1]-17.5*row
    return (p[0],y) if k%2 else (300-p[0],390.5-y)
def inwin(k,x,y):
    X,Y=Tinv(k,(x,y)); return WIN[0]<=X<=WIN[1] and WIN[2]<=Y<=WIN[3]
def rip(b,k):
    """the port's signal nets everywhere, and every other net's copper inside the block except the power stage: VBUS copper,
    the D_L tab vias and pin 4 link, the V_L vias from the FET's pins outward, and the in-pad GND/V_L vias"""
    rx=portnets(k); kill=[]; pads=PADS
    for t in list(b.GetTracks()):
        n=t.GetNetname(); via=t.GetClass()=='PCB_VIA'
        if rx.match(n): kill.append(t); continue
        if n=='/VBUS': continue
        s=t.GetStart(); e=t.GetEnd()
        if not (inwin(k,MM(s.x),MM(s.y)) or inwin(k,MM(e.x),MM(e.y))): continue
        if n==f'/V_L{k}' and Tinv(k,(MM(s.x),MM(s.y)))[0]>171.0 and via: continue
        if n==f'/D_L{k}' and ((not via and MM(t.GetWidth())>=0.45) or (via and any(p.GetNetname()==n and p.HitTest(t.GetPosition()) for p in pads))): continue   # pin 4 link, tab via field
        if via and n=='GND' and any(p.GetNetname()=='GND' and p.HitTest(t.GetPosition()) for p in pads): continue   # in-pad thermal vias
        kill.append(t)
    return kill
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); load(b); ports=[int(x) for x in os.environ.get('PORTS','1,2,3,4,5,6').split(',')]
    for k in ports:
        place(b,k); print(f'port {k}: placed {len(PLACE)} parts',flush=True)
    kill=[t for k in ports for t in rip(b,k)]; print('ripping',len(kill),flush=True)
    for t in kill: b.Remove(t)
    if os.environ.get('ROUTE','1')=='1':
        import port_copper
        for k in ports: port_copper.lay(b,k,FPS)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
