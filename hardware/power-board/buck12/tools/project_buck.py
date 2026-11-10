"""project_buck.py: write ../layout/marengo_buck12.kicad_pro, the buck board's project file (plain Python): the schematic
project (../marengo_buck12.kicad_pro) with the main board's board settings (design rules: 0.2 mm track and space, 0.6/0.3 mm
vias, 0.5 mm to the edge, the same DRC severities) and one net class, Default 0.2/0.2: no E-stop or 54 V-to-E-stop rule
applies here (no E-stop net crosses to this board), and the coated board's 0.2 mm covers the 54 V input."""
import json,os
H=os.path.dirname(os.path.abspath(__file__)); PB=os.path.join(H,'..','..')
sch=json.load(open(os.path.join(H,'..','marengo_buck12.kicad_pro')))
main=json.load(open(os.path.join(PB,'layout','marengo_pdu_revb.kicad_pro')))
sch['board']=main['board']
# U1's stock footprint (Texas_RGY ..._ThermalVias) has 0.2 mm thermal vias in its exposed pad: the one drill under 0.3 mm on
# this board (JLC's 6-layer minimum is 0.15 mm); they sit in a pad, so they are filled and capped like the main board's
sch['board']['design_settings']['rules']['min_through_hole_diameter']=0.2
ns=sch['net_settings']; ns['classes']=[main['net_settings']['classes'][0]]; ns['netclass_patterns']=[]; ns['netclass_assignments']=None
os.makedirs(os.path.join(H,'..','layout'),exist_ok=True)
json.dump(sch,open(os.path.join(H,'..','layout','marengo_buck12.kicad_pro'),'w',newline='\n'),indent=2)
print('wrote layout/marengo_buck12.kicad_pro')
