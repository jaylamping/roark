import cadquery as cq, numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
T=np.array([[-1,0,0,97],[0,0,1,424.860667548201],[0,1,0,-0.0141253439872],[0,0,0,1]])
I='J:/code/roark-wt/shoulder-study/cad/reference/shoulder/'
for nm,src,rs in [('shoulder_pitch_bracket_left_l01.step',1,(3.05,4.8,5.5,6.0,2.25)),('shoulder_roll_bracket_left_l04b.step',1,(2.3,3.9,3.05,4.5,3.8)),('upper_arm_hub_left.step',0,(2.15,4.4,5.0))]:
    sh=cq.importers.importStep(I+nm); seen=set()
    for f in sh.val().Faces():
        a=BRepAdaptor_Surface(f.wrapped)
        if a.GetType()!=GeomAbs_Cylinder: continue
        r=round(a.Cylinder().Radius(),2)
        if r not in rs: continue
        bb=f.BoundingBox(); c=np.array([[bb.xmin,bb.ymin,bb.zmin,1],[bb.xmax,bb.ymax,bb.zmax,1]])
        if src: c=(T@c.T).T
        lo=np.minimum(c[0],c[1])[:3].round(1); hi=np.maximum(c[0],c[1])[:3].round(1)
        key=(r,tuple(lo),tuple(hi))
        if r in seen: continue
        seen.add(r); print(nm[:24],'r',r,'lo',lo.tolist(),'hi',hi.tolist())
