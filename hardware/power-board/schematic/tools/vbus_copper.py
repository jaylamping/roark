"""vbus_copper.py in.kicad_pcb out.kicad_pcb (KiCad Python): parallel copper for the VBUS stem (LAYOUT_RULES.md, "Board").
The stem carries 60 A from the bus-cap bar (page Y 170-178) down to the ports on L6 alone, and the port blocks' signal
vias perforate it. This script adds what runs in parallel with it and rebuilds it on every run (zones named VBUS_STEM_*
are removed first; tools/route_power.py calls build() on a new board):
  - VBUS pours on In2 and In3 over the stem (STEM_IN), from the bar's via rows to the last port's via field. They are
    joined to L6 by the VBUS vias that already pass through: the bar's rows and each port's field at its shunt.
  - the L6 stem's outline widened from X 137.2-162.8 to STEM_L6 (X 130.8-169.2, up to 0.6 mm from the ports' drain
    mirrors): the strips beside it were GND fill cut up by the port blocks' vias. This is where most of the gain is:
    0.5 oz inner copper counts for about a tenth of its width.
The pours fill round the signal tracks and vias on their layers with the zone clearance (0.25 mm; 1.5 mm to E-stop
copper by the .kicad_dru when kicad-cli refills). tools/pour_width.py measures what results and holds the floor.
Coordinates: page mm."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
def env(name,default): return tuple(float(x) for x in os.environ.get(name,default).split(','))
STEM_IN=env('STEM_IN','130.8,169.2,170.4,239.6')     # X0, X1, Y0, Y1 of the In2 / In3 pours
STEM_L6=env('STEM_L6','130.8,169.2,178.0,240.0')     # the L6 stem's outline
def rect(z,r):
    o=z.Outline(); o.RemoveAllContours(); o.NewOutline()
    for x,y in ((r[0],r[2]),(r[1],r[2]),(r[1],r[3]),(r[0],r[3])): o.Append(IU(x),IU(y))
def build(b):
    KL=stack.kicad_layers(pcbnew); net=b.FindNet('/VBUS')   # read before the first Remove
    stem=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='/VBUS' and z.IsOnLayer(KL[5]) and z.GetAssignedPriority()==3]
    assert len(stem)==1,len(stem)
    old=[z for z in b.Zones() if z.GetZoneName().startswith('VBUS_STEM_')]
    for z in old: b.Remove(z)
    rect(stem[0],STEM_L6); stem[0].SetZoneName('VBUS_L6_STEM')
    for i in (2,3):
        z=pcbnew.ZONE(b); z.SetLayer(KL[i]); z.SetNet(net); z.SetAssignedPriority(3); z.SetZoneName(f'VBUS_STEM_{stack.NAMES[i]}')
        z.SetLocalClearance(IU(0.25)); z.SetMinThickness(IU(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); rect(z,STEM_IN); b.Add(z)
    return len(old)
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); n=build(b); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
    print('VBUS stem copper: In2 and In3 pours',STEM_IN,'L6 stem',STEM_L6,'(replaced',n,'old zones)')
