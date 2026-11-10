"""joint_check.py board.kicad_pcb [MIN=0.1] (KiCad Python): every copper joint has real overlap.
KiCad's connectivity (and so its DRC "unconnected" list) accepts two shapes that only touch at a tangent point: a 0.2 mm
track ending 0.2 mm beside another 0.2 mm track counts as connected, but the copper joint is a point. This check builds
each net's connectivity twice from the copper shapes:
  touch : two items are joined when their shapes touch at all (what KiCad accepts);
  strong: two items are joined only when they overlap by MIN mm or more (default 0.1):
            track-track  w1/2 + w2/2 - (distance between the centre lines)           >= MIN
            track-via    r + w/2 - (distance from the centre line to the via centre) >= MIN
            track-pad    w/2 - (distance from the centre line to the pad shape)      >= MIN (for a 0.2 mm track: the
                         centre line reaches the pad)
            via-pad      r - (distance from the via centre to the pad shape)         >= MIN
            via-via, pad-pad: shapes overlap after shrinking one by MIN
            item-zone    the track's centre line reaches the filled island; the island reaches MIN inside the via or pad
A net fails when the strong graph has more pieces than the touch graph: some joint that holds the net together is weaker
than MIN. Each such joint is listed with its overlap and position (page mm). A dead-end piece with no pad and no via
(a fill sliver, a stub) that hangs on one weak joint is not counted. Zones are taken as filled in the file.
Exit 1 on any weak joint."""
import sys,math,collections
import pcbnew
IU,MM=pcbnew.FromMM,pcbnew.ToMM
def segdist(a,b,c,d):
    """distance between segments ab and cd (points as (x,y) in mm)"""
    def pd(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]; ll=dx*dx+dy*dy
        f=0 if ll==0 else max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/ll))
        return math.hypot(p[0]-a[0]-f*dx,p[1]-a[1]-f*dy)
    def ccw(p,q,r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if a!=b and c!=d:
        d1,d2,d3,d4=ccw(a,b,c),ccw(a,b,d),ccw(c,d,a),ccw(c,d,b)
        if d1*d2<0 and d3*d4<0: return 0.0
    return min(pd(a,c,d),pd(b,c,d),pd(c,a,b),pd(d,a,b))
def check(path,MIN=0.1,verbose=True):
    b=pcbnew.LoadBoard(path)
    CUL=[L for L in b.GetEnabledLayers().CuStack()]
    # nodes: ('t',i) track, ('v',i) via, ('p',i) pad, ('z',i) zone island
    tracks=[t for t in b.GetTracks() if t.GetClass()!='PCB_VIA']; vias=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
    pads=[p for p in b.GetPads() if p.GetNetname()]
    T=[]   # (net, layer, a, c, w)
    for t in tracks:
        s,e=t.GetStart(),t.GetEnd(); T.append((t.GetNetname(),t.GetLayer(),(MM(s.x),MM(s.y)),(MM(e.x),MM(e.y)),MM(t.GetWidth())))
    VI=[]  # (net, (x,y), r, layers)
    for v in vias:
        p=v.GetPosition(); VI.append((v.GetNetname(),(MM(p.x),MM(p.y)),MM(v.GetWidth(pcbnew.F_Cu))/2,[L for L in CUL if v.IsOnLayer(L)]))
    isl=[]  # (net, layer, polyset, bbox)
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.GetNetname(): continue
        for L in CUL:
            if not z.IsOnLayer(L): continue
            ps=z.GetFilledPolysList(L)
            for i in range(ps.OutlineCount()):
                one=pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
                for h in range(ps.HoleCount(i)): one.AddHole(ps.Hole(i,h))
                bb=one.BBox(); isl.append((z.GetNetname(),L,one,(MM(bb.GetLeft()),MM(bb.GetTop()),MM(bb.GetRight()),MM(bb.GetBottom()))))
    G=2.0
    def cells(x0,y0,x1,y1):
        for gx in range(int(x0//G),int(x1//G)+1):
            for gy in range(int(y0//G),int(y1//G)+1): yield gx,gy
    idx=collections.defaultdict(list)   # (net,layer,cell) -> nodes
    def put(net,L,box,node):
        for c in cells(*box): idx[(net,L)+c].append(node)
    for i,(n,L,a,c,w) in enumerate(T): put(n,L,(min(a[0],c[0])-w/2,min(a[1],c[1])-w/2,max(a[0],c[0])+w/2,max(a[1],c[1])+w/2),('t',i))
    for i,(n,p,r,Ls) in enumerate(VI):
        for L in Ls: put(n,L,(p[0]-r,p[1]-r,p[0]+r,p[1]+r),('v',i))
    PSH={}
    for i,p in enumerate(pads):
        for L in CUL:
            if p.IsOnLayer(L) and p.FlashLayer(L):
                s=p.GetEffectiveShape(L); PSH[(i,L)]=s; bb=s.BBox()
                put(p.GetNetname(),L,(MM(bb.GetLeft()),MM(bb.GetTop()),MM(bb.GetRight()),MM(bb.GetBottom())),('p',i))
    for i,(n,L,ps,bb) in enumerate(isl): put(n,L,bb,('z',i))
    V2=lambda p: pcbnew.VECTOR2I(IU(p[0]),IU(p[1]))
    SHR={}
    def shrunk(i,L):
        """pad i's copper on layer L pulled in by MIN on every side"""
        if (i,L) not in SHR:
            q=pcbnew.SHAPE_POLY_SET(); pads[i].TransformShapeToPolygon(q,L,0,IU(0.005),pcbnew.ERROR_INSIDE)
            q.Deflate(IU(MIN),pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS,IU(0.005)); SHR[(i,L)]=q
        return SHR[(i,L)]
    def col(a,c,cl):
        try: return a.Collide(c,cl)
        except Exception: return c.Collide(a,cl)
    def overlap(L,x,y):
        """overlap depth in mm between nodes x and y on layer L (negative: apart); None when not comparable"""
        (kx,ix),(ky,iy)=x,y
        if kx>ky: (kx,ix),(ky,iy)=(ky,iy),(kx,ix)
        if kx=='t' and ky=='t':
            _,_,a,c,w=T[ix]; _,_,a2,c2,w2=T[iy]; return w/2+w2/2-segdist(a,c,a2,c2)
        if kx=='t' and ky=='v':
            _,_,a,c,w=T[ix]; _,p,r,_=VI[iy]; return r+w/2-segdist(a,c,p,p)
        if kx=='p' and ky=='t':
            _,_,a,c,w=T[iy]; s=PSH[(ix,L)]; line=pcbnew.SHAPE_SEGMENT(V2(a),V2(c),2)
            if col(s,line,0): return w/2
            lo,hi=0.0,w/2+0.01   # bisect the distance from the centre line to the pad
            if not col(s,line,IU(hi)): return -1
            for _ in range(12):
                m=(lo+hi)/2
                if col(s,line,IU(m)): hi=m
                else: lo=m
            return w/2-hi
        if kx=='p' and ky=='v':
            _,p,r,_=VI[iy]; s=PSH[(ix,L)]; pt=pcbnew.SHAPE_CIRCLE(V2(p),1)
            if col(s,pt,0): return r
            lo,hi=0.0,r+0.01
            if not col(s,pt,IU(hi)): return -1
            for _ in range(12):
                m=(lo+hi)/2
                if col(s,pt,IU(m)): hi=m
                else: lo=m
            return r-hi
        if kx=='v' and ky=='v':
            _,p,r,_=VI[ix]; _,p2,r2,_=VI[iy]; return r+r2-math.dist(p,p2)
        if kx=='p' and ky=='p':
            s,s2=PSH[(ix,L)],PSH[(iy,L)]
            if not col(s,s2,0): return -1
            return MIN if pads[ix].GetParentFootprint() is pads[iy].GetParentFootprint() else 0.0   # same footprint: the package's own
        if ky=='z':
            _,_,ps,_=isl[iy]
            if kx=='t':
                _,_,a,c,w=T[ix]
                if col(ps,pcbnew.SHAPE_SEGMENT(V2(a),V2(c),2),0): return w/2
                return 0.0 if col(ps,pcbnew.SHAPE_SEGMENT(V2(a),V2(c),IU(w)),0) else -1
            if kx=='v':
                _,p,r,_=VI[ix]
                if col(ps,pcbnew.SHAPE_CIRCLE(V2(p),IU(max(r-MIN,0.01))),0): return MIN
                return 0.0 if col(ps,pcbnew.SHAPE_CIRCLE(V2(p),IU(r)),0) else -1
            if kx=='p':
                s=PSH[(ix,L)]
                if not col(ps,s,0): return -1
                return MIN if col(ps,shrunk(ix,L),0) else 0.0   # the fill reaches MIN or more inside the pad's outline
            if kx=='z': return None
        return None
    class UF:
        def __init__(s): s.p={}
        def f(s,x):
            while s.p.setdefault(x,x)!=x: s.p[x]=s.p[s.p[x]]; x=s.p[x]
            return x
        def u(s,x,y): s.p[s.f(x)]=s.f(y)
    touch,strong=UF(),UF(); weak=[]
    # a via and a PTH pad are one node over all their layers already; walk every (net, layer, cell) bucket once per pair
    seen=set()
    for key,nodes in idx.items():
        L=key[1]
        for i in range(len(nodes)):
            for j in range(i+1,len(nodes)):
                x,y=nodes[i],nodes[j]
                if x==y or (L,x,y) in seen: continue
                seen.add((L,x,y))
                o=overlap(L,x,y)
                if o is None or o<-1e-6: continue
                touch.u(x,y)
                if o>=MIN-1e-6: strong.u(x,y)
                else: weak.append((key[0],L,x,y,o))
    def where(x):
        k,i=x
        if k=='t': return f'track {T[i][2]}-{T[i][3]} w{T[i][4]:g}'
        if k=='v': return f'via {VI[i][1]}'
        if k=='p': p=pads[i]; q=p.GetPosition(); return f'pad {p.GetParentFootprint().GetReference()}.{p.GetNumber()} ({MM(q.x):.2f}, {MM(q.y):.2f})'
        return f'zone island at {isl[i][3]}'
    # a weak joint counts only when it holds parts of the net together: both sides are separate pieces of the strong graph,
    # and neither side is a dead-end scrap (a piece with no pad and no via that hangs on this one joint: a fill sliver
    # or a stub, which carries no current)
    live=[w for w in weak if strong.f(w[2])!=strong.f(w[3])]
    haspv=collections.Counter()
    for kind,n in (('p',len(pads)),('v',len(VI))):
        for i in range(n):
            if (kind,i) in strong.p: haspv[strong.f((kind,i))]+=1
    while True:
        nb=collections.defaultdict(set)
        for w in live:
            a,c=strong.f(w[2]),strong.f(w[3]); nb[a].add(c); nb[c].add(a)
        dead={c for c,s_ in nb.items() if len(s_)==1 and not haspv[c]}
        if not dead: break
        live=[w for w in live if strong.f(w[2]) not in dead and strong.f(w[3]) not in dead]
    def geo(x):
        k,i=x
        return {'t':lambda:('t',)+T[i][2:],'v':lambda:('v',VI[i][1],VI[i][2]),'p':lambda:('p',pads[i]),'z':lambda:('z',isl[i][2])}[k]()
    bad=[dict(net=n,layer=L,overlap=round(o,3),a=where(x),b=where(y),ga=geo(x),gb=geo(y)) for n,L,x,y,o in live]
    if verbose:
        print(f'joints: {len(seen)} touching pairs tested, {len(weak)} with under {MIN} mm of overlap, {len(bad)} of them hold a net together')
        for r in sorted(bad,key=lambda r:(r['net'],r['a'])): print('   WEAK',r['net'],b.GetLayerName(r['layer']),r['overlap'],'|',r['a'],'|',r['b'])
    return bad
if __name__=='__main__':
    m=[a for a in sys.argv[2:] if a.startswith('MIN=')]
    sys.exit(1 if check(sys.argv[1],float(m[0][4:]) if m else 0.1) else 0)
