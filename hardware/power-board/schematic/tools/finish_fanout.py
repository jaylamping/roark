"""Replace unlocked local F.Cu GND stubs with direct GND-plane fanouts.

KiCad python finish_fanout.py INPUT OUTPUT X0 Y0 X1 Y1
Keeps existing vias and locked tracks. Reconnects every touched GND pad or
retained track contact using an off-pad 0.6/0.3 via and 0.25 mm stub. Rolls back
the entire operation if a contact cannot be restored. Validate with DRC and
finish_audit.py; intended to free narrow signal pin escapes.
"""
import sys,math
import pcbnew
from finish_route import Router,XY,UID,IU,V,CU,RL

def main():
    r=Router(sys.argv[1]); box=tuple(map(float,sys.argv[3:7])); original=list(r.tracks)
    removed=[t for t in original if t.GetClass()=='PCB_TRACK' and t.GetLayer()==CU[0] and t.GetNetname()=='GND' and not t.IsLocked() and all(box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3] for p in (XY(t.GetStart()),XY(t.GetEnd())))]
    ids={UID(t) for t in removed}; r.ignore |= ids
    def touches(t): return t.IsOnLayer(CU[0]) and any(t.GetEffectiveShape(CU[0]).Collide(c.GetEffectiveShape(CU[0]),IU(.001)) for c in removed)
    terms=[(XY(p.GetPosition()),CU[0],p.GetParentFootprint().GetReference()+'.'+p.GetNumber()) for p in r.pads if p.GetNetname()=='GND' and touches(p)]
    for t in original:
        if UID(t) in ids or t.GetNetname()!='GND' or t.GetClass()!='PCB_TRACK' or t.GetLayer()!=CU[0]: continue
        for e in (t.GetStart(),t.GetEnd()):
            sh=pcbnew.SHAPE_CIRCLE(e,0)
            if any(c.GetEffectiveShape(CU[0]).Collide(sh,IU(.001)) for c in removed): terms.append((XY(e),CU[0],'track contact'))
    print('fanout removing',len(removed),'stubs; restoring',terms,flush=True)
    for p,L,label in terms:
        cand=[]
        for radius in (.6,.8,1.,1.1,1.2,1.3,1.5,1.8,2.2,2.6,3.2,4.):
            for k in range(32):
                q=(round(p[0]+radius*math.cos(k*math.pi/16),5),round(p[1]+radius*math.sin(k*math.pi/16),5))
                if r.via('GND',q): cand.append((q,L))
        fix=r.simple('GND',[(p,L)],cand) if cand else None
        if fix is None and cand: fix=r.maze('GND',[(p,L)],cand)
        if fix is None:
            print('fanout ROLLED BACK: cannot fan out',label,flush=True)
            # Original file is loaded afresh, so no trial copper is saved.
            r=Router(sys.argv[1]); r.save(sys.argv[2]); return
        vp=next(it[2][-1] for it in reversed(fix) if it[0]=='t'); fix.append(('v',vp))
        r.commit('GND',fix); print('fanout',label,'via',vp,flush=True)
    for t in removed: r.b.Remove(t)
    r.save(sys.argv[2]); print('fanout restored',len(terms),'contacts',flush=True)

if __name__=='__main__':main()
