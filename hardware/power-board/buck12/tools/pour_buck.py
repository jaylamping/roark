"""pour_buck.py board.kicad_pcb (KiCad Python): the buck board's current paths, cut by cut, with the IPC-2221B temperature
rise at the narrowest cut (the same method as ../../schematic/tools/pour_width.py: the zone fills on each layer cut by a
0.02 mm strip every 0.25 mm, outer 2 oz in full, inner 0.5 oz derated to IPC's internal curve). Fails over RISE_MAX.
Board mm; the board's page origin is ORIGIN."""
import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','schematic','tools'))
import pcbnew, stack
from pour_width import rise, outer_equiv
IU,MM=pcbnew.FromMM,pcbnew.ToMM
O=(30.0,30.0); H=0.02
# (key, net, name, cut axis ('y': cuts are horizontal lines at each Y; 'x': vertical lines at each X), from, to, span lo, span hi, amps, limit degC)
PATHS=[
 ('vout','/VOUT','VOUT, L2 to RS1 (12 A)','x',44.0,51.1,33.0,44.0,12.0,20.0),   # to RS1.1's left edge (X 51.12)
 ('p12','/+12V','+12V, RS1 into the distribution pour (12 A)','x',42.0,49.8,44.0,62.0,12.0,20.0),   # to RS1.4's left edge (X 49.85)
 ('sw','/SW','SW node, Q2 to L2 (12 A)','y',27.6,30.9,33.0,44.0,12.0,20.0),
 ('vin','/VIN','VIN, L1 to the input caps and Q1 (3.5 A at 36 V, 126 W in)','x',22.0,28.5,12.0,40.0,3.5,10.0),
 ('vinp','/VIN_P','VIN_P, J1 to the filter (3.5 A)','y',7.2,10.8,8.0,17.0,3.5,10.0),
 ('jet','/+12V_JET','Jetson output, F1 to J2 (5 A)','y',64.0,76.5,9.0,14.0,5.0,20.0),
 ('pi','/+12V_PI','Pi output, F2 to J3 (5 A)','y',64.0,76.5,19.0,24.0,5.0,20.0),
 ('fan','/+12V_FAN','fan output, F3 to J4 (2 A)','y',64.0,76.5,29.0,34.0,2.0,20.0),
]
def measure(path):
    b=pcbnew.LoadBoard(path); KL=stack.kicad_layers(pcbnew); out=[]; bad=0
    for key,net,name,ax,c0,c1,s0,s1,amps,lim in PATHS:
        zs=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()==net]
        tr=[t for t in b.GetTracks() if t.GetNetname()==net and t.GetClass()=='PCB_TRACK']
        worst=None; c=c0
        while c<=c1+1e-9:
            strip=pcbnew.SHAPE_POLY_SET(); strip.NewOutline()
            pts=((s0,c-H/2),(s1,c-H/2),(s1,c+H/2),(s0,c+H/2)) if ax=='y' else ((c-H/2,s0),(c+H/2,s0),(c+H/2,s1),(c-H/2,s1))
            for px,py in pts:
                if ax=='y': strip.Append(IU(px+O[0]),IU(py+O[1]))
                else: strip.Append(IU(px+O[0]),IU(py+O[1]))
            w={}
            for i,L in enumerate(KL):
                tot=0.0
                for z in zs:
                    if not z.IsOnLayer(L): continue
                    f=pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(L)); f.BooleanIntersection(strip)
                    tot+=MM(MM(f.Area()))/H if f.OutlineCount() else 0.0
                for t in tr:   # tracks of the net crossing the cut count too
                    if t.GetLayer()!=L: continue
                    s=pcbnew.SHAPE_POLY_SET(); t.TransformShapeToPolygon(s,L,0,IU(0.005),pcbnew.ERROR_INSIDE); s.BooleanIntersection(strip)
                    tot+=MM(MM(s.Area()))/H if s.OutlineCount() else 0.0
                if tot>0.01: w[i]=tot
            r=rise(w,amps)
            if worst is None or r>worst[0]: worst=(r,c,w)
            c+=0.25
        r,c,w=worst; ok=r<=lim; bad+=not ok
        lay=', '.join(f'{stack.NAMES[i]} {v:.1f}' for i,v in w.items())
        print(f'   {name}: worst cut {ax.upper()} {c:.2f} at {amps:.1f} A: {lay} mm; as one 2 oz outer layer {outer_equiv(w):.1f} mm; rise {r:.1f} degC (limit {lim:.0f}) {"ok" if ok else "FAIL"}')
    return bad
if __name__=='__main__':
    print(sys.argv[1]); bad=measure(sys.argv[1]); print('pour_buck fails',bad); sys.exit(1 if bad else 0)
