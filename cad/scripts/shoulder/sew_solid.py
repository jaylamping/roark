"""Sew a STEP made of open shells (the pitch RS03 in TORSO.step) into closed solids, so SolidWorks imports solid bodies.

    python sew_solid.py IN.step OUT.step
"""
import sys

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
from OCP.ShapeFix import ShapeFix_Solid
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

s = cq.importers.importStep(sys.argv[1])
sew = BRepBuilderAPI_Sewing(0.01)
for f in s.faces().vals():
    sew.Add(f.wrapped)
sew.Perform()
sh = sew.SewedShape()
solids = []
ex = TopExp_Explorer(sh, TopAbs_SHELL)
while ex.More():
    mk = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(ex.Current()))
    fx = ShapeFix_Solid(mk.Solid())
    fx.Perform()
    so = cq.Solid(fx.Solid())
    if so.isValid() and abs(so.Volume()) > 1:
        solids.append(so)
    ex.Next()
print('solids', len(solids), 'volume', round(sum(abs(x.Volume()) for x in solids)))
cq.exporters.export(cq.Workplane().add(cq.Compound.makeCompound(solids)), sys.argv[2])
