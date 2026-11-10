"""spacing_buck.py board.kicad_pcb (KiCad Python): the buck board's one cross-board safety rule. SP_EN (J1 pin 9) is an
E-stop-class net on the main board (../../schematic/tools/domains.py): about 3 MOhm of leakage from 54 V into it turns
SPARE_SW on during an E-stop, so here too it keeps 1.5 mm, on every layer, to the copper at or switching up to 54 V:
VIN_P, VIN, VIN_C, SW, HO, BST, BST_R, ILIM (on SW through 402R) and EN / ON_N (on VIN through 300k / 220k).
Also: no other net of the main board's E-stop class is on this board. Exit 1 on a pair closer than 1.5 mm."""
import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','schematic','tools'))
import pcbnew, stack, domains
IU,MM=pcbnew.FromMM,pcbnew.ToMM
HV={'/VIN_P','/VIN','/VIN_C','/SW','/HO','/BST','/BST_R','/ILIM','/EN','/ON_N'}
b=pcbnew.LoadBoard(sys.argv[1]); KL=stack.kicad_layers(pcbnew)
nets={str(n) for n in b.GetNetsByName().keys()}
estop=sorted(n for n in nets if domains.is_estop(n))
items={}   # layer -> [(net, label, shape)]
for t in b.GetTracks():
    for L in KL:
        if t.IsOnLayer(L): items.setdefault(L,[]).append((t.GetNetname(),'via' if t.GetClass()=='PCB_VIA' else 'track',t.GetEffectiveShape(L)))
for p in b.GetPads():
    for L in KL:
        if p.IsOnLayer(L): items.setdefault(L,[]).append((p.GetNetname(),p.GetParentFootprint().GetReference()+'.'+p.GetNumber(),p.GetEffectiveShape(L)))
for z in b.Zones():
    if z.GetIsRuleArea(): continue
    for L in KL:
        if z.IsOnLayer(L) and z.GetNetname() in HV|set(estop):
            items.setdefault(L,[]).append((z.GetNetname(),'zone '+z.GetZoneName(),pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(L))))
bad=[]
for L,its in items.items():
    es=[i for i in its if i[0] in estop]; hv=[i for i in its if i[0] in HV]
    for n,lab,s in es:
        for m,lab2,s2 in hv:
            if s.Collide(s2,IU(1.5-0.001)) if hasattr(s,'Collide') else False: bad.append((b.GetLayerName(L),n,lab,m,lab2))
print('E-stop-class nets on the buck board:',estop,'(SP_EN only is expected)')
print('SP_EN within 1.5 mm of 54 V copper:',len(bad))
for r in bad[:30]: print('   ',r)
sys.exit(1 if bad or set(estop)-{'/SP_EN'} else 0)
