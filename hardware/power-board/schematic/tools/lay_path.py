"""lay_path.py in.kicad_pcb out.kicad_pcb SPEC... (KiCad Python): lay hand-specified copper, checked against the same
exact-geometry rules as finish_route.py (its Router: domains.py clearances, fine-pitch courtyards, latch and VBUS-band
via rules). Each SPEC is  NET=<item>;<item>;...  with items
  F|2|3|B:x,y x,y ...   a track on F.Cu / In2.Cu / In3.Cu / B.Cu through the points (page mm)
  v:x,y                 a 0.6/0.3 mm via
A spec that fails a check is reported with what blocks it and nothing of it is added (DRY=1 only reports).
LOCK=1 locks what was added. Zones are refilled on save; run the kicad-cli DRC after."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import finish_route as FR, pcbnew
LAY={'F':FR.CU[0],'2':FR.CU[2],'3':FR.CU[3],'B':FR.CU[5]}
def parse(spec):
    net,body=spec.split('=',1); items=[]
    for it in body.split(';'):
        it=it.strip()
        if not it: continue
        k,pts=it.split(':'); P=[tuple(float(c) for c in p.split(',')) for p in pts.split()]
        items.append(('v',P[0]) if k=='v' else ('t',LAY[k],P))
    return net,items
def check(r,net,items):
    bad=[]
    for it in items:
        if it[0]=='v':
            if not r.via(net,it[1]):
                dg=set(); sh=pcbnew.SHAPE_CIRCLE(FR.V(it[1]),FR.IU(.3)); r.collect_all=True
                for L in FR.CU: r.free(net,L,sh,via=True,diagnostics=dg)
                r.collect_all=False; bad.append(('via',it[1],sorted({(k[0],k[1],str(k[3])) for k in dg})))
        else:
            for a,c in zip(it[2],it[2][1:]):
                dg=set()
                if not r.seg(net,it[1],a,c,dg): bad.append(('seg',a,c,sorted({(k[0],k[1],str(k[3])) for k in dg})))
    return bad
if __name__=='__main__':
    r=FR.Router(sys.argv[1]); n=0; fail=0
    for spec in sys.argv[3:]:
        net,items=parse(spec); bad=check(r,net,items)
        if bad:
            fail+=1; print('BLOCKED',net)
            for b in bad: print('   ',b)
            continue
        if os.getenv('DRY')!='1':
            k0=len(r.tracks); n+=r.commit(net,items)
            if os.getenv('LOCK')=='1':
                for t in r.tracks[k0:]: t.SetLocked(True)
            print('LAID',net)
    if os.getenv('DRY')!='1': r.save(sys.argv[2])
    print('added',n,'blocked',fail)
