"""Cut the old torso STEP (TORSO.step, 2026-11-05, old 150-wide cage) down to what the left shoulder sees, in the torso frame
(X outboard, Y up, Z forward, mm):

    PART=cage python torso_corner.py TORSO.step torso_cage_left.step         2020 cage corner and torso pitch mount
    PART=pitch_rs03 python torso_corner.py TORSO.step raw.step; python sew_solid.py raw.step torso_pitch_rs03_left.step
                                                                             the pitch RS03 as placed (open shells in TORSO.step, sewn)

The pitch RS03 moves outboard with the shoulder in the rev A frame, the cage does not, so they are separate references.
"""
import sys
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.TCollection import TCollection_ExtendedString
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import cadquery as cq
import os
PART = os.environ.get('PART', 'cage')   # 'cage': 2020 cage corner and pitch mount; 'pitch_rs03': the pitch RS03 only (NAUO5)

doc = TDocStd_Document(TCollection_ExtendedString('d'))
r = STEPCAFControl_Reader(); r.SetNameMode(True)
r.ReadFile(sys.argv[1]); r.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())


def name(l):
    a = TDataStd_Name()
    return a.Get().ToExtString() if l.FindAttribute(TDataStd_Name.GetID_s(), a) else '?'


keep = []


def walk(lab, loc, path):
    if st.IsAssembly_s(lab):
        seq = TDF_LabelSequence(); st.GetComponents_s(lab, seq)
        for i in range(1, seq.Length() + 1):
            c = seq.Value(i); ref = TDF_Label(); st.GetReferredShape_s(c, ref)
            walk(ref, loc.Multiplied(st.GetLocation_s(c)), path + [name(c)])
        return
    s = st.GetShape_s(lab).Moved(loc)
    b = Bnd_Box(); BRepBndLib.Add_s(s, b)
    if b.IsVoid():
        return
    x0, y0, z0, x1, y1, z1 = b.Get()
    # the corner of the cage round the left shoulder, the pitch mount and the pitch motor; clip long rails by their bbox only
    top = path[1] if len(path) > 1 else ''
    if top in ('NAUO1', 'NAUO8') or (PART == 'cage') == (top == 'NAUO5'):   # torso body and inner rail: not near the arm
        return
    if x1 > 20 and y1 > 330 and y0 < 540 and z0 < 150 and z1 > -150:
        keep.append(('/'.join(path), s, (x0, y0, z0, x1, y1, z1)))


roots = TDF_LabelSequence(); st.GetFreeShapes(roots)
for i in range(1, roots.Length() + 1):
    walk(roots.Value(i), TopLoc_Location(), [name(roots.Value(i))])
for p, s, b in keep:
    print(p, [round(v, 1) for v in b])
comp = cq.Compound.makeCompound([cq.Shape.cast(s) for _, s, _ in keep])
cq.exporters.export(cq.Workplane().add(comp), sys.argv[2])
print('kept', len(keep))
