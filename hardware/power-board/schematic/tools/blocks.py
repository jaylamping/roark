"""blocks.py: what the designed blocks share (tools/port_template.py + port_copper.py, tools/u8_block.py): placing a
footprint by its courtyard centre and pad 1, and making a locked 0.6/0.3 mm via or a track. KiCad Python, page mm."""
import math
import pcbnew, stack
IU,MM=pcbnew.FromMM,pcbnew.ToMM
CU=stack.kicad_layers(pcbnew)
def V(p): return pcbnew.VECTOR2I(IU(p[0]),IU(p[1]))
def place_fp(fp,c,p1,tol=0.06):
    """put the footprint with its courtyard centre at c, turned (0/90/180/270) so that pad 1 lies at p1 (None: as it is);
    stops if no turn brings pad 1 within tol mm"""
    def centre():
        fp.SetPosition(V(c)); bb=fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetCenter(); fp.Move(pcbnew.VECTOR2I(IU(c[0])-bb.x,IU(c[1])-bb.y))
    if p1 is None: centre(); return
    best=None
    for rot in (0,90,180,270):
        fp.SetOrientationDegrees(rot); centre()
        q=next(p for p in fp.Pads() if p.GetNumber()=='1').GetPosition(); d=math.hypot(MM(q.x)-p1[0],MM(q.y)-p1[1])
        if best is None or d<best[0]: best=(d,rot)
    fp.SetOrientationDegrees(best[1]); centre()
    assert best[0]<tol,(fp.GetReference(),best)
def make(b,p,nets=None):
    """a primitive ('v', net, (x,y)) or ('t', net, layer id, a, c, width) as a new, not yet added, via or track. nets: a
    {name: NETINFO_ITEM} map read before any Remove/Add (KiCad 10's FindNet can go wrong after them)"""
    ni=nets[p[1]] if nets else b.FindNet(p[1])
    assert ni,p[1]
    if p[0]=='v':
        v=pcbnew.PCB_VIA(b); v.SetPosition(V(p[2])); v.SetWidth(IU(.6)); v.SetDrill(IU(.3)); v.SetNet(ni)
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(CU[0],CU[5]); return v
    t=pcbnew.PCB_TRACK(b); t.SetStart(V(p[3])); t.SetEnd(V(p[4])); t.SetWidth(IU(p[5])); t.SetLayer(p[2]); t.SetNet(ni); return t
def key(t):
    """a board track or via in the primitives' form, rounded to 1 um; a track's ends in sorted order"""
    r=lambda p:(round(MM(p.x),3),round(MM(p.y),3))
    if t.GetClass()=='PCB_VIA': return ('v',t.GetNetname(),r(t.GetPosition()))
    return ('t',t.GetNetname(),t.GetLayer())+tuple(sorted((r(t.GetStart()),r(t.GetEnd()))))+(round(MM(t.GetWidth()),3),)
def pkey(p):
    r=lambda q:(round(q[0],3),round(q[1],3))
    return ('v',p[1],r(p[2])) if p[0]=='v' else ('t',p[1],p[2])+tuple(sorted((r(p[3]),r(p[4]))))+(round(p[5],3),)
