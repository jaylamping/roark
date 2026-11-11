"""Exact-geometry hand-finishing search for KiCad 10 (no footprint/zone edits).

Usage: KiCad python finish_route.py INPUT OUTPUT DRC_JSON [NET_REGEX]
Only adds 0.2/0.25 mm tracks on F/In2/In3/B and 0.6/0.3 mm vias.
Searches exact endpoint escapes, then a multi-layer maze with collision-tested
edges. Zones are refilled before save. Never removes or edits existing copper. No 54 V inner track or via under the
latch block (domains.LATCH; route_checks.py check 4).
STEP, SECONDS, MARGIN, WINDOW and SIMPLE_ONLY environment variables tune search.
Use kicad-cli pcb drc --refill-zones --save-board on a project-matched copy
after each batch: CLI loads the custom rules for the authoritative final fill.
DRC and route_checks remain mandatory after each batch.
"""
import os, sys, json, math, re, heapq, time
import pcbnew
import domains, stack

IU, MM = pcbnew.FromMM, pcbnew.ToMM
V = lambda p: pcbnew.VECTOR2I(IU(p[0]), IU(p[1]))
XY = lambda p: (MM(p.x), MM(p.y))
UID = lambda p: p.m_Uuid.AsString()
CU = stack.kicad_layers(pcbnew)
RL = [CU[i] for i in stack.ROUTABLE]
OUT = {CU[0], CU[5]}
STEP = float(os.getenv('STEP', '.2'))
MARGIN = float(os.getenv('MARGIN', '.002'))
SECONDS = float(os.getenv('SECONDS', '25'))
WINDOW = float(os.getenv('WINDOW', '8'))
HEURISTIC = float(os.getenv('HEURISTIC', '1.15'))

