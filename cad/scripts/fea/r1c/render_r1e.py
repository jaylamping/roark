"""R1e hub end for Joey (2026-11-12): the closed upper arm's hub end on the rev D hub with a mid-size shim ring, all plain white;
front and back three-quarter views and a close-up of the shadow line where the ring sits. Offscreen VTK.
    python render_r1e.py FRONT_STL BACK_STL HUB_STL OUT_DIR [ring_t=0.70]      (run under capped.py)"""
import sys
from pathlib import Path

import numpy as np
import trimesh

HX, CZ = 170.49, 5.985875
WHITE = (0.94, 0.94, 0.93)


def render(meshes, eye, focus, out, angle=20.0, size=(1400, 1000), reset=True, zoom=1.0):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.80, 0.81, 0.83)
    ren.SetBackground2(0.97, 0.97, 0.98)
    ren.GradientBackgroundOn()
    for m in meshes:
        pts = vtk.vtkPoints()
        pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices, float), deep=True))
        cells = vtk.vtkCellArray()
        cells.SetCells(len(m.faces), numpy_to_vtkIdTypeArray(np.hstack([np.full((len(m.faces), 1), 3), m.faces]).astype(np.int64).ravel(), deep=True))
        pd = vtk.vtkPolyData()
        pd.SetPoints(pts)
        pd.SetPolys(cells)
        nf = vtk.vtkPolyDataNormals()
        nf.SetInputData(pd)
        nf.SetFeatureAngle(32)
        nf.SplittingOn()
        mp = vtk.vtkPolyDataMapper()
        mp.SetInputConnection(nf.GetOutputPort())
        mp.ScalarVisibilityOff()
        a = vtk.vtkActor()
        a.SetMapper(mp)
        p = a.GetProperty()
        p.SetColor(*WHITE)
        p.SetAmbient(0.18)
        p.SetDiffuse(0.78)
        p.SetSpecular(0.25)
        p.SetSpecularPower(30)
        ren.AddActor(a)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*focus)
    cam.SetPosition(*eye)
    cam.SetViewUp(0, 1, 0)
    cam.SetViewAngle(angle)
    if reset:
        ren.ResetCamera()
    cam.SetFocalPoint(*focus)
    cam.Zoom(zoom)
    ren.ResetCameraClippingRange()
    lk = vtk.vtkLightKit()
    lk.SetKeyLightIntensity(0.85)
    lk.AddLightsToRenderer(ren)
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.AddRenderer(ren)
    rw.SetSize(*size)
    rw.SetMultiSamples(8)
    rw.Render()
    w = vtk.vtkWindowToImageFilter()
    w.SetInput(rw)
    w.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(str(out))
    wr.SetInputConnection(w.GetOutputPort())
    wr.Write()


if __name__ == '__main__':
    front, back, hub = (trimesh.load(f) for f in sys.argv[1:4])
    out = Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    t = float(sys.argv[5]) if len(sys.argv) > 5 else 0.70
    ring = trimesh.creation.annulus(36.2, 38.4, t, sections=256)
    ring.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    ring.apply_translation((HX, 302.0 - t / 2, CZ))
    # only the hub end of the halves (Y > 255): quicker, and the views are about the joint
    halves = [trimesh.intersections.slice_mesh_plane(m, [0, 1, 0], [0, 255.0, 0], cap=True) for m in (front, back)]
    meshes = halves + [hub, ring]
    focus = (HX, 300.0, CZ)
    render(meshes, (HX + 170, 345, CZ + 190), focus, out / 'r1e_hub_end_front.png', zoom=1.25)
    render(meshes, (HX - 170, 345, CZ - 190), focus, out / 'r1e_hub_end_back.png', zoom=1.25)
    a = np.radians(60.0)      # close-up of the shadow line on the front half
    p0 = np.array([HX + 38.9 * np.cos(a), 301.65, CZ + 38.9 * np.sin(a)])
    d = np.array([np.cos(a), -0.12, np.sin(a)])
    render(meshes, tuple(p0 + 80 * d), tuple(p0), out / 'r1e_shadow_line_closeup.png', angle=15.0, reset=False, size=(1200, 900))
    print('rendered', list(out.glob('r1e_*.png')))
