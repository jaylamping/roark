"""plane_clearance.py in.kicad_pcb out.kicad_pcb (KiCad Python): set the zone clearance of the inner GND planes and fills
(In1-In4) to stack.PLANE_CLEAR on an existing board (tools/route_power.py builds new boards with it). Refill with
kicad-cli pcb drc --refill-zones --save-board afterwards."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, stack
b=pcbnew.LoadBoard(sys.argv[1]); KL=stack.kicad_layers(pcbnew); inner={KL[i] for i in range(1,stack.NL-1)}; n=0
for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname()=='GND' and z.GetFirstLayer() in inner:
        z.SetLocalClearance(pcbnew.FromMM(stack.PLANE_CLEAR)); n+=1
b.Save(sys.argv[2]); print('inner GND zones set to',stack.PLANE_CLEAR,'mm:',n)
