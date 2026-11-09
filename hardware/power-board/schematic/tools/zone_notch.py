"""zone_notch.py in.kicad_pcb out.kicad_pcb NET X0 Y0 X1 Y1 [LAYER,...] (KiCad Python, page mm): cut a rectangular
notch out of the outline of NET's zones (on the listed layers, default all) and refill. Used to pull the MID pour back
from U8's controller pins so its E-stop pins can escape (Joey, 2026-11-09: up to 1.5 mm, next to the controller pins
only). Prints each zone's outline area and its narrowest vertical and horizontal section through the notch's band
before and after."""
import sys,pcbnew
F,I=pcbnew.FromMM,pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1]); net=sys.argv[3]; x0,y0,x1,y1=map(float,sys.argv[4:8]); LS=set(sys.argv[8].split(',')) if len(sys.argv)>8 else None
cut=pcbnew.SHAPE_POLY_SET(); r=pcbnew.SHAPE_LINE_CHAIN()
for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)): r.Append(F(x),F(y))
r.SetClosed(True); cut.AddOutline(r)
def section(ps,horizontal,c,lo,hi):
    """copper length along a line (y=c if horizontal else x=c) inside the polygon set, sampled at 0.05 mm"""
    n=0; v=lo
    while v<=hi:
        p=pcbnew.VECTOR2I(F(v),F(c)) if horizontal else pcbnew.VECTOR2I(F(c),F(v))
        n+=ps.Contains(p); v+=.05
    return round(n*.05,2)
for z in b.Zones():
    if z.GetNetname()!=net or z.GetIsRuleArea(): continue
    L=b.GetLayerName(z.GetFirstLayer())
    if LS and L not in LS: continue
    o=z.Outline(); bb=o.BBox(); bx0,by0,bx1,by1=I(bb.GetLeft()),I(bb.GetTop()),I(bb.GetRight()),I(bb.GetBottom())
    if not bb.Intersects(cut.BBox()): continue
    before=[min(section(o,True,y,bx0,bx1) for y in (y0+.1,(y0+y1)/2,y1-.1)), min(section(o,False,x,by0,by1) for x in (x0+.05,(x0+x1)/2,x1-.05))]
    a0=o.Area()
    o.BooleanSubtract(cut)
    after=[min(section(o,True,y,bx0,bx1) for y in (y0+.1,(y0+y1)/2,y1-.1)), min(section(o,False,x,by0,by1) for x in (x0+.05,(x0+x1)/2,x1-.05))]
    print(f'{net} {L}: outline area {I(I(a0)):.1f} -> {I(I(o.Area())):.1f} mm2; section across the notch rows (horizontal) {before[0]} -> {after[0]} mm, along its columns (vertical) {before[1]} -> {after[1]} mm')
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
