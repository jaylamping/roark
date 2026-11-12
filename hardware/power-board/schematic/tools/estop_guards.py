"""estop_guards.py in.kicad_pcb out.kicad_pcb (KiCad Python): the F.Cu "no copper pour" guards round E-stop pads.
A guard is a rule area 1.6 mm round the pad's bounding box, named ESTOP_GUARD_<ref>_<pad>, for every E-stop pad
(tools/domains.py) that has a 54 V pour outline within 1.5 mm on F.Cu. It keeps the pour 1.5 mm off the pad even when
the zones are filled without the project's .kicad_dru (pcbnew's ZONE_FILLER in the tools; kicad-cli's fill applies the
estop_to_54v rule by itself). The guards are generated from the footprints' pads, so a moved part takes its guard with
it: this script removes every ESTOP_GUARD_* area and writes the set for the board as it is. tools/hv_spacing.py calls
build() on a new board; tools/route_checks.py check 9 fails when the board's guards differ from expected()."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, domains
mm=pcbnew.FromMM; L=pcbnew.F_Cu; G=1.6
def expected(b):
    """{guard name: (x0, y0, x1, y1) in internal units} for the board's present pads and 54 V pour outlines"""
    hv=[z for z in b.Zones() if not z.GetIsRuleArea() and z.IsOnLayer(L) and domains.is_hv(z.GetNetname())]
    out={}
    for p in b.GetPads():
        if not domains.is_estop(p.GetNetname()) or not p.IsOnLayer(L): continue
        s=p.GetEffectiveShape(L)
        if any(z.Outline().Collide(s,mm(1.5)-1) for z in hv):
            pb=p.GetBoundingBox(); g=mm(G)
            out[f'ESTOP_GUARD_{p.GetParentFootprint().GetReference()}_{p.GetNumber()}']=(pb.GetLeft()-g,pb.GetTop()-g,pb.GetRight()+g,pb.GetBottom()+g)
    return out
def existing(b):
    out={}
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetZoneName().startswith('ESTOP_GUARD_'):
            bb=z.GetBoundingBox(); out.setdefault(z.GetZoneName(),[]).append((bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()))
    return out
def diff(b,tol=mm(0.02)):
    """(missing or misplaced guard names, stale guard names): empty lists when the board's guards are the expected set"""
    want,have=expected(b),existing(b)
    wrong=[n for n,r in want.items() if len(have.get(n,[]))!=1 or any(abs(a-c)>tol for a,c in zip(have[n][0],r))]
    return sorted(wrong),sorted(n for n in have if n not in want)
def build(b):
    want=expected(b)   # read before the first Remove
    old=[z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('ESTOP_GUARD_')]
    for z in old: b.Remove(z)
    for name,(x0,y0,x1,y1) in sorted(want.items()):
        k=pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetDoNotAllowZoneFills(True); k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False)
        k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False); k.SetLayer(L); k.SetZoneName(name)
        o=k.Outline(); o.NewOutline()
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)): o.Append(pcbnew.VECTOR2I(x,y))
        b.Add(k)
    return len(old),sorted(want)
if __name__=='__main__':
    b=pcbnew.LoadBoard(sys.argv[1]); print('before: wrong or missing',*diff(b)[0:1],'stale',diff(b)[1])
    n,names=build(b); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
    print('removed',n,'guards; wrote',len(names),names)
