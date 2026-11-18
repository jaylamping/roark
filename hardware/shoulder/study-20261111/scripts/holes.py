import sys, cadquery as cq, numpy as np, collections
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
T=np.array([[-1,0,0,97],[0,0,1,424.860667548201],[0,1,0,-0.0141253439872],[0,0,0,1]])
AX={'x':(0,(424.86,-0.014)),'z':(2,(170.49,424.86)),'y':(1,(170.49,5.99))}
def run(path,src):
    sh=cq.importers.importStep(path); res=collections.defaultdict(set)
    for f in sh.val().Faces():
        a=BRepAdaptor_Surface(f.wrapped)
        if a.GetType()!=GeomAbs_Cylinder: continue
        c=a.Cylinder(); r=c.Radius()
        if r>6: continue
        ax=c.Axis(); d=np.array([ax.Direction().X(),ax.Direction().Y(),ax.Direction().Z()]); o=np.array([ax.Location().X(),ax.Location().Y(),ax.Location().Z()])
        if src: d=T[:3,:3]@d; o=(T@np.r_[o,1])[:3]
        k=int(np.argmax(abs(d))); 
        if abs(d[k])<0.99: continue
        name='xyz'[k]; i,cc=AX[name]; oth=[j for j in range(3) if j!=i]
        rr=np.hypot(o[oth[0]]-cc[0],o[oth[1]]-cc[1]); ang=np.degrees(np.arctan2(o[oth[1]]-cc[1],o[oth[0]]-cc[0]))
        bb=f.BoundingBox()
        res[(name,round(r,2),round(rr,1))].add(round(ang/2)*2)
    for k,v in sorted(res.items()):
        if len(v)>=2: print('  axis',k[0],'hole r',k[1],'circle R',k[2],'n',len(v),sorted(v))
I='J:/code/roark-wt/shoulder-study/cad/reference/shoulder/'
for nm,src in [('shoulder_pitch_bracket_left_l01.step',1),('shoulder_roll_bracket_left_l04b.step',1),('shoulder_roll_spacer_left_pf03.step',1),('upper_arm_hub_left.step',0)]:
    print(nm); run(I+nm,src)
