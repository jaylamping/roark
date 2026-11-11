"""Point fixes after the staged routing (tools/route_stages.sh), all checked by DRC afterwards:
  - SH9 Kelvin at U7: the router brings SH9_N into U7 pin 1 from above, across pins 2-3, which blocks SH9_P. SH9_N is
    moved to a via right of pin 1 (In2 run extended) and SH9_P runs on F.Cu from RS9 pin 2 straight down onto pins 2-3.
  - U8: a GND stub into pin 2 that passes 0.13 mm from the EN_A pin (E-stop class, 0.2 mm) is re-ended clear of it. That
    leaves U8 pin 2 without its GND track: the re-route must connect it (DRC reports it unconnected until then).
  - a RUN_A via 1.41 mm from the SH_N diagonal on In2 (E-stop 1.5 mm) moves onto the end of its B.Cu run;
  - the GATE via at (132.0, 161.46), connected on one layer only (a stub end the router left), is removed;
  - the VBUS pours go to 0.25 mm clearance (coated), so the signal vias through the L6 VBUS pour cost less pour width.
Every fix reports whether it found what it edits (STRICT=1 makes a miss fatal).
Run with KiCad's Python: <kicad python> tools/route_fixes.py <in.kicad_pcb> <out.kicad_pcb>"""
import sys, pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.FromMM; P=lambda x,y: pcbnew.VECTOR2I(mm(x),mm(y))
def near(a,x,y,tol=0.02): return abs(pcbnew.ToMM(a.x)-x)<tol and abs(pcbnew.ToMM(a.y)-y)<tol
def track(net,L,pts,w=0.25):
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        t=pcbnew.PCB_TRACK(b); t.SetStart(P(x0,y0)); t.SetEnd(P(x1,y1)); t.SetWidth(mm(w)); t.SetLayer(L); t.SetNet(net); b.Add(t)
def via(net,x,y):
    v=pcbnew.PCB_VIA(b); v.SetPosition(P(x,y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(net); b.Add(v)
n=0; hits={}
def hit(k): global n; n+=1; hits[k]=hits.get(k,0)+1
TR=list(b.GetTracks())   # snapshot: KiCad 10 can't iterate Tracks() again after an Add
# --- SH9 at U7 (pads from the footprint, so a placement shift is followed)
u7=b.FindFootprintByReference('U7'); rs=b.FindFootprintByReference('RS9')
pd={p.GetNumber():p for p in u7.Pads()}; rp={p.GetNumber():p for p in rs.Pads()}
p1=pcbnew.ToMM(pd['1'].GetPosition()); p23=[pcbnew.ToMM(pd[k].GetPosition()) for k in ('2','3')]; r2=pcbnew.ToMM(rp['2'].GetPosition())
SHN=pd['1'].GetNet(); SHP=pd['2'].GetNet()
top=p1[1]-0.75   # pad tip
# SH9_N F.Cu copper above the pins (y < pin tip, within 1.5 mm) and its via there go
oldv=None
for t in TR:
    if t.GetNetCode()!=SHN.GetNetCode(): continue
    if t.GetClass()=='PCB_VIA':
        x,y=pcbnew.ToMM(t.GetPosition())
        if abs(x-p23[0][0])<1.0 and top-1.6<y<top: oldv=(x,y); b.Remove(t); hit('sh9')
    elif t.GetLayer()==pcbnew.F_Cu:
        ys=[pcbnew.ToMM(t.GetStart())[1],pcbnew.ToMM(t.GetEnd())[1]]; xs=[pcbnew.ToMM(t.GetStart())[0],pcbnew.ToMM(t.GetEnd())[0]]
        if min(xs)>p23[0][0]-1.2 and max(xs)<p23[1][0]+1.2 and max(ys)<=top+0.05 and min(ys)>top-1.6: b.Remove(t); hit('sh9')
assert oldv, 'SH9_N via above U7 not found'
vx,vy=p1[0]+0.75,oldv[1]-0.1
track(SHN,pcbnew.In2_Cu,[oldv,(vx,vy)]); via(SHN,vx,vy); track(SHN,pcbnew.F_Cu,[(vx,vy),(p1[0],vy+0.75),(p1[0],top+0.2)])
xm=(p23[0][0]+p23[1][0])/2   # between pins 2 and 3: the 0.25 mm track overlaps both
track(SHP,pcbnew.F_Cu,[r2,(r2[0]+1.4,r2[1]),(xm,r2[1]+(xm-r2[0]-1.4)),(xm,top+0.2)])
# --- U8 GND stub next to EN_A
for t in TR:
    if t.GetClass()!='PCB_VIA' and t.GetNetname()=='GND' and near(t.GetStart(),168.05,152.15) and near(t.GetEnd(),169.02,152.02):
        t.SetEnd(P(168.15,152.02)); hit('u8')
# --- RUN_A via 1.41 mm from the SH_N diagonal on In2 (E-stop 1.5 mm; raster error on a 45-degree track): the via moves
# onto the end of its B.Cu run, 1.70 mm clear, and the In3 run starts there
for t in TR:
    if t.GetNetname()!='/RUN_A': continue
    if t.GetClass()=='PCB_VIA' and near(t.GetPosition(),156.55,133.35): t.SetPosition(P(156.35,133.55)); hit('run_a_via')
    elif t.GetClass()!='PCB_VIA' and t.GetLayer()==pcbnew.B_Cu and near(t.GetStart(),156.35,133.55) and near(t.GetEnd(),156.55,133.35):
        b.Remove(t); hit('run_a_b')
    elif t.GetClass()!='PCB_VIA' and t.GetLayer()==pcbnew.In3_Cu and near(t.GetStart(),156.55,133.35): t.SetStart(P(156.35,133.55)); hit('run_a_in3')
# --- the one-layer GATE via (the stub end the router left)
for t in TR:
    if t.GetClass()=='PCB_VIA' and t.GetNetname()=='/GATE' and near(t.GetPosition(),132.0,161.46): b.Remove(t); hit('gate')
# --- VBUS pours at 0.25 mm clearance (coated: 0.2 mm domain rule; E-stop and fine-pitch rules still apply through the
# .kicad_dru): each signal via stages 3-5 put through the L6 VBUS pour clears a 1.1 mm hole at 0.25 (0.6 mm via plus
# 0.25 each side) against 1.8 mm at 0.6
for z in b.Zones():
    if z.GetNetname()=='/VBUS': z.SetLocalClearance(mm(0.25)); hit('vbus')
need={'sh9':2,'u8':1,'run_a_via':1,'run_a_b':1,'run_a_in3':1,'gate':1,'vbus':1}
short={k:hits.get(k,0) for k,m in need.items() if hits.get(k,0)<m}
# U8's and RUN_A's fixes were written for the placement before U8's block was turned (tools/u8_block.py): on a rebuild
# they find nothing, and the blocks stage re-lays that copper anyway. So a fix with nothing to edit is reported, and is
# fatal only with STRICT=1 (tools/verify_board.sh at the end of the build is what decides).
if short: print('route_fixes: fixes that found nothing to edit (superseded by the designed blocks, or the routing moved):',short)
assert not (short and __import__('os').environ.get('STRICT')=='1'), short
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('route_fixes: edits',n)
