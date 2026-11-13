"""Last-stage SHL4 trial: replace R98's P branch and add its paired R99 N tap.

KiCad python finish_pair_branch.py INPUT OUTPUT
Only rips the unlocked, unbranched F.Cu P trace out of R98. Routes both new
branches on In3, with adjacent off-pad vias and a cost favoring side-by-side
tracks. Retains all other Kelvin copper. Saves only a complete trial with at
least 50 percent P pairing. Full-rule refill/DRC and finish_audit must accept it.
"""
import sys,math
import pcbnew
from finish_route import Router,UID,XY,V,IU,CU
from finish_kelvin import paired,distance

def pad(r,ref,num): return next(p for p in r.b.FindFootprintByReference(ref).Pads() if p.GetNumber()==num)

def branch(r):
    root=pad(r,'R98','1'); net=root.GetNetname()
    tracks=[t for t in r.tracks if t.GetNetname()==net and t.GetClass()=='PCB_TRACK' and t.GetLayer()==CU[0]]
    adj={}
    for t in tracks:
        for e in (t.GetStart(),t.GetEnd()): adj.setdefault((e.x,e.y),[]).append(t)
    starts={k for k in adj if root.HitTest(pcbnew.VECTOR2I(*k))}
    otherpads=[p for p in r.pads if p.GetNetname()==net and UID(p)!=UID(root)]
    vias=[t for t in r.tracks if t.GetNetname()==net and t.GetClass()=='PCB_VIA']
    queue=list(starts); seen=set(); stops=[]
    while queue:
        k=queue.pop(); p=pcbnew.VECTOR2I(*k)
        hitvia=any(t.GetEffectiveShape(CU[0]).Collide(p,IU(.001)) for t in vias)
        hitpad=any(t.HitTest(p) for t in otherpads)
        if k not in starts and (len(adj[k])>2 or hitvia or hitpad): stops.append(XY(p)); continue
        for t in adj[k]:
            if UID(t) in seen: continue
            assert not t.IsLocked()
            seen.add(UID(t)); e=t.GetEnd() if (t.GetStart().x,t.GetStart().y)==k else t.GetStart(); queue.append((e.x,e.y))
    assert seen and stops,('not a simple P branch',len(seen),stops)
    return seen,stops

def source_candidates(r,p):
    n=p.GetNetname(); centre=XY(p.GetPosition()); candidates=[]
    for ix in range(round((centre[0]-3.5)*10),round((centre[0]+3.5)*10)+1):
        for iy in range(round((centre[1]-3.5)*10),round((centre[1]+3.5)*10)+1):
            q=(round(ix*.1,6),round(iy*.1,6))
            if not r.via(n,q): continue
            paths=sorted(r.shapes(centre,q),key=r.plen)
            ps=next((ps for ps in paths if r.path(n,CU[0],ps)),None)
            if ps: candidates.append((r.plen(ps),q,ps))
    return sorted(candidates)[:60]

def main():
    inp,out=sys.argv[1:3]; base=Router(inp); rip,stops=branch(base); base.ignore |= rip
    pn,nn='/SHL4_P','/SHL4_N'; pp,np=pad(base,'R98','1'),pad(base,'R99','2')
    pc,nc=source_candidates(base,pp),source_candidates(base,np)
    pairs=[]
    for lp,p,ps in pc:
        for ln,n,ns in nc:
            d=math.dist(p,n)
            if .805<=d<=1.8: pairs.append((lp+ln+abs(d-.9),p,ps,n,ns))
    print('pair branch rip:',len(rip),'stops:',stops,'P candidates:',len(pc),'N candidates:',len(nc),'via pairs:',len(pairs),flush=True)
    baseline=paired([t for t in base.tracks if t.GetNetname()==pn and t.GetClass()=='PCB_TRACK'],[t for t in base.tracks if t.GetNetname()==nn and t.GetClass()=='PCB_TRACK'])
    for attempt,(_,p,ps,n,ns) in enumerate(sorted(pairs)[:24]):
        print('pair branch attempt',attempt+1,p,n,flush=True)
        r=Router(inp); original=list(r.tracks); r.ignore |= rip
        for t in original:
            if UID(t) in rip: r.b.Remove(t)
        try:
            r.commit(pn,[('t',CU[0],ps),('v',p)])
            r.commit(nn,[('t',CU[0],ns),('v',n)])
        except AssertionError: continue
        r.via_filter=lambda net,q: False
        Ptarget=(136.15,214.35); Ntarget=(135.25,214.35); L=CU[3]
        pi=r.simple(pn,[(p,L)],[(Ptarget,L)]) or r.maze(pn,[(p,L)],[(Ptarget,L)])
        if pi is None: continue
        r.commit(pn,pi)
        branchsegs=[(a,c) for it in pi if it[0]=='t' for a,c in zip(it[2],it[2][1:])]
        def cost(net,layer,a,c):
            if net!=nn: return 1.
            q=((a[0]+c[0])/2,(a[1]+c[1])/2)
            d=min(distance(q,s,e) for s,e in branchsegs) if layer==L else 10
            return 1+min(12,max(0,d-.65)*10)
        r.step_cost=cost
        ni=r.maze(nn,[(n,L)],[(Ntarget,L)])
        if ni is None: continue
        r.commit(nn,ni)
        P=[t for t in r.tracks if UID(t) not in rip and t.GetNetname()==pn and t.GetClass()=='PCB_TRACK']
        N=[t for t in r.tracks if t.GetNetname()==nn and t.GetClass()=='PCB_TRACK']
        share=paired(P,N)
        print('pair branch pairing:',round(100*baseline,1),'to',round(100*share,1),flush=True)
        if share<.5: continue
        r.save(out); print('paired branch trial saved:',out,flush=True); return
    print('paired branch rejected; no output saved',flush=True)

if __name__=='__main__': main()
