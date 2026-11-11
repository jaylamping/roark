"""heatsink_pads.py in.kicad_pcb [out.kicad_pcb] (KiCad Python): the bare heatsink pads on the bottom (THERMAL_OPTION.md
option D, LAYOUT_RULES.md "FET copper and the heatsink"): a solder-mask opening on B.Mask under each power FET's tab,
so the tab's via array ends in bare (OSP) copper against the insulating gap pad.
For each FET in FETS the opening is the 15 x 15 mm square centred on the tab pad, cut down to that FET's own drain copper
on B.Cu pulled in by INSET (0.3 mm) from the copper's edge. So an opening never reaches the edge of its pour, never
uncovers copper of another net (the VBUS sheet, a neighbouring mirror, GND fill, a signal via's hole in the pour), and
the bare copper keeps INSET plus the pour's clearance to everything else, which stays under mask. Where the drain
mirror is smaller than 15 x 15 mm the opening is smaller too; the area of each is printed.
The openings are generated from the filled zones, so they are rebuilt whenever the B.Cu pours change:
  heatsink_pads.py in out      removes every board-level shape on B.Mask and writes the set for the board as it is
  MODE=check heatsink_pads.py in   exit 1 if the board's openings differ from that set (tools/verify_board.sh)
Zones are taken as filled in the file (run after kicad-cli's refill)."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew
IU,MM=pcbnew.FromMM,pcbnew.ToMM
FETS=['Q8','Q9','Q1','Q2','Q15','Q16','Q17','Q18','Q19','Q20']   # bank A, bank B, the six ports
SIDE=15.0; INSET=0.3
AREA_MIN={'Q8':135.0,'Q9':135.0,'Q1':140.0,'Q2':140.0}   # mm2 floors (the board of 2026-11-10 rounded down): a pour change may not quietly shrink a pad
PORT_MIN=105.0
def expected(b):
    """{ref: SHAPE_POLY_SET} of the openings for the board as it is"""
    out={}; zones=[z for z in b.Zones() if not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.B_Cu)]
    for ref in FETS:
        fp=b.FindFootprintByReference(ref)
        tab=max((p for p in fp.Pads() if p.GetNumber()=='4'),key=lambda p:p.GetSize(pcbnew.F_Cu).x*p.GetSize(pcbnew.F_Cu).y)
        net=tab.GetNetname(); c=tab.GetPosition(); h=IU(SIDE/2)
        sq=pcbnew.SHAPE_POLY_SET(); sq.NewOutline()
        for dx,dy in ((-h,-h),(h,-h),(h,h),(-h,h)): sq.Append(c.x+dx,c.y+dy)
        cu=pcbnew.SHAPE_POLY_SET()
        for z in zones:
            if z.GetNetname()==net: cu.BooleanAdd(z.GetFilledPolysList(pcbnew.B_Cu))
        cu.Deflate(IU(INSET),pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS,IU(0.005))
        cu.BooleanIntersection(sq); cu.Simplify()
        # keep the piece under the tab only (the square can also catch a separate lobe of the same net)
        best=None
        for i in range(cu.OutlineCount()):
            one=pcbnew.SHAPE_POLY_SET(); one.AddOutline(cu.Outline(i))
            for k in range(cu.HoleCount(i)): one.AddHole(cu.Hole(i,k))
            if one.Contains(c) or best is None or one.Area()>best.Area():
                if best is None or one.Contains(c) or not best.Contains(c): best=one
        out[ref]=(net,best)
    return out
def existing(b):
    return [d for d in b.GetDrawings() if d.GetClass()=='PCB_SHAPE' and d.GetLayer()==pcbnew.B_Mask]
def area(ps): return ps.Area()/IU(1)**2
def diff(b):
    """refs whose opening is missing or differs by more than 0.05 mm2 in area or symmetric difference; stray shapes"""
    want=expected(b); have=existing(b); used=set(); wrong=[]
    for ref,(net,ps) in want.items():
        hit=None
        for i,d in enumerate(have):
            if i in used: continue
            q=pcbnew.SHAPE_POLY_SET(d.GetPolyShape()); x=pcbnew.SHAPE_POLY_SET(q); x.BooleanXor(ps)
            if area(x)<0.05: hit=i; break
        if hit is None: wrong.append(ref)
        else: used.add(hit)
    return wrong,len(have)-len(used),want
def build(b):
    want=expected(b); old=existing(b)   # read before the first Remove
    for d in old: b.Remove(d)
    for ref,(net,ps) in want.items():
        s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_POLY); q=pcbnew.SHAPE_POLY_SET(ps); q.Fracture(); s.SetPolyShape(q)
        s.SetFilled(True); s.SetWidth(0); s.SetLayer(pcbnew.B_Mask); b.Add(s)
    return len(old),want
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1])
    if os.environ.get('MODE')=='check':
        wrong,stray,want=diff(b); small=[]
        for ref,(net,ps) in want.items():
            a=area(ps); lim=AREA_MIN.get(ref,PORT_MIN)
            if a<lim: small.append((ref,round(a,1),lim))
        print(f'heatsink pads: {len(want)-len(wrong)} of {len(want)} openings on B.Mask as generated; missing or different {wrong}; other B.Mask shapes {stray}; under the area floor {small}')
        sys.exit(1 if wrong or stray or small else 0)
    n,want=build(b)
    for ref,(net,ps) in want.items():
        bb=ps.BBox(); print(f'   {ref} {net}: {area(ps):.0f} mm2 bare, within X {MM(bb.GetLeft()):.1f}..{MM(bb.GetRight()):.1f}, Y {MM(bb.GetTop()):.1f}..{MM(bb.GetBottom()):.1f}')
    b.Save(sys.argv[2]); print('removed',n,'old B.Mask shapes; wrote',len(want))
