import sys, cadquery as cq, numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
T=np.array([[-1,0,0,97],[0,0,1,424.860667548201],[0,1,0,-0.0141253439872],[0,0,0,1]])
def W(p): return (T@np.r_[p,1])[:3]
def Wd(d): return T[:3,:3]@d
p=sys.argv[1]; rmin=float(sys.argv[2]) if len(sys.argv)>2 else 15
sh=cq.importers.importStep(p)
rows=[]
for s in sh.vals():
  for f in s.Faces():
    a=BRepAdaptor_Surface(f.wrapped)
    if a.GetType()==GeomAbs_Cylinder:
        c=a.Cylinder(); r=c.Radius()
        if r<rmin: continue
        ax=c.Axis(); d=np.array([ax.Direction().X(),ax.Direction().Y(),ax.Direction().Z()]); o=np.array([ax.Location().X(),ax.Location().Y(),ax.Location().Z()])
        bb=f.BoundingBox()
        dw=np.round(Wd(d),3); k=np.argmax(abs(dw))
        lo=W([bb.xmin,bb.ymin,bb.zmin])[k]; hi=W([bb.xmax,bb.ymax,bb.zmax])[k]
        ow=W(o)
        rows.append((round(r,2),'XYZ'[k],round(min(lo,hi),2),round(max(lo,hi),2),np.round(ow,2).tolist(),round(f.Area(),0)))
for r in sorted(set((x[0],x[1],x[2],x[3],tuple(x[4])) for x in rows)): print(r)
