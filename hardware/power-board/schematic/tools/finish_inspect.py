"""Export exact local copper and blockers to work/ for headless routing review.
KiCad python finish_inspect.py BOARD OUT_JSON X0 Y0 X1 Y1 [NET ...]
Exports polygons plus pad/track labels, lock flags and exact coordinates.
"""
import sys,json
import pcbnew
from finish_route import Router, CU, RL, UID, XY, IU, V
r=Router(sys.argv[1]); box=tuple(map(float,sys.argv[3:7])); data=[]
for L in RL:
    seen=set()
    for cell in r.cells(box):
        for ob in r.idx.get((L,)+cell,[]):
            if id(ob) in seen or not r.overlap(ob[3],box): continue
            seen.add(id(ob)); n,sh,kind,bb,cy,uid=ob
            t=r.byid.get(uid); poly=pcbnew.SHAPE_POLY_SET()
            if t: t.TransformShapeToPolygon(poly,L,0,IU(.005),pcbnew.ERROR_INSIDE)
            elif kind in ('zone','keepout'): poly=sh
            else: continue
            rings=[]
            for i in range(poly.OutlineCount()):
                o=poly.Outline(i); rings.append([XY(o.CPoint(j)) for j in range(o.PointCount())])
                for h in range(poly.HoleCount(i)):
                    o=poly.Hole(i,h); rings.append([XY(o.CPoint(j)) for j in range(o.PointCount())]+[None])
            rec=dict(net=n,layer=r.b.GetLayerName(L),kind=kind,uid=uid,poly=rings,locked=t.IsLocked() if t else False)
            if t:
                if kind=='pad': rec['label']=t.GetParentFootprint().GetReference()+'.'+t.GetNumber(); rec['p']=XY(t.GetPosition())
                elif kind=='track': rec['a']=XY(t.GetStart()); rec['b']=XY(t.GetEnd())
                else: rec['p']=XY(t.GetPosition())
            data.append(rec)
json.dump(dict(box=box,items=data),open(sys.argv[2],'w'))
for n in sys.argv[7:]:
    print('NET',n)
    for p in r.pads:
        if p.GetNetname()!=n: continue
        pt=XY(p.GetPosition()); diag=set(); r.seg(n,pcbnew.F_Cu,pt,pt,diag)
        print(p.GetParentFootprint().GetReference(),p.GetNumber(),pt,'point blockers',diag)
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            diag=set(); q=(pt[0]+dx,pt[1]+dy); ok=r.seg(n,pcbnew.F_Cu,pt,q,diag)
            print('  ',(dx,dy),ok,diag)