class Router:
    def __init__(self, path):
        self.b = pcbnew.LoadBoard(path)
        # Retain the input's authoritative, project-aware fill while searching.
        # Save() still performs the required pcbnew refill; CLI then refills
        # with the complete custom-rule engine before acceptance.
        self.b.BuildConnectivity()
        # Keep the snapshot alive across all BOARD.Add calls (KiCad 10).
        self.tracks = list(self.b.GetTracks())
        self.pads = list(self.b.GetPads())
        self.byid = {UID(t): t for t in self.tracks + self.pads}
        self.idx = {}
        self.ignore = set()
        if os.getenv('FCOST'):   # FCOST=<k>: a step on F.Cu costs k times more, so a net prefers the inner layers
            k=float(os.getenv('FCOST')); self.step_cost=lambda net,L,p,q: k if L==CU[0] else 1.0
        self.collect_all = False   # escape_probe.py: free() lists every blocker instead of stopping at the first
        self.fine = []; self.fineshape = []
        for ref in os.getenv('FINE','U1').split(','):   # the .kicad_dru fine-pitch courtyards
            f = self.b.FindFootprintByReference(ref)
            self.fine.append(self.bb(f.GetCourtyard(pcbnew.F_CrtYd).BBox()))
            self.fineshape.append(pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd)))
        e = self.bb(self.b.GetBoardEdgesBoundingBox())
        self.bounds = (e[0]+.85, e[1]+.85, e[2]-.85, e[3]-.85)   # board edge clearance 0.5 mm + via radius 0.3 mm
        for p in self.pads:
            for L in CU:
                if p.IsOnLayer(L):
                    self.add(L, p.GetNetname(), p.GetEffectiveShape(L), 'pad', UID(p))
        for t in self.tracks:
            self.index_track(t)
        zones = list(self.b.Zones())
        zones += [z for f in self.b.GetFootprints() for z in f.Zones()]
        for z in zones:
            if z.GetIsRuleArea():
                kind = 'keepout' if z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() else 'keepout_track' if z.GetDoNotAllowTracks() else 'keepout_via' if z.GetDoNotAllowVias() else None
                if kind is None: continue
                for L in CU:
                    if z.IsOnLayer(L): self.add(L, '', z.Outline().Clone(), kind, UID(z))
            elif z.GetNetname() != 'GND':
                for L in z.GetLayerSet().Seq():
                    if L not in CU: continue
                    ps = z.GetFilledPolysList(L)
                    for i in range(ps.OutlineCount()):
                        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
                        for h in range(ps.HoleCount(i)): one.AddHole(ps.Hole(i, h))
                        self.add(L, z.GetNetname(), one, 'zone', UID(z))
        self.zones = zones
        self.hvzones = [z for z in zones if not z.GetIsRuleArea() and domains.is_hv(z.GetNetname())]
        self.midzones = [z for z in zones if not z.GetIsRuleArea() and z.GetNetname() == '/MID']

    @staticmethod
    def bb(b): return MM(b.GetLeft()), MM(b.GetTop()), MM(b.GetRight()), MM(b.GetBottom())
    def incy(self, shape, bb):
        """U1's courtyard (the .kicad_dru estop_at_U1 scope), if the copper itself enters it, as the .kicad_dru intersectsCourtyard() tests
        (the callers ask on F.Cu only, and never for a pour, as the rules do);
        a bounding-box overlap alone would relax the clearance for a long diagonal that only passes near the courtyard"""
        out = set()
        for i, f in enumerate(self.fine):
            if not self.overlap(bb, f): continue
            c = self.fineshape[i]
            try: hit = c.Collide(shape, 0)
            except Exception: hit = any(c.Collide(shape.Outline(k), 0) for k in range(shape.OutlineCount()))
            if hit: out.add(i)
        return out
    @staticmethod
    def cells(bb):
        for x in range(math.floor(bb[0]/2), math.floor(bb[2]/2)+1):
            for y in range(math.floor(bb[1]/2), math.floor(bb[3]/2)+1): yield x, y
    def add(self, L, net, shape, kind, uid):
        bb = self.bb(shape.BBox())
        cy = self.incy(shape, bb) if L == CU[0] and kind != 'zone' else set()   # the .kicad_dru scope: F.Cu, never a pour
        ob = (net, shape, kind, bb, cy, uid)
        for c in self.cells(bb): self.idx.setdefault((L,)+c, []).append(ob)
    @staticmethod
    def overlap(a, c, gap=0):
        return a[0] <= c[2]+gap and c[0] <= a[2]+gap and a[1] <= c[3]+gap and c[1] <= a[3]+gap
    def index_track(self, t):
        for L in CU:
            if t.IsOnLayer(L): self.add(L, t.GetNetname(), t.GetEffectiveShape(L), 'via' if t.GetClass()=='PCB_VIA' else 'track', UID(t))
    def free(self, net, L, shape, via=False, diagnostics=None):
        bb = self.bb(shape.BBox()); margin = 1.51
        query = (bb[0]-margin, bb[1]-margin, bb[2]+margin, bb[3]+margin)
        cy = self.incy(shape, bb) if L == CU[0] else set()
        seen = set(); hit = False
        for c in self.cells(query):
            for ob in self.idx.get((L,)+c, ()):
                if id(ob) in seen: continue
                seen.add(id(ob))
                n, sh, kind, obb, ocy, uid = ob
                if uid in self.ignore: continue
                if not self.overlap(bb, obb, margin): continue
                if (via and kind=='keepout_track') or (not via and kind=='keepout_via'): continue
                if via and kind=='pad' and sh.Collide(shape, IU(.001)):
                    if diagnostics is not None: diagnostics.add((kind,n,uid,'pad touch'))
                    if not self.collect_all: return False
                    hit=True; continue
                if via and kind=='via' and sh.Collide(shape, IU(.002)):
                    if diagnostics is not None: diagnostics.add((kind,n,uid,'via overlap'))
                    if not self.collect_all: return False
                    hit=True; continue
                if n==net and not kind.startswith('keepout'): continue
                if kind=='zone' and ((via and n=='/VBUS') or os.getenv('SOFTZ')=='1'): continue
                cl = .001 if kind.startswith('keepout') else domains.clearance(net,n,L in OUT)
                if not via and cy & ocy and not kind.startswith('keepout'): cl=min(cl,.2)   # U1's courtyard: the E-stop rule gives way to the pin gap
                if sh.Collide(shape, IU(cl+MARGIN)):
                    if diagnostics is not None: diagnostics.add((kind,n,uid,cl))
                    if not self.collect_all: return False
                    hit=True
        return not hit
    def inside(self,p):
        a=self.bounds
        return a[0]<=p[0]<=a[2] and a[1]<=p[1]<=a[3]
    @staticmethod
    def in_latch(net,box):
        """54 V copper, copper riding on 54 V or the latch supply chain, whose bbox (x0,y0,x1,y1) touches the latch block
        (domains.LATCH): banned on the inner layers, the same set as route_checks check 4"""
        if not domains.latch_inner_banned(net): return False
        lx0,lx1,ly0,ly1=domains.latch_page()
        return box[2]>=lx0 and box[0]<=lx1 and box[3]>=ly0 and box[1]<=ly1
    def seg(self,net,L,a,c,diag=None):
        if not self.inside(a) or not self.inside(c): return False
        w=self.width(net)/2
        if L not in OUT and self.in_latch(net,(min(a[0],c[0])-w,min(a[1],c[1])-w,max(a[0],c[0])+w,max(a[1],c[1])+w)): return False
        sh=pcbnew.SHAPE_SEGMENT(V(a),V(c),IU(self.width(net)))
        return self.free(net,L,sh,diagnostics=diag)
    def via(self,net,p):
        if not self.inside(p) or domains.in_vbus_band(p): return False
        if hasattr(self,'via_filter') and not self.via_filter(net,p): return False
        if self.in_latch(net,(p[0]-.3,p[1]-.3,p[0]+.3,p[1]+.3)): return False   # a via is inner copper too
        if domains.is_estop(net) and any(z.Outline().Contains(V(p)) for z in self.hvzones): return False   # route_checks 5
        # route_checks 7: no via of another net inside a MID pour outline, except the listed ones (domains.MID_VIA_OK)
        if net != '/MID' and not domains.via_listed(p, domains.MID_VIA_OK, net) and any(z.Outline().Contains(V(p)) for z in self.midzones): return False
        sh=pcbnew.SHAPE_CIRCLE(V(p),IU(.3))
        return all(self.free(net,L,sh,via=True) for L in CU)
    @staticmethod
    def width(net): return .25 if net=='GND' or domains.is_hv(net) else .2
    def path(self,net,L,ps): return all(self.seg(net,L,a,c) for a,c in zip(ps,ps[1:]))
    def parse(self,it):
        ob=self.byid.get(it['uuid'])
        desc=it['description']; net=re.search(r'\[([^]]+)\]',desc)[1]
        if ob:
            if ob.GetClass()=='PAD': return net, [(XY(ob.GetPosition()),L) for L in RL if ob.IsOnLayer(L)]
            if ob.GetClass()=='PCB_VIA': return net,[(XY(ob.GetPosition()),L) for L in RL]
            if ob.GetClass()=='PCB_TRACK':
                return net,[(XY(ob.GetStart()),ob.GetLayer()),(XY(ob.GetEnd()),ob.GetLayer())]
        return net, []
    def zone_anchors(self,it,other):
        net=re.search(r'\[([^]]+)\]',it['description'])[1]
        layer=re.search(r'on (\S+)',it['description'])[1].rstrip(','); L=self.b.GetLayerID(layer)
        cand=[]
        zs=[]
        for z in self.zones:
            if z.GetIsRuleArea(): continue
            if os.getenv('ZCOMP')=='1':
                if z.GetNetname()!=net: continue
                zs += [(z,K) for K in RL if z.IsOnLayer(K)]
            elif UID(z)==it['uuid'] and L in RL: zs.append((z,L))
        for z,K in zs:
            ps=z.GetFilledPolysList(K)
            for i in range(ps.OutlineCount()):
                o=ps.Outline(i)
                for j in range(o.PointCount()):
                    a,c=XY(o.CPoint(j)),XY(o.CPoint((j+1)%o.PointCount()))
                    for p,_ in other:
                        dx,dy=c[0]-a[0],c[1]-a[1]; ll=dx*dx+dy*dy
                        f=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(ll or 1)))
                        q=(round(a[0]+f*dx,6),round(a[1]+f*dy,6))
                        cand.append((math.dist(p,q),q,K))
        out=[]
        for _,q,K in sorted(cand):
            if all(K!=J or math.dist(q,a)>.4 for a,J in out) and sum(J==K for a,J in out)<8: out.append((q,K))
            if len(out)>=24: break
        return out
    def component_anchors(self,it,other,base):
        ob=self.byid.get(it['uuid'])
        if not ob or ob.GetNetname()=='GND': return base
        # the whole connected piece, not only what touches the reported item: a via two segments away is an anchor too
        con=self.b.GetConnectivity(); items=[]; seen={UID(ob)}; todo=[ob]
        while todo and len(items)<80:
            for t in con.GetConnectedItems(todo.pop()):
                if not hasattr(t,'m_Uuid') or UID(t) in seen or t.GetClass() not in ('PCB_VIA','PCB_TRACK','PAD'): continue
                seen.add(UID(t)); items.append(t); todo.append(t)
        candidates=list(base)
        via=[]
        for t in items:
            if t.GetClass()=='PCB_VIA':
                via += [(XY(t.GetPosition()),L) for L in RL]
            elif t.GetClass()=='PAD':
                candidates += [(XY(t.GetPosition()),L) for L in RL if t.IsOnLayer(L)]
            elif t.GetClass()=='PCB_TRACK':
                a,c=XY(t.GetStart()),XY(t.GetEnd()); L=t.GetLayer()
                if L not in RL: continue
                candidates += [(a,L),(c,L)]
                dx,dy=c[0]-a[0],c[1]-a[1]; ll=dx*dx+dy*dy
                for p,_ in other:
                    f=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(ll or 1)))
                    candidates.append(((round(a[0]+f*dx,6),round(a[1]+f*dy,6)),L))
        key=lambda a:min(math.dist(a[0],c[0]) for c in other)
        out=[]
        for a in sorted(candidates+via,key=key):
            if all(a[1]!=c[1] or math.dist(a[0],c[0])>.5 for c in out): out.append(a)
            if len(out)>=12: break
        for a in sorted(via,key=key)[:8]:
            if a not in out: out.append(a)
        return out or base
    @staticmethod
    def shapes(p,q):
        yield [p,q]
        x,y=p; X,Y=q
        yield [p,(x,Y),q]; yield [p,(X,y),q]
        d=min(abs(X-x),abs(Y-y)); sx=math.copysign(1,X-x); sy=math.copysign(1,Y-y)
        yield [p,(x+sx*d,y+sy*d),q]; yield [p,(X-sx*d,Y-sy*d),q]
        for off in (.5,-.5,1,-1,2,-2,3,-3):
            yield [p,(x+off,y),(x+off,Y),q]
            yield [p,(x,y+off),(X,y+off),q]
    def simple(self,net,A,B):
        cand=[]
        for p,L in A:
            for q,K in B:
                if L==K:
                    for ps in self.shapes(p,q): cand.append((self.plen(ps),L,ps))
        for _,L,ps in sorted(cand):
            if self.path(net,L,ps): return [('t',L,ps)]
        return None
    @staticmethod
    def plen(ps): return sum(math.dist(a,c) for a,c in zip(ps,ps[1:]))
    def seeds(self,net,anchors):
        out={}
        for p,L in anchors:
            # Straight escapes along a pin's exact axis precede lattice snapping.
            pts=[p]
            for r in (.4,.6,.8,1.,1.2,1.5,1.8,2.2,2.6,3.):
                pts += [(round(p[0]+r*dx,6),round(p[1]+r*dy,6)) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))]
            for ep in pts:
                if not self.seg(net,L,p,ep): continue
                gx,gy=round(ep[0]/STEP),round(ep[1]/STEP)
                for x in range(gx-1,gx+2):
                    for y in range(gy-1,gy+2):
                        q=(round(x*STEP,6),round(y*STEP,6)); k=(L,x,y)
                        if not self.seg(net,L,ep,q): continue
                        cost=math.dist(p,ep)+math.dist(ep,q)
                        if k not in out or cost<out[k][0]: out[k]=(cost,[p,ep,q])
        return out
    def maze(self,net,A,B):
        start=time.monotonic(); SA=self.seeds(net,A); SB=self.seeds(net,B)
        if not SA or not SB:
            print('  no escape',len(SA),len(SB),flush=True); return None
        pts=[p for p,L in A+B]; x0=min(p[0] for p in pts)-WINDOW; x1=max(p[0] for p in pts)+WINDOW
        y0=min(p[1] for p in pts)-WINDOW; y1=max(p[1] for p in pts)+WINDOW
        limits=(x0,y0,x1,y1)
        targets={L:[] for L in RL}
        for L,x,y in SB: targets[L].append((x,y))
        # Heuristic to target bounding box, admissible, layer-change cost 3 mm.
        tx0=min(k[1] for k in SB); tx1=max(k[1] for k in SB); ty0=min(k[2] for k in SB); ty1=max(k[2] for k in SB)
        def h(k):
            L,x,y=k; dx=max(tx0-x,0,x-tx1); dy=max(ty0-y,0,y-ty1)
            return STEP*math.hypot(dx,dy)+(0 if targets[L] else 3)
        dist={k:v[0] for k,v in SA.items()}; prev={}; heap=[]; seq=0
        for k,v in SA.items(): heapq.heappush(heap,(v[0]+HEURISTIC*h(k),seq,v[0],k)); seq+=1
        edgecache={}; viacache={}; visited=0
        def pt(k): return (round(k[1]*STEP,6),round(k[2]*STEP,6))
        while heap:
            _,_,g,k=heapq.heappop(heap)
            if g>dist.get(k,1e30)+1e-8: continue
            visited+=1
            if visited%256==0 and time.monotonic()-start>SECONDS:
                print('  timeout',visited,'nodes',flush=True); return None
            if k in SB:
                nodes=[k]
                while nodes[-1] in prev: nodes.append(prev[nodes[-1]])
                nodes.reverse(); items=[('t',nodes[0][0],SA[nodes[0]][1])]
                run=[pt(nodes[0])]; L=nodes[0][0]
                for nk in nodes[1:]:
                    if nk[0]!=L:
                        items += [('t',L,run),('v',pt(nk))]; run=[pt(nk)]; L=nk[0]
                    else: run.append(pt(nk))
                items += [('t',L,run),('t',L,list(reversed(SB[k][1])))]
                # Simplify with exact collision checks; no approximate shortcuts.
                result=[]
                for it in items:
                    if it[0]=='v': result.append(it); continue
                    ps=it[2]; simple=[ps[0]]; i=0
                    while i<len(ps)-1:
                        j=len(ps)-1
                        while j>i+1 and not self.seg(net,it[1],ps[i],ps[j]): j-=1
                        simple.append(ps[j]); i=j
                    result.append(('t',it[1],simple))
                print('  maze',visited,'nodes',round(time.monotonic()-start,2),'s',flush=True)
                return result
            L,x,y=k; p=pt(k)
            ns=[((L,x+dx,y+dy),STEP*math.hypot(dx,dy),False) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1))]
            ns += [((K,x,y),3.,True) for K in RL if K!=L]
            for nk,cost,isvia in ns:
                if not isvia and hasattr(self,'step_cost'): cost *= self.step_cost(net,L,p,pt(nk))
                ng=g+cost
                if ng>=dist.get(nk,1e30)-1e-8: continue
                q=pt(nk)
                if not (x0<=q[0]<=x1 and y0<=q[1]<=y1): continue
                if isvia:
                    vk=(x,y)
                    if vk not in viacache: viacache[vk]=self.via(net,p)
                    ok=viacache[vk]
                else:
                    ek=(min(k,nk),max(k,nk))
                    if ek not in edgecache: edgecache[ek]=self.seg(net,L,p,q)
                    ok=edgecache[ek]
                if not ok: continue
                dist[nk]=ng; prev[nk]=k
                heapq.heappush(heap,(ng+HEURISTIC*h(nk),seq,ng,nk)); seq+=1
        print('  exhausted',visited,'nodes',flush=True)
        return None
    def commit(self,net,items):
        # Check every new primitive before adding any of them.
        assert all(self.path(net,it[1],it[2]) if it[0]=='t' else self.via(net,it[1]) for it in items)
        ni=self.b.FindNet(net); new=[]
        seen_vias=set()
        for it in items:
            if it[0]=='t':
                for a,c in zip(it[2],it[2][1:]):
                    if math.dist(a,c)<.00001: continue
                    t=pcbnew.PCB_TRACK(self.b); t.SetStart(V(a)); t.SetEnd(V(c)); t.SetWidth(IU(self.width(net))); t.SetLayer(it[1]); t.SetNet(ni)
                    self.b.Add(t); new.append(t)
            elif it[1] not in seen_vias:
                seen_vias.add(it[1]); t=pcbnew.PCB_VIA(self.b); t.SetPosition(V(it[1])); t.SetWidth(IU(.6)); t.SetDrill(IU(.3)); t.SetNet(ni); t.SetViaType(pcbnew.VIATYPE_THROUGH); t.SetLayerPair(CU[0],CU[5]); self.b.Add(t); new.append(t)
        for t in new: self.index_track(t)
        self.tracks.extend(new)
        return len(new)
    def save(self,path):
        pcbnew.ZONE_FILLER(self.b).Fill(self.b.Zones()); self.b.Save(path)

