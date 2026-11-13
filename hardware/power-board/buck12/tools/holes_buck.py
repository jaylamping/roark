"""holes_buck.py board.kicad_pcb (KiCad Python): the M3 holes are not bonded to the frame, so no copper may sit where the
screw head, washer or standoff lands. For every mounting hole (H*): a copper keep-out (rule area, every copper layer, no
tracks, vias or fills) holds a circle of tools/place_buck.py KO_R round it, and no copper of any kind (track, via, pad,
zone fill) is inside that circle on any layer. Exit 1 on a hole without its keep-out, copper inside, or no hole found."""
import os,sys,math
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'..','..','schematic','tools'))
import pcbnew, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
KO_R=float(next(l.split('=')[1].split('#')[0] for l in open(os.path.join(HERE,'place_buck.py'),encoding='utf-8') if l.startswith('KO_R=')))
b=pcbnew.LoadBoard(sys.argv[1]); KL=stack.kicad_layers(pcbnew)
holes=[f for f in b.GetFootprints() if f.GetReference().startswith('H') and f.GetReference()[1:].isdigit()]
KO=[z for z in b.Zones() if z.GetIsRuleArea()]
bad=[]
for h in holes:
    c=h.GetPosition(); ref=h.GetReference(); circ=pcbnew.SHAPE_CIRCLE(c,IU(KO_R-0.01))
    ring=[pcbnew.VECTOR2I(int(c.x+IU(KO_R-0.01)*math.cos(a*math.pi/8)),int(c.y+IU(KO_R-0.01)*math.sin(a*math.pi/8))) for a in range(16)]+[c]
    ok=[z for z in KO if z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowZoneFills()
        and all(z.IsOnLayer(L) for L in KL) and all(z.Outline().Contains(p) for p in ring)]
    if not ok: bad.append(f'{ref}: no copper keep-out on every layer holding the {KO_R} mm circle')
    found=[]
    for t in b.GetTracks():
        for L in KL:
            if t.IsOnLayer(L) and t.GetEffectiveShape(L).Collide(circ,0): found.append(f'{"via" if t.GetClass()=="PCB_VIA" else "track"} {t.GetNetname()} {b.GetLayerName(L)}')
    for p in b.GetPads():
        if p.GetParentFootprint().GetReference()==ref: continue
        for L in KL:
            if p.IsOnLayer(L) and p.GetEffectiveShape(L).Collide(circ,0): found.append(f'pad {p.GetParentFootprint().GetReference()}.{p.GetNumber()} {b.GetLayerName(L)}')
    for z in b.Zones():
        if z.GetIsRuleArea(): continue
        for L in KL:
            if z.IsOnLayer(L) and pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(L)).Collide(circ,0): found.append(f'fill {z.GetNetname()} {b.GetLayerName(L)}')
    if found: bad.append(f'{ref}: copper inside {KO_R} mm: {sorted(set(found))[:6]}')
    print(f'   {ref} at ({MM(c.x)-30:.1f}, {MM(c.y)-30:.1f}): keep-out {"yes" if ok else "NO"}, copper inside {len(found)}')
if len(holes)!=4: bad.append(f'{len(holes)} mounting holes found, 4 expected')
for r in bad: print('FAIL:',r)
print('holes_buck fails',len(bad)); sys.exit(1 if bad else 0)
