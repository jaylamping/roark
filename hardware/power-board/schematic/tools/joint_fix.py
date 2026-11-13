"""joint_fix.py in.kicad_pcb out.kicad_pcb (KiCad Python): close every weak joint tools/joint_check.py finds by adding
one short track of the same net, layer and width that runs from one item's centre line into the other:
  track-pad   from the track's nearer end towards the pad's centre, to 0.1 mm past the pad's edge;
  track-via   from the track's nearer end to the via's centre;  via-pad: from the via's centre into the pad;
  track-track from the nearer end of one to the nearest point of the other's centre line;
  track-zone  from the track's nearer end on, along the track, until 0.15 mm inside the filled island.
Each added track is tested with finish_route.py's Router (domains.py clearances) and skipped with a message if it
doesn't fit; nothing is removed. Run tools/joint_check.py and the DRC again afterwards. DRY=1 only lists."""
import os,sys,math
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pcbnew, joint_check, finish_route as FR
IU,MM=pcbnew.FromMM,pcbnew.ToMM
def nearest_on(p,a,c):
    dx,dy=c[0]-a[0],c[1]-a[1]; ll=dx*dx+dy*dy
    f=0 if ll==0 else max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/ll))
    return (a[0]+f*dx,a[1]+f*dy)
def into(shape,start,toward,step=0.02,extra=0.1,limit=3.0):
    """walk from start towards `toward` until inside the shape, then `extra` further (not past `toward`)"""
    d=math.dist(start,toward)
    if d<1e-6: return toward
    u=((toward[0]-start[0])/d,(toward[1]-start[1])/d); t=0.0
    while t<=min(d,limit):
        q=(start[0]+u[0]*t,start[1]+u[1]*t)
        if shape.Collide(pcbnew.SHAPE_CIRCLE(FR.V(q),1),0):
            t=min(d,t+extra); return (start[0]+u[0]*t,start[1]+u[1]*t)
        t+=step
    return None
def plan(j):
    """(layer, a, c, width) of the bridging track for weak joint j, or None"""
    ga,gb=j['ga'],j['gb']
    if ga[0]!='t' and gb[0]=='t': ga,gb=gb,ga
    if ga[0]=='t':
        a,c,w=ga[1],ga[2],ga[3]
        if gb[0]=='t':
            a2,c2,w2=gb[1],gb[2],gb[3]
            cand=[(math.dist(p,nearest_on(p,a2,c2)),p,nearest_on(p,a2,c2),w) for p in (a,c)]+[(math.dist(p,nearest_on(p,a,c)),p,nearest_on(p,a,c),w2) for p in (a2,c2)]
            _,p,q,ww=min(cand); return (j['layer'],p,q,ww)
        if gb[0]=='v':
            p=min((a,c),key=lambda e:math.dist(e,gb[1])); return (j['layer'],p,gb[1],w)
        if gb[0]=='p':
            pad=gb[1]; sh=pad.GetEffectiveShape(j['layer']); pc=(MM(pad.GetPosition().x),MM(pad.GetPosition().y))
            p=min((a,c),key=lambda e:math.dist(e,pc)); q=into(sh,p,pc)
            return (j['layer'],p,q,w) if q else None
        if gb[0]=='z':
            for p,o in ((c,a),(a,c)):   # extend past each end in turn
                d=math.dist(o,p)
                if d<1e-6: continue
                far=(p[0]+(p[0]-o[0])/d*1.0,p[1]+(p[1]-o[1])/d*1.0); q=into(gb[1],p,far,extra=0.15)
                if q: return (j['layer'],p,q,w)
            return None
    if {ga[0],gb[0]}=={'v','p'}:
        v,pd=(ga,gb) if ga[0]=='v' else (gb,ga); pad=pd[1]; pc=(MM(pad.GetPosition().x),MM(pad.GetPosition().y))
        q=into(pad.GetEffectiveShape(j['layer']),v[1],pc)
        return (j['layer'],v[1],q,0.2) if q else None
    return None
if __name__=='__main__':
    bad=joint_check.check(sys.argv[1],verbose=False); r=FR.Router(sys.argv[1]); n=0; left=0; done=set()
    for j in bad:
        pl=plan(j)
        if not pl: print('NO PLAN',j['net'],j['a'],'|',j['b']); left+=1; continue
        L,a,c,w=pl; a=(round(a[0],4),round(a[1],4)); c=(round(c[0],4),round(c[1],4))
        if (j['net'],L,a,c) in done or math.dist(a,c)<1e-4: continue
        sh=pcbnew.SHAPE_SEGMENT(FR.V(a),FR.V(c),IU(w)); dg=set()
        if not r.free(j['net'],L,sh,diagnostics=dg):
            print('BLOCKED',j['net'],a,c,sorted({(k[0],k[1],str(k[3])) for k in dg})); left+=1; continue
        done.add((j['net'],L,a,c)); print('bridge',j['net'],r.b.GetLayerName(L),a,c,w,'for',j['a'],'|',j['b'])
        if os.getenv('DRY')!='1':
            t=pcbnew.PCB_TRACK(r.b); t.SetStart(FR.V(a)); t.SetEnd(FR.V(c)); t.SetWidth(IU(w)); t.SetLayer(L); t.SetNet(r.b.FindNet(j['net']))
            r.b.Add(t); r.index_track(t); r.tracks.append(t); n+=1
    if os.getenv('DRY')!='1': r.save(sys.argv[2])
    print('joint_fix: added',n,'left',left)
    sys.exit(1 if left else 0)
