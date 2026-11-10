"""pour_width.py board.kicad_pcb [board2 ...] (KiCad Python): narrowest copper cross-section of the 60 A pours, measured
on the filled zone polygons (not the outlines), and the temperature rise it gives.
For each cut line across the current's direction, every 0.25 mm along the path, the filled width of the net on each
copper layer (a 0.02 mm strip of the fill cut out and measured exactly; via barrels are not counted). The rise at a cut
is IPC-2221B's, I = 0.048 * dT^0.44 * A^0.725 (A in mil^2, external conductor), with all the layers at the cut lumped
into one external conductor: the outer layers' cross-section in full and the inner layers' multiplied by 0.384, which
puts an inner layer by itself on IPC's internal curve (k = 0.024). Lumping is the cautious choice for stacked layers:
they heat each other, so they are not taken as separate conductors that each shed their own heat.
Copper thickness from tools/stack.py (2 oz outer = 70 um, 0.5 oz inner = 17.5 um). The cut with the highest rise is
reported per path, with its width per layer and the 2 oz outer width that would give the same rise.
  VBUS stem, bank B to the ports: cuts Y = 178..231.4 (page mm) over X 136..164. The worst case is the last two ports
        loaded (30 A each), so the stem carries 60 A down to port 5's tap (Y 222) and 30 A from there to port 6's (Y 231.4).
        The cuts run through the port templates' via rows (Y 190.9 on), where signal vias perforate the sheet.
  The four bank FETs' source-pin columns (pins 5-7 on F.Cu, pins 2-3 through vias on the B.Cu mirror), 30 A each: MID
        below Q8 and Q9 (Y 149..149.75, past the last pin), VBUS below Q1 and Q2 (Y 169..169.75). They are separate conductors 13 mm apart,
        so each is taken by itself (an earlier version measured the cut at Y 150.0, on the pour's outline, and reported
        the two MID columns together as a "21.1 mm MID band").
  MID band between the two FET rows: cuts Y = 150.25..158 over X 130..170, 60 A.
Also counted: vias of other nets in the VBUS band X 130-160, Y 180-190 (tools/finish_route.py puts no new ones there).
Exit 1 when a path's rise is over its limit (RISE_MAX, degC) or the band holds more than BAND_VIAS_MAX vias.
Boards given together are printed one after the other for a before/after comparison (the exit code is the last one's)."""
import os,sys,pcbnew
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
MIL=0.0254
# (key, net, name, [(y0, y1, amps), ...], x0, x1)
PATHS=[('stem','/VBUS','VBUS stem Y 178-231.4',[(178.0,222.0,60.0),(222.0,231.4,30.0)],136.0,164.0),
       ('vq1','/VBUS','VBUS at Q1 source pins',[(169.0,169.75,30.0)],131.0,138.5),
       ('vq2','/VBUS','VBUS at Q2 source pins',[(169.0,169.75,30.0)],150.0,156.5),
       ('mq8','/MID','MID at Q8 source pins',[(149.0,149.75,30.0)],131.0,138.5),
       ('mq9','/MID','MID at Q9 source pins',[(149.0,149.75,30.0)],150.0,156.5),
       ('mid','/MID','MID band Y 150.25-158',[(150.25,158.0,60.0)],130.0,170.0)]
# Limits, degC. 20 is the rating's target and 25 the most this board accepts (LAYOUT_RULES, "Board").
RISE_MAX={'stem':41.0,'vq1':25.0,'vq2':25.0,'mq8':25.0,'mq9':25.0,'mid':25.0}
BAND=(130.0,160.0,180.0,190.0); BAND_VIAS_MAX=18
H=0.02
INNER_DERATE=(0.024/0.048)**(1/0.725)   # 0.384: an internal conductor needs 1/0.384 of the external area for the same rise
def area_eq(widths):
    """the cut's copper as one external conductor, mil^2: outer layers in full, inner layers derated to IPC's internal curve"""
    return sum((w/MIL)*(stack.CU_UM[i]/25.4)*(1.0 if i in stack.OUTER else INNER_DERATE) for i,w in widths.items())
def rise(widths,amps):
    a=area_eq(widths)
    return (amps/(0.048*a**0.725))**(1/0.44) if a>0 else float('inf')
def outer_equiv(widths):
    """the width in mm of one 2 oz outer layer with the same rise"""
    return area_eq(widths)*MIL/(stack.CU_UM[0]/25.4)
def measure(path):
    b=pcbnew.LoadBoard(path); KL=stack.kicad_layers(pcbnew); out=[]
    for key,net,name,spans,x0,x1 in PATHS:
        zs=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()==net]
        fills={i:[z.GetFilledPolysList(L) for z in zs if z.IsOnLayer(L)] for i,L in enumerate(KL)}
        worst=None
        for y0,y1,amps in spans:
            y=y0
            while y<=y1+1e-9:
                strip=pcbnew.SHAPE_POLY_SET(); strip.NewOutline()
                for px,py in ((x0,y-H/2),(x1,y-H/2),(x1,y+H/2),(x0,y+H/2)): strip.Append(IU(px),IU(py))
                w={}
                for i,ps in fills.items():
                    a=0.0
                    for p in ps:
                        c=pcbnew.SHAPE_POLY_SET(p); c.BooleanIntersection(strip); a+=c.Area()
                    w[i]=a/IU(1)**2/H
                r=rise(w,amps)
                if worst is None or r>worst[0]: worst=(r,y,amps,w)
                if os.environ.get('PROFILE'): print(f'      {net} Y {y:.2f} {amps:.0f} A: '+', '.join(f'{stack.NAMES[i]} {v:.2f}' for i,v in w.items() if v>0.05)+f'; rise {r:.1f}')
                y+=0.25
        out.append((key,name,worst))
    bx0,bx1,by0,by1=BAND
    nv=sum(1 for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()!='/VBUS'
           and bx0<=MM(t.GetPosition().x)<=bx1 and by0<=MM(t.GetPosition().y)<=by1)
    return out,nv
if __name__=='__main__':
    bad=0
    for p in sys.argv[1:]:
        print(p); res,nv=measure(p); bad=0
        for key,name,(r,y,amps,w) in res:
            lay=', '.join(f'{stack.NAMES[i]} {v:.1f}' for i,v in w.items() if v>0.05)
            ok=r<=RISE_MAX[key]; bad+=not ok
            print(f'   {name}: worst cut Y {y:.2f} at {amps:.0f} A: {lay} mm; as one 2 oz outer layer {outer_equiv(w):.1f} mm; rise {r:.1f} degC (limit {RISE_MAX[key]:.0f}) {"ok" if ok else "FAIL"}')
        ok=nv<=BAND_VIAS_MAX; bad+=not ok
        print(f'   vias of other nets in the VBUS band X {BAND[0]:.0f}-{BAND[1]:.0f}, Y {BAND[2]:.0f}-{BAND[3]:.0f}: {nv} (limit {BAND_VIAS_MAX}) {"ok" if ok else "FAIL"}')
    sys.exit(1 if bad else 0)
