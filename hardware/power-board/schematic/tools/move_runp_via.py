"""move_runp_via.py in.kicad_pcb out.kicad_pcb (KiCad Python): take the RUN_P feed out of the L6 VBUS pour
(route_checks check 5). Removes the RUN_P via at page (145.25, 187.35), which sits inside the B.Cu VBUS zone outline,
its In3 run back to the via at (129.55, 181.65), and its F.Cu stub to R85 pad 1, so finish_route.py can join R85 to the
(129.55, 181.65) via on F.Cu (no via inside a 54 V zone for an E-stop net). Unlocked copper only."""
import sys,pcbnew
F,I=pcbnew.FromMM,pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1]); tr=[t for t in b.GetTracks() if t.GetNetname()=='/RUN_P']
def at(p,x,y): return abs(I(p.x)-x)<.01 and abs(I(p.y)-y)<.01
kill=[t for t in tr if t.GetClass()=='PCB_VIA' and at(t.GetPosition(),145.25,187.35)]
kill+=[t for t in tr if t.GetClass()!='PCB_VIA' and t.GetLayer()==pcbnew.In3_Cu]
STUB=[(145.25,187.35),(145.45,187.35),(145.55,187.45),(145.65,187.45),(146.1,187.88)]
kill+=[t for t in tr if t.GetClass()!='PCB_VIA' and t.GetLayer()==pcbnew.F_Cu and any(at(t.GetStart(),*STUB[i]) and at(t.GetEnd(),*STUB[i+1]) or at(t.GetEnd(),*STUB[i]) and at(t.GetStart(),*STUB[i+1]) for i in range(4))]
assert not any(t.IsLocked() for t in kill)
print('removed',len(kill),'vias',sum(t.GetClass()=='PCB_VIA' for t in kill))
for t in kill: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
