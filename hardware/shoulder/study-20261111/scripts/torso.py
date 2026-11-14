# Extract torso STEP components near the left shoulder, with names, to STL (world frame).
import json, time
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.TCollection import TCollection_ExtendedString
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import cadquery as cq
t=time.time()
doc=TDocStd_Document(TCollection_ExtendedString("d"))
r=STEPCAFControl_Reader(); r.SetNameMode(True)
r.ReadFile(r'C:\Users\joeyl\Documents\Codex\2026-10-29\task\LEFT_ARM_V1_LAYOUT_20261106\inputs\TORSO.step'); r.Transfer(doc)
st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
print('read',time.time()-t,flush=True)
out=[]
def name(l):
    a=TDataStd_Name()
    return a.Get().ToExtString() if l.FindAttribute(TDataStd_Name.GetID_s(),a) else '?'
def walk(lab,loc,path):
    if st.IsReference_s(lab):
        ref=st.GetReferredShape_s(lab) if False else None
    if st.IsAssembly_s(lab):
        seq=TDF_LabelSequence(); st.GetComponents_s(lab,seq)
        for i in range(1,seq.Length()+1):
            c=seq.Value(i); l2=loc.Multiplied(st.GetLocation_s(c))
            from OCP.TDF import TDF_Label
            ref=TDF_Label(); st.GetReferredShape_s(c,ref)
            walk(ref,l2,path+[name(c)])
    else:
        s=st.GetShape_s(lab).Moved(loc)
        b=Bnd_Box(); BRepBndLib.Add_s(s,b)
        if b.IsVoid(): return
        x0,y0,z0,x1,y1,z1=b.Get()
        out.append(dict(path='/'.join(path),bb=[x0,y0,z0,x1,y1,z1],shape=s))
roots=TDF_LabelSequence(); st.GetFreeShapes(roots)
for i in range(1,roots.Length()+1): walk(roots.Value(i),TopLoc_Location(),[name(roots.Value(i))])
print('leaves',len(out),time.time()-t,flush=True)
meta=[]
import os
os.makedirs('torso_parts',exist_ok=True)
for k,o in enumerate(out):
    x0,y0,z0,x1,y1,z1=o['bb']
    near = x1>20 and y1>330 and y0<540
    meta.append(dict(i=k,path=o['path'],bb=o['bb'],near=near))
    if near:
        try:
            cq.Shape.cast(o['shape']).exportStl(f'torso_parts/{k:04d}.stl',tolerance=0.1,angularTolerance=0.2)
        except Exception as e: print('fail',k,e)
json.dump(meta,open('torso_meta.json','w'),indent=0)
print('done',time.time()-t)
