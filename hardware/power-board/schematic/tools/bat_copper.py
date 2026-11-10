"""bat_copper.py in.kicad_pcb out.kicad_pcb (KiCad Python): a BAT mirror on L6 under the pack pad's run to RS1.
The BAT pour is on L1 alone, 26.6 mm at its narrowest cut for 60 A (21.7 degC by tools/pour_width.py, target 20). This
adds a BAT pour on B.Cu under the western part of it (MIRROR, page mm), from the pack pad J1.1 (a plated hole, joined
solid on every layer) to a grid of BAT vias just north of RS1's BAT pad (GRID: wherever tools/finish_route.py's Router
finds a via legal, so inner-layer tracks passing below are left alone). The pack's GND pad J1.2 and the GND fill round
it on L6 are east of the mirror and are not touched. Rebuilt on every run: the zone named BAT_L6_MIRROR and the vias
this script laid (locked BAT vias inside GRID) are removed first. tools/route_power.py's board gets it from
tools/build_board.sh's finish stage."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, stack, finish_route as FR
IU,MM=pcbnew.FromMM,pcbnew.ToMM
MIRROR=(147.2,158.4,100.4,125.6)       # X0, X1, Y0, Y1 of the L6 pour
GRID=(148.2,157.6,119.0,122.2,1.8,1.6) # X0, X1, Y0, Y1, pitch along X, row pitch: the via grid north of RS1.1. Alternate rows are
                                       # offset by half a pitch and the holes keep 0.6 mm of GND plane between them (at 1.0 mm they merge into a slot)
def ingrid(p): return GRID[0]-.01<=MM(p.x)<=GRID[1]+.01 and GRID[2]-.01<=MM(p.y)<=GRID[3]+.01
if __name__=='__main__':
    r=FR.Router(sys.argv[1]); b=r.b; KL=stack.kicad_layers(pcbnew); net=b.FindNet('/BAT')
    old=[z for z in b.Zones() if z.GetZoneName()=='BAT_L6_MIRROR']+[t for t in r.tracks if t.GetClass()=='PCB_VIA' and t.GetNetname()=='/BAT' and t.IsLocked() and ingrid(t.GetPosition())]
    pts=[]; y=GRID[2]; row=0
    while y<=GRID[3]+1e-9:
        x=GRID[0]+(GRID[4]/2 if row%2 else 0)
        while x<=GRID[1]+1e-9:
            if r.via('/BAT',(round(x,3),round(y,3))): pts.append((round(x,3),round(y,3)))
            x+=GRID[4]
        y+=GRID[5]; row+=1
    z=pcbnew.ZONE(b); z.SetLayer(KL[5]); z.SetNet(net); z.SetAssignedPriority(5); z.SetZoneName('BAT_L6_MIRROR')
    z.SetLocalClearance(IU(0.6)); z.SetMinThickness(IU(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); o=z.Outline(); o.NewOutline()
    for px,py in ((MIRROR[0],MIRROR[2]),(MIRROR[1],MIRROR[2]),(MIRROR[1],MIRROR[3]),(MIRROR[0],MIRROR[3])): o.Append(IU(px),IU(py))
    new=[]
    for p in pts:
        v=pcbnew.PCB_VIA(b); v.SetPosition(FR.V(p)); v.SetWidth(IU(.6)); v.SetDrill(IU(.3)); v.SetNet(net)
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(KL[0],KL[5]); v.SetLocked(True); new.append(v)
    for t in old: b.Remove(t)
    b.Add(z)
    for v in new: b.Add(v)
    r.save(sys.argv[2]); print('BAT L6 mirror',MIRROR,'with',len(new),'vias north of RS1 (replaced',len(old),'old items)')
