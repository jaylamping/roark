"""Export the board's copper per layer for tools/render_routed.py: pads, tracks, vias and zone fills as polygons with
their net, the board outline, and the open connections from a KiCad DRC JSON (unconnected_items). Page mm.
Run with KiCad's Python: <kicad python> tools/render_export.py <board.kicad_pcb> <drc.json> <out.json>"""
import json,sys,os
import pcbnew
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import stack
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.ToMM
LAY=stack.kicad_layers(pcbnew)
def polys(ps):
    out=[]
    for i in range(ps.OutlineCount()):
        o=ps.Outline(i); out.append([(mm(o.CPoint(k).x),mm(o.CPoint(k).y)) for k in range(o.PointCount())])
    return out
D=dict(layers=[b.GetLayerName(L) for L in LAY],items=[],edge=None,open=[])
bb=b.GetBoardEdgesBoundingBox(); D['edge']=[mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom())]
for i,L in enumerate(LAY):
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsOnLayer(L): continue
        D['items'].append(dict(k='zone',L=i,net=z.GetNetname(),p=polys(z.GetFilledPolysList(L))))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if not p.IsOnLayer(L): continue
            s=pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(s,L,0,pcbnew.FromMM(.01),pcbnew.ERROR_INSIDE)
            D['items'].append(dict(k='pad',L=i,net=p.GetNetname(),p=polys(s)))
    for t in b.GetTracks():
        if t.GetClass()=='PCB_VIA':
            q=t.GetPosition(); D['items'].append(dict(k='via',L=i,net=t.GetNetname(),c=[mm(q.x),mm(q.y)],r=mm(t.GetWidth(pcbnew.F_Cu))/2))
        elif t.GetLayer()==L:
            s,e=t.GetStart(),t.GetEnd(); D['items'].append(dict(k='trk',L=i,net=t.GetNetname(),a=[mm(s.x),mm(s.y)],b=[mm(e.x),mm(e.y)],w=mm(t.GetWidth())))
# the bare heatsink pads: board-level shapes on B.Mask (tools/heatsink_pads.py), drawn on the B.Cu picture
for d in b.GetDrawings():
    if d.GetClass()=='PCB_SHAPE' and d.GetLayer()==pcbnew.B_Mask: D['items'].append(dict(k='mask',L=len(LAY)-1,net='',p=polys(d.GetPolyShape())))
for u in json.load(open(sys.argv[2]))['unconnected_items']:
    D['open'].append([[u['items'][0]['pos']['x'],u['items'][0]['pos']['y']],[u['items'][1]['pos']['x'],u['items'][1]['pos']['y']]])
json.dump(D,open(sys.argv[3],'w'))
print('items',len(D['items']),'open',len(D['open']))
