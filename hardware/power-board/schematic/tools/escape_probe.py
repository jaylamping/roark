"""escape_probe.py board.kicad_pcb NET PX PY [R] (KiCad Python, page mm): for a pad whose escape is blocked, list via
spots within R mm (default 2.5) of (PX, PY) that are blocked only by rippable copper (unlocked tracks and vias of
signal nets: not GND, Kelvin, gate drive or 54 V), with a clear F.Cu stub from the pad, ranked by how many items would
have to go. Writes the best spot's blocker uuids to stdout as RIP=<uuid,...> for rip_uuids.py. Nothing is changed."""
import sys,os,math,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import finish_route as FR, pcbnew, domains
r=FR.Router(sys.argv[1]); r.collect_all=True; n=sys.argv[2]; px,py=float(sys.argv[3]),float(sys.argv[4]); R=float(sys.argv[5]) if len(sys.argv)>5 else 2.5
KEEP=re.compile(r'^(GND|/SH|/G\d|/GC_|/GPU_|/GPD_|/G_L)')
byuid={FR.UID(t):t for t in r.tracks}
def rippable(k):
    kind,net,uid=k[0],k[1],k[2]
    t=byuid.get(uid)
    return kind in ('track','via') and t is not None and not t.IsLocked() and not KEEP.match(net) and not domains.is_hv(net)
best=[]
for i in range(-int(R*10),int(R*10)+1,2):
    for j in range(-int(R*10),int(R*10)+1,2):
        p=(round(px+i/10,2),round(py+j/10,2)); d=math.dist(p,(px,py))
        if d>R or d<.5: continue
        if not r.inside(p) or (130<=p[0]<=160 and 180<=p[1]<=190) or r.in_latch(n,(p[0]-.3,p[1]-.3,p[0]+.3,p[1]+.3)): continue
        dg=set(); sh=pcbnew.SHAPE_CIRCLE(FR.V(p),FR.IU(.3))
        for L in FR.CU: r.free(n,L,sh,via=True,diagnostics=dg)
        if len(dg)>12: continue
        seg=pcbnew.SHAPE_SEGMENT(FR.V((px,py)),FR.V(p),FR.IU(r.width(n)))
        r.free(n,FR.CU[0],seg,diagnostics=dg)
        if all(rippable(k) for k in dg):
            best.append((len(dg),round(d,2),p,sorted({k[1] for k in dg}),[k[2] for k in dg]))
best.sort(key=lambda x:(x[0],x[1]))
print(n,'spots blocked only by rippable copper:',len(best))
for b in best[:6]: print('  items',b[0],'dist',b[1],'at',b[2],'nets',b[3])
if best: print('RIP='+','.join(best[0][4]))
