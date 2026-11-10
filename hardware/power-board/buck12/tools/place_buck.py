"""place_buck.py net.net template.kicad_pcb out.kicad_pcb (KiCad Python): the buck board, placed by design.
Starts from the main board file (template) for its stackup, layer set and design settings, removes every item, then
lays the 60 x 85 mm outline, four M3 holes, the bare test pads and every part of the netlist at PLACE (board mm from the
board's top-left corner; page mm = board mm + ORIGIN), with its pad nets, value and attributes from the netlist.
Prints courtyard overlaps and parts outside the board; exit 1 on either."""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'..','..','schematic','tools')); from sx import *
import pcbnew
IU,MM=pcbnew.FromMM,pcbnew.ToMM
FPDIR=os.environ.get('KICAD_FP') or next((p for p in ('C:/Program Files/KiCad/10.0/share/kicad/footprints/','/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/') if os.path.isdir(p)),None)
OWN=os.path.join(HERE,'..','marengo_buck12.pretty')
ORIGIN=(30.0,30.0); W,H=60.0,85.0
def P(x,y): return pcbnew.VECTOR2I(IU(x+ORIGIN[0]),IU(y+ORIGIN[1]))
# ref: (courtyard centre x, y in board mm, rotation in degrees)
PLACE={
 # pigtail from the main board's J24 (top edge, cable leaves upward); pins 1-2 +VIN at the left end
 'J1':(20.5,8.42,0),
 # input: crowbar, connector cap, 2.2 uH filter, 47 uF damping cap (left column)
 'D1':(4.6,19.6,270), 'C1':(11.0,16.2,270), 'L1':(18.6,18.0,0), 'C2':(9.5,32.6,180),
 # power stage: input ceramics (VIN pads on Q1's drain), Q1 | Q2 side by side, SW node between, L2 below, out caps under L2
 'C3':(26.5,15.6,180), 'C4':(26.5,19.0,180), 'C5':(26.5,22.4,180), 'C6':(26.5,25.8,180), 'C7':(26.5,29.2,180), 'C8':(26.5,32.4,180),
 'Q1':(32.5,22.3,180), 'Q2':(39.8,22.3,180),
 'L2':(38.8,33.0,270),
 'C9':(33.0,41.0,270), 'C10':(36.4,41.0,270), 'C11':(39.8,41.0,270), 'C12':(43.2,41.0,270), 'C13':(46.6,41.0,270),
 # controller above the FETs, pins 12-19 facing them; drive, bootstrap and VCC parts between
 'U1':(39.0,13.5,270),
 'C16':(36.5,17.4,180), 'C17':(42.5,17.3,0), 'R5':(45.7,17.3,0), 'D2':(31.6,16.6,90),
 'R6':(34.6,11.9,90), 'C18':(34.6,8.6,90),
 'C14':(44.4,14.4,90), 'R1':(44.4,11.0,90),
 # quiet analog corner above U1 (RT, SS, compensation, feedback)
 'R4':(36.0,3.6,0), 'C15':(39.3,3.6,0), 'R11':(42.6,3.6,0), 'C20':(45.9,3.6,0),
 'C21':(36.0,6.0,0), 'R8':(39.3,6.0,0), 'R9':(42.6,6.0,0), 'R10':(45.9,6.0,0),
 'C19':(39.3,8.4,0), 'R7':(42.6,8.4,0),
 # enable: UVLO divider, ON/OFF transistor (right of U1)
 'R2':(50.8,12.2,90), 'R3':(53.0,14.6,90), 'Q3':(56.0,12.0,0), 'R12':(48.2,9.6,90), 'R13':(53.0,9.3,90),
 # output metering and bulk
 'RS1':(51.5,40.8,270), 'U2':(56.0,38.5,90), 'C22':(56.0,43.0,0),
 'C24':(8.5,48.0,0), 'D3':(20.0,46.5,0),
 # fused outputs: fuses above their connectors on the bottom edge
 'F1':(11.6,62.0,90), 'F2':(21.4,62.0,90), 'F3':(31.2,62.0,90),
 'J2':(11.6,79.42,0), 'J3':(21.4,79.42,0), 'J4':(31.2,79.42,0), 'J6':(41.0,79.42,0), 'J5':(54.0,66.5,90),
 # SPARE_SW eFuse, its meter and shunt (right), SPARE_ON eFuse (bottom middle)
 'U3':(46.0,54.0,0), 'R14':(42.5,51.0,0), 'R15':(46.0,57.3,0), 'C25':(42.5,54.0,90), 'C26':(49.5,51.0,90), 'C27':(51.0,57.3,90),
 'D4':(45.0,61.0,0), 'RS2':(55.0,53.6,90), 'U4':(55.0,47.0,0), 'C23':(50.4,47.6,90),
 'U5':(38.0,66.5,0), 'R16':(34.5,63.5,90), 'R17':(34.5,67.5,90), 'R18':(41.5,66.5,90), 'C28':(38.0,69.8,0), 'C29':(38.0,63.3,0),
 'D5':(40.0,72.6,0),
}
HOLES=[(3.5,3.5),(56.5,3.5),(3.5,81.5),(56.5,81.5)]
# bare test pads (not in the schematic, so not in the BOM: copper only, "TP_" + what they carry), board mm
TPADS={'TPV1':('/VIN',23.5,35.5),'TPV2':('/SW',46.5,27.2),'TPV3':('/VOUT',47.8,36.3),'TPV4':('/+12V',20.0,54.0),
       'TPV5':('GND',47.0,30.0),'TPV6':('GND',26.0,54.0),'TPV7':('/EN',57.5,17.0),'TPV8':('/VCC',34.0,14.9),
       'TPV9':('/SS',49.0,2.0),'TPV10':('/COMP',49.0,5.0),'TPV11':('/SPARE_SW',58.2,59.5),'TPV12':('/SPARE_ON',46.0,70.0),'TPV13':('/VIN_P',3.0,11.0)}
