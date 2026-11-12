"""lay_path.py in.kicad_pcb out.kicad_pcb SPEC... (KiCad Python): lay hand-specified copper, checked against the same
exact-geometry rules as finish_route.py (its Router: domains.py clearances, fine-pitch courtyards, latch and VBUS-band
via rules). Each SPEC is  NET=<item>;<item>;...  with items
  F|2|3|B:x,y x,y ...   a track on F.Cu / In2.Cu / In3.Cu / B.Cu through the points (page mm)
  v:x,y                 a 0.6/0.3 mm via
A spec that fails a check is reported with what blocks it and nothing of it is added (DRY=1 only reports).
LOCK=1 locks what was added. RIP=1 removes unlocked tracks and vias of other nets that block a spec (for a rebuild). A SPEC argument @file reads one SPEC per line from the file (tools/hand_laid.specs holds
this board's). MODE=check only tests that every primitive of the specs is on the board. Exit 1 if any spec was blocked
(or, with MODE=check, missing). Zones are refilled on save; run the kicad-cli DRC after."""
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
def blockers(r,net,items):
    """uuids of everything that blocks the spec"""
    dg=set(); r.collect_all=True
    for it in items:
        if it[0]=='v':
            sh=pcbnew.SHAPE_CIRCLE(FR.V(it[1]),FR.IU(.3))
            for L in FR.CU: r.free(net,L,sh,via=True,diagnostics=dg)
        else:
            for a,c in zip(it[2],it[2][1:]): r.seg(net,it[1],a,c,dg)
    r.collect_all=False
    return {k[2] for k in dg}
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
    n=0; fail=0; specs=[]
    for a in sys.argv[2 if os.getenv('MODE')=='check' else 3:]:   # @file: one SPEC per line, # comments (MODE=check takes no output file)
        specs+=[l.strip() for l in open(a[1:],encoding='utf-8') if l.strip() and not l.lstrip().startswith('#')] if a.startswith('@') else [a]
    if os.getenv('MODE')=='check':   # every primitive of the specs is on the board (no output file needed)
        import blocks
        b=pcbnew.LoadBoard(sys.argv[1]); have={blocks.key(t) for t in b.GetTracks()}; miss=0
        for spec in specs:
            net,items=parse(spec)
            for it in items:
                ps=[('v',net,it[1])] if it[0]=='v' else [('t',net,it[1],a,c,FR.Router.width(net)) for a,c in zip(it[2],it[2][1:])]
                for p in ps:
                    if blocks.pkey(p) not in have: miss+=1; print('   hand-laid copper missing:',net,p[2:] if p[0]=='v' else (b.GetLayerName(p[2]),)+p[3:])
        print('hand-laid copper check:',len(specs),'specs,',miss,'primitives missing'); sys.exit(1 if miss else 0)
    r=FR.Router(sys.argv[1]); ripped=[]
    for spec in specs:
        net,items=parse(spec); bad=check(r,net,items)
        if bad and os.getenv('RIP')=='1':
            # RIP=1 (a rebuild: the routers' copper differs from run to run): unlocked tracks and vias of other nets
            # that block the spec are removed, to be re-routed by finish_route.py; pads, pours and locked copper still block
            uids=blockers(r,net,items); obs=[r.byid.get(u) for u in uids]
            if uids and all(o is not None and o.GetClass() in ('PCB_TRACK','PCB_VIA') and not o.IsLocked() for o in obs):
                r.ignore.update(uids)
                if not check(r,net,items): ripped+=obs; bad=[]; print('RIPPED for',net,sorted({o.GetNetname() for o in obs}),len(obs),'items')
                else: r.ignore.difference_update(uids)
        if bad:
            fail+=1; print('BLOCKED',net)
            for b in bad: print('   ',b)
            continue
        if os.getenv('DRY')!='1':
            k0=len(r.tracks); n+=r.commit(net,items)
            if os.getenv('LOCK')=='1':
                for t in r.tracks[k0:]: t.SetLocked(True)
            print('LAID',net)
    if os.getenv('DRY')!='1':
        for o in ripped: r.b.Remove(o)
        r.save(sys.argv[2])
    print('added',n,'blocked',fail,'ripped',len(ripped))
    sys.exit(1 if fail else 0)   # a blocked spec is a failure: nothing downstream may take the board as complete
