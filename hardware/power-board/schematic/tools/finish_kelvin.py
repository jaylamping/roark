"""Last-stage trial: re-route one unlocked Kelvin N leg beside its P leg.

KiCad python finish_kelvin.py INPUT OUTPUT /SHL4
Only use after all other routing attempts. Keeps P fixed, removes only unlocked
N copper, and reconnects every N pad. Penalizes leaving the P leg and confines
new N vias to within 1.3 mm of P vias. Saves only a complete trial whose P
pairing share improves to at least 50 percent. Full-rule CLI refill, DRC,
route_checks and finish_audit are mandatory before accepting the trial.
"""
import sys,math,os
import pcbnew
from finish_route import Router,UID,XY,IU,CU,RL

def distance(p,a,c):
    dx,dy=c[0]-a[0],c[1]-a[1]; ll=dx*dx+dy*dy
    f=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(ll or 1)))
    return math.hypot(p[0]-a[0]-f*dx,p[1]-a[1]-f*dy)

def paired(P,N):
    total=near=0.
    for t in P:
        a,c=XY(t.GetStart()),XY(t.GetEnd()); length=math.dist(a,c); k=max(1,int(length/.25)); total+=length
        for i in range(k):
            f=(i+.5)/k; q=(a[0]+f*(c[0]-a[0]),a[1]+f*(c[1]-a[1]))
            if any(u.GetLayer()==t.GetLayer() and distance(q,XY(u.GetStart()),XY(u.GetEnd()))<=1+pcbnew.ToMM(u.GetWidth())/2 for u in N): near+=length/k
    return near/max(total,1e-9)

def trial(inp,out,stem,reverse=False):
    r=Router(inp); pn,nn=stem+'_P',stem+'_N'; original=list(r.tracks)
    P=[t for t in original if t.GetNetname()==pn and t.GetClass()=='PCB_TRACK']
    N=[t for t in original if t.GetNetname()==nn]; assert not any(t.IsLocked() for t in N)
    baseline=paired(P,[t for t in N if t.GetClass()=='PCB_TRACK'])
    r.ignore |= {UID(t) for t in N}
    pv=[XY(t.GetPosition()) for t in original if t.GetNetname()==pn and t.GetClass()=='PCB_VIA']
    segments={L:[(XY(t.GetStart()),XY(t.GetEnd())) for t in P if t.GetLayer()==L] for L in RL}
    cache={}
    def cost(net,L,a,c):
        if net!=nn: return 1.
        q=((a[0]+c[0])/2,(a[1]+c[1])/2); key=(L,round(q[0],4),round(q[1],4))
        if key not in cache:
            d=min((distance(q,s,e) for s,e in segments[L]),default=20)
            cache[key]=1+min(12,max(0,d-.7)*6)
        return cache[key]
    r.step_cost=cost
    r.via_filter=lambda net,p: net!=nn or any(math.dist(p,q)<=1.3 for q in pv)
    pads=[p for p in r.pads if p.GetNetname()==nn]
    def kind(p):
        ref=p.GetParentFootprint().GetReference()
        return 0 if ref.startswith('U1') else 1 if ref.startswith('U2') else 2 if ref.startswith('RS') else 3
    pads.sort(key=kind,reverse=reverse)
    connected=[(XY(pads[0].GetPosition()),L) for L in RL if pads[0].IsOnLayer(L)]
    for p in pads[1:]:
        target=[(XY(p.GetPosition()),L) for L in RL if p.IsOnLayer(L)]
        print('kelvin routing',p.GetParentFootprint().GetReference(),p.GetNumber(),flush=True)
        items=r.maze(nn,connected,target)
        if items is None: print('kelvin rejected: cannot connect all pads',flush=True); return False
        r.commit(nn,items); connected+=target
        for it in items:
            if it[0]=='t': connected += [(q,it[1]) for q in it[2]]
            else: connected += [(it[1],L) for L in RL]
    newN=[t for t in r.tracks[len(original):] if t.GetClass()=='PCB_TRACK']
    share=paired(P,newN); print('kelvin trial pairing',round(100*baseline,1),'to',round(100*share,1),flush=True)
    # KMIN: the pairing share a trial must reach (default 50 %)
    if share<max(float(os.getenv('KMIN','.50')),baseline+.05): print('kelvin rejected: insufficient paired length',flush=True); return False
    for t in N: r.b.Remove(t)
    r.save(out); print('kelvin complete trial saved',out,flush=True); return True

def main():
    assert sys.argv[3] in ('/SHL2','/SHL4','/SHL6','/SH9','/SH')
    if not trial(*sys.argv[1:4]): trial(*sys.argv[1:4],reverse=True)

if __name__=='__main__':main()