def load(lib,name):
    p=os.path.abspath(OWN) if lib=="marengo_buck12" else FPDIR+lib+".pretty"
    try: return pcbnew.FootprintLoad(p,name)
    except Exception as e: raise SystemExit(f"cannot load {p} {name}: {e}")
def put(f,x,y,rot):
    f.SetOrientationDegrees(rot); f.SetPosition(P(x,y))
    c=f.GetCourtyard(pcbnew.F_CrtYd).BBox().GetCenter() if f.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else f.GetPosition()
    t=P(x,y); f.Move(pcbnew.VECTOR2I(t.x-c.x,t.y-c.y))
if __name__=='__main__':
    N=parse(open(sys.argv[1]).read())
    # every footprint is read from its library before the template board is loaded and emptied (KiCad 10's library
    # loader fails after a board's items have been removed)
    LIBS={str(get(c,'ref')[1]):tuple(str(get(c,'footprint')[1]).split(':')) for c in getall(get(N,'components'),'comp')}
    PRE={r:load(*LIBS[r]) for r in LIBS if r in PLACE}
    PRE.update({f'H{k}':load('MountingHole','MountingHole_3.2mm_M3') for k in range(1,len(HOLES)+1)})
    PRE.update({r:load('TestPoint','TestPoint_Pad_D1.5mm') for r in TPADS})
    if os.environ.get('EMPTY')!='1':
        # empty the template in a separate process: removing thousands of items leaves KiCad 10's SWIG layer unable to
        # type the objects made afterwards in the same process
        import subprocess,tempfile
        tmp=os.path.join(tempfile.mkdtemp(),'empty.kicad_pcb')
        subprocess.run([sys.executable,'-c',"import pcbnew,sys;b=pcbnew.LoadBoard(sys.argv[1]);[b.Remove(i) for i in list(b.GetFootprints())+list(b.GetTracks())+list(b.Zones())+list(b.GetDrawings())];b.Save(sys.argv[2])",sys.argv[2],tmp],check=True,capture_output=True)
        sys.argv[2]=tmp
    b=pcbnew.LoadBoard(sys.argv[2])
    padnet={}
    for net in getall(get(N,'nets'),'net'):
        nm=str(get(net,'name')[1])
        for x in getall(net,'node'): padnet[(str(get(x,'ref')[1]),str(get(x,'pin')[1]))]=nm
    nets={}
    def ni(nm):
        if nm not in nets:
            n=pcbnew.NETINFO_ITEM(b,nm); b.Add(n); nets[nm]=n
        return nets[nm]
    # outline
    sh=pcbnew.PCB_SHAPE(b); sh.SetShape(pcbnew.SHAPE_T_RECT); sh.SetStart(P(0,0)); sh.SetEnd(P(W,H)); sh.SetLayer(pcbnew.Edge_Cuts); sh.SetWidth(IU(0.1)); b.Add(sh)
    comps={str(get(c,'ref')[1]):c for c in getall(get(N,'components'),'comp')}
    missing=[r for r in comps if r not in PLACE]; extra=[r for r in PLACE if r not in comps]
    for ref,c in comps.items():
        if ref not in PLACE: continue
        lib,name=LIBS[ref]; f=PRE[ref]
        f.SetReference(ref); f.SetValue(str(get(c,'value')[1])); f.SetFPID(pcbnew.LIB_ID(lib,name))
        ds=get(c,'datasheet'); f.SetField('Datasheet',str(ds[1]) if ds and len(ds)>1 else '')
        props={str(get(p,'name')[1]) for p in getall(c,'property')}
        f.SetExcludedFromBOM('exclude_from_bom' in props); f.SetDNP('dnp' in props)
        for pad in f.Pads():
            nm=padnet.get((ref,pad.GetNumber()))
            if nm: pad.SetNet(ni(nm))   # unconnected-(...) nets too: the parity check expects them
        b.Add(f); put(f,*PLACE[ref])
    for k,(x,y) in enumerate(HOLES,1):
        f=PRE[f'H{k}']; f.SetReference(f'H{k}'); f.SetValue('M3'); f.SetFPID(pcbnew.LIB_ID('MountingHole','MountingHole_3.2mm_M3'))
        f.SetBoardOnly(True); f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True); b.Add(f); put(f,x,y,0)
    for ref,(nm,x,y) in TPADS.items():
        f=PRE[ref]; f.SetReference(ref); f.SetValue('TP '+nm.lstrip('/')); f.SetFPID(pcbnew.LIB_ID('TestPoint','TestPoint_Pad_D1.5mm'))
        f.SetBoardOnly(True); f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True)
        for pad in f.Pads(): pad.SetNet(ni(nm))
        b.Add(f); put(f,x,y,0)
    b.Save(sys.argv[3])
    # checks: courtyard overlaps, parts inside the board (0.3 mm), every netlist part placed
    b=pcbnew.LoadBoard(sys.argv[3]); fps=list(b.GetFootprints()); bad=0
    cy={f.GetReference():f.GetCourtyard(pcbnew.F_CrtYd) for f in fps}
    for i,f in enumerate(fps):
        for g in fps[i+1:]:
            a,c=cy[f.GetReference()],cy[g.GetReference()]
            if a.OutlineCount() and c.OutlineCount() and a.Collide(c.Outline(0),0):
                print('overlap',f.GetReference(),g.GetReference()); bad+=1
        bb=f.GetCourtyard(pcbnew.F_CrtYd).BBox() if cy[f.GetReference()].OutlineCount() else f.GetBoundingBox()
        x0,y0,x1,y1=MM(bb.GetLeft())-ORIGIN[0],MM(bb.GetTop())-ORIGIN[1],MM(bb.GetRight())-ORIGIN[0],MM(bb.GetBottom())-ORIGIN[1]
        if x0<0.0 or y0<0.0 or x1>W or y1>H: print('outside',f.GetReference(),round(x0,2),round(y0,2),round(x1,2),round(y1,2)); bad+=1
    print('placed',len(fps),'missing',missing,'extra',extra,'problems',bad)
    sys.exit(1 if bad or missing or extra else 0)
