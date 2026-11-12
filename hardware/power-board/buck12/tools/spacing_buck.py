"""spacing_buck.py board.kicad_pcb (KiCad Python): the buck board's one cross-board safety rule. SP_EN (J1 pin 9) is an
E-stop-class net on the main board (../../schematic/tools/domains.py): about 3 MOhm of leakage from 54 V into it turns
SPARE_SW on during an E-stop, so here too it keeps its distance, on every layer, to the copper at or switching up to 54 V
(tools/hv_buck.py HV). The rule is 1.5 mm; this board keeps hv_buck.SP_MIN (1.7 mm: the rule plus etch tolerance) and
prints the closest pair. Also: no other net of the main board's E-stop class is on this board.
Exit 1 on a pair under SP_MIN, and when the check had nothing to check: no E-stop net, no 54 V copper, a layer with
SP_EN copper but no 54 V copper to compare is fine, but zero pairs compared over the whole board, or a shape without a
distance test, fails."""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'..','..','schematic','tools')); sys.path.insert(0,HERE)
import pcbnew, stack, domains, hv_buck
IU,MM=pcbnew.FromMM,pcbnew.ToMM
HV=set(hv_buck.HV)
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
def gap(s,s2,hi=3.0):
    """distance between two shapes to 0.005 mm (bisection on Collide), or hi when they are farther apart"""
    if not s.Collide(s2,IU(hi)): return hi
    lo=0.0
    while hi-lo>0.005:
        m=(lo+hi)/2
        if s.Collide(s2,IU(m)): hi=m
        else: lo=m
    return hi
bad=[]; nohit=[]; pairs=0; closest=(9e9,None)
for L,its in items.items():
    es=[i for i in its if i[0] in estop]; hv=[i for i in its if i[0] in HV]
    for n,lab,s in es:
        for m,lab2,s2 in hv:
            if not hasattr(s,'Collide'): nohit.append(lab); continue
            pairs+=1; d=gap(s,s2)
            if d<closest[0]: closest=(d,(b.GetLayerName(L),lab,m,lab2))
            if d<hv_buck.SP_MIN: bad.append((round(d,3),b.GetLayerName(L),n,lab,m,lab2))
hvn=sorted(n for n in HV if n in nets)
print('E-stop-class nets on the buck board:',estop,'(SP_EN only is expected)')
print(f'54 V nets on the board: {len(hvn)} of {len(HV)}; SP_EN to 54 V copper: {pairs} pairs compared on {len(items)} layers')
if closest[1]: print(f'closest: {closest[0]:.3f} mm, {closest[1]}')
print(f'SP_EN within {hv_buck.SP_MIN} mm of 54 V copper: {len(bad)} (rule {hv_buck.SP_RULE} mm, kept {hv_buck.SP_MIN} mm)')
for r in sorted(bad)[:30]: print('   ',r)
fail=[]
if set(estop)-{'/SP_EN'}: fail.append('an E-stop net other than SP_EN')
if '/SP_EN' not in estop: fail.append('no SP_EN on the board: nothing was checked')
if not hvn: fail.append('no 54 V net on the board: nothing was checked')
if not pairs: fail.append('no pair compared: nothing was checked')
if nohit: fail.append(f'{len(nohit)} shapes without a distance test')
for f in fail: print('FAIL:',f)
sys.exit(1 if bad or fail else 0)
