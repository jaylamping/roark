"""Stitch isolated F.Cu GND fill outlines to the solid planes without edits.

KiCad python finish_ground_islands.py INPUT OUTPUT
Finds F.Cu GND fill outlines with no connection through an existing GND via or
PTH pad, including tracks which lead to those. Tries an off-pad 0.6/0.3 GND via
inside each remaining outline. Never changes the zone definition or removes
copper. DRC must verify that the island count decreases without new violations.
"""
import sys,math,os
import pcbnew
from finish_route import Router,UID,XY,IU,V,CU

def main():
    r=Router(sys.argv[1]); con=r.b.GetConnectivity(); grounded=[]
    for t in r.tracks+r.pads:
        if t.GetNetname()!='GND' or not t.IsOnLayer(CU[0]): continue
        if t.GetClass()=='PCB_VIA' or (t.GetClass()=='PAD' and t.HasHole()): grounded.append(t); continue
        connected=con.GetConnectedItems(t)
        if any(c.GetClass()=='PCB_VIA' or (c.GetClass()=='PAD' and c.HasHole()) for c in connected): grounded.append(t)
    count=0
    for z in r.b.Zones():
        if z.GetIsRuleArea() or z.GetNetname()!='GND' or not z.IsOnLayer(CU[0]): continue
        ps=z.GetFilledPolysList(CU[0])
        for i in range(ps.OutlineCount()):
            poly=pcbnew.SHAPE_POLY_SET(); poly.AddOutline(ps.Outline(i))
            for h in range(ps.HoleCount(i)): poly.AddHole(ps.Hole(i,h))
            bb=r.bb(poly.BBox())
            if any(r.overlap(bb,r.bb(t.GetBoundingBox())) and poly.Collide(t.GetEffectiveShape(CU[0]),IU(.001)) for t in grounded): continue
            print('ungrounded outline',i,'bbox',bb,flush=True)
            # Try the centre, then a 0.1 mm scan. A via can slightly overhang the
            # fill edge; its centre must lie in this island and copper refill
            # supplies the clearance to other nets.
            points=[((bb[0]+bb[2])/2,(bb[1]+bb[3])/2)]
            points += [(round(x*.1,5),round(y*.1,5)) for x in range(math.ceil(bb[0]*10),math.floor(bb[2]*10)+1) for y in range(math.ceil(bb[1]*10),math.floor(bb[3]*10)+1)]
            for p in points:
                if not poly.Contains(V(p)) or not r.via('GND',p): continue
                r.commit('GND',[('v',p)]); count+=1; print('stitched outline',i,'at',p,flush=True); break
            else:
                anchors=[(p,CU[0]) for p in points if poly.Contains(V(p)) and r.seg('GND',CU[0],p,p)]
                anchors=sorted(anchors,key=lambda a:math.dist(a[0],points[0]))[:8]
                nearby=[]
                for x in range(math.floor((bb[0]-3)*5),math.ceil((bb[2]+3)*5)+1):
                    for y in range(math.floor((bb[1]-3)*5),math.ceil((bb[3]+3)*5)+1):
                        p=(round(x*.2,5),round(y*.2,5))
                        if r.via('GND',p): nearby.append((p,CU[0]))
                nearby=sorted(nearby,key=lambda a:math.dist(a[0],points[0]))[:40]
                fix=r.simple('GND',anchors,nearby) if anchors and nearby else None
                if fix is None and anchors and nearby: fix=r.maze('GND',anchors,nearby)
                if fix:
                    vp=next(it[2][-1] for it in reversed(fix) if it[0]=='t'); fix.append(('v',vp)); r.commit('GND',fix); count+=1
                    print('stitched outline',i,'by stub to',vp,flush=True)
                elif os.getenv('SHOVE')=='1' and anchors:
                    from finish_shove import shove
                    targets=[]
                    for t in r.tracks:
                        if t.GetNetname()=='GND' and t.GetClass()=='PCB_VIA': targets.append(XY(t.GetPosition()))
                    targets=sorted(set(targets),key=lambda p:math.dist(p,points[0]))[:8]
                    BB=[(p,L) for p in targets for L in (CU[0],CU[2],CU[3],CU[5])]
                    if BB and shove(r,'GND',anchors,BB): count+=1; print('stitched outline',i,'by displaced escape',flush=True)
                    else: print('no displaced escape in outline',i,flush=True)
                    # The transaction refilled zones, invalidating the borrowed
                    # polygon iteration snapshot. Start a fresh run if needed.
                    r.save(sys.argv[2]); print('finish_ground_islands islands stitched:',count,flush=True); return
                else: print('no legal via or escape in outline',i,flush=True)
    r.save(sys.argv[2]); print('finish_ground_islands islands stitched:',count,flush=True)

if __name__=='__main__':main()