def main():
    r=Router(sys.argv[1]); d=json.load(open(sys.argv[3])); only=re.compile(sys.argv[4] if len(sys.argv)>4 else '.*')
    edges=[]
    for i,u in enumerate(d['unconnected_items']):
        n,A=r.parse(u['items'][0]); _,B=r.parse(u['items'][1])
        if not only.search(n) or (n.startswith('/SH') and os.getenv('ALLOWSH')!='1'): continue   # Kelvin legs only on request
        if not A and B and u['items'][0]['description'].startswith('Zone'): A=r.zone_anchors(u['items'][0],B)
        if not B and A and u['items'][1]['description'].startswith('Zone'): B=r.zone_anchors(u['items'][1],A)
        if not A or not B: continue
        if os.getenv('COMPONENTS')=='1':
            A0,B0=A,B
            A=r.component_anchors(u['items'][0],B0,A0); B=r.component_anchors(u['items'][1],A0,B0)
        length=min(math.dist(a[0],b[0]) for a in A for b in B)
        edges.append((length,i,n,A,B))
    done=[]
    for length,i,n,A,B in sorted(edges):
        print('TRY',i,n,round(length,2),flush=True)
        result=r.simple(n,A,B)
        if not result and os.getenv('SIMPLE_ONLY')!='1': result=r.maze(n,A,B)
        if result:
            count=r.commit(n,result); done.append((i,n)); print('CLOSED',i,n,count,'primitives',flush=True)
        else: print('LEFT',i,n,flush=True)
    r.save(sys.argv[2]); print('finish_route added edges:',len(done),done,flush=True)

if __name__=='__main__': main()
