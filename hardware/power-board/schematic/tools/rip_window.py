"""rip_window.py in.kicad_pcb out.kicad_pcb X0 Y0 X1 Y1 [LAYERS] (KiCad Python, page mm): remove the unlocked tracks
and vias of signal nets that touch the window, to make room for a blocked connection (rip-up and re-route). GND,
Kelvin (/SH*), gate drive (/G*, /GC_*, /GPU_*, /GPD_*) and 54 V nets are kept. LAYERS: comma list such as
In2.Cu,In3.Cu (default: all copper). The cut tracks' remaining stubs stay as anchors for finish_route.py, which then
routes the blocked connection first and the ripped ones after; tools/rrr.sh runs the whole trial."""
import sys,re,pcbnew
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__))); import domains
F=pcbnew.FromMM
b=pcbnew.LoadBoard(sys.argv[1]); x0,y0,x1,y1=map(float,sys.argv[3:7])
LS=set(sys.argv[7].split(',')) if len(sys.argv)>7 else None
W=pcbnew.BOX2I(pcbnew.VECTOR2I(F(x0),F(y0)),pcbnew.VECTOR2L(F(x1-x0),F(y1-y0)))
KEEP=re.compile(r'^(GND|/SH|/G\d|/GC_|/GPU_|/GPD_|/G_L)')
kill=[]
for t in list(b.GetTracks()):
    n=t.GetNetname()
    if t.IsLocked() or KEEP.match(n) or domains.is_hv(n) or not t.GetBoundingBox().Intersects(W): continue
    if t.GetClass()!='PCB_VIA':
        if LS and b.GetLayerName(t.GetLayer()) not in LS: continue
        if not t.GetEffectiveShape().Collide(pcbnew.SHAPE_RECT(W),0): continue
    kill.append(t)
from collections import Counter
print('ripped',dict(Counter(t.GetNetname() for t in kill)))
for t in kill: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
