"""stitch_pads.py in.kicad_pcb out.kicad_pcb REF PAD[,PAD...] (KiCad Python): join each listed GND pad of REF to the GND
planes with a short 0.25 mm F.Cu stub along the pad's long axis and a 0.6/0.3 via just past the pad end, at the first
spot finish_route's exact rules accept (0.35 to 2.0 mm past the pad, either direction). Prints what it placed."""
import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import finish_route as FR, pcbnew
r=FR.Router(sys.argv[1]); fp=r.b.FindFootprintByReference(sys.argv[3]); want=set(sys.argv[4].split(','))
I=pcbnew.ToMM; placed=[]
for p in fp.Pads():
    if p.GetNumber() not in want: continue
    n=p.GetNetname(); c=(I(p.GetPosition().x),I(p.GetPosition().y))
    bb=p.GetBoundingBox(); w,h=I(bb.GetWidth()),I(bb.GetHeight())
    axis=(1,0) if w>=h else (0,1); half=max(w,h)/2
    done=False
    for d in [x/20 for x in range(7,41)]:
        for sgn in (-1,1):
            q=(round(c[0]+sgn*axis[0]*(half+d),3),round(c[1]+sgn*axis[1]*(half+d),3))
            if r.via(n,q) and r.seg(n,FR.CU[0],c,q):
                r.commit(n,[('t',FR.CU[0],[c,q]),('v',q)]); placed.append((p.GetNumber(),q)); done=True; break
        if done: break
    if not done: placed.append((p.GetNumber(),None))
r.save(sys.argv[2]); print('stitched',placed)
