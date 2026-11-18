"""Quick look at STLs (offscreen VTK): python view.py out.png az el file1.stl[:r,g,b] ..."""
import sys
import numpy as np
import vtk


def render(files, out, az=30, el=20, size=(1000, 800), zoom=1.0, colors=None):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.83, 0.84, 0.86)
    ren.SetBackground2(0.97, 0.97, 0.98)
    ren.GradientBackgroundOn()
    for i, f in enumerate(files):
        r = vtk.vtkSTLReader()
        r.SetFileName(f)
        nm = vtk.vtkPolyDataNormals()
        nm.SetInputConnection(r.GetOutputPort())
        nm.SetFeatureAngle(35)
        mp = vtk.vtkPolyDataMapper()
        mp.SetInputConnection(nm.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(mp)
        c = (colors[i] if colors else (0.93, 0.93, 0.92))
        a.GetProperty().SetColor(*c[:3])
        if len(c) > 3:
            a.GetProperty().SetOpacity(c[3])
        a.GetProperty().SetSpecular(0.25)
        a.GetProperty().SetSpecularPower(30)
        a.GetProperty().SetDiffuse(0.8)
        a.GetProperty().SetAmbient(0.18)
        ren.AddActor(a)
    cam = ren.GetActiveCamera()
    cam.SetPosition(0, 0, 1)
    cam.SetViewUp(0, 1, 0)
    ren.ResetCamera()
    cam.Azimuth(az)
    cam.Elevation(el)
    cam.OrthogonalizeViewUp()
    ren.ResetCamera()
    cam.Zoom(zoom)
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.AddRenderer(ren)
    rw.SetSize(*size)
    rw.Render()
    w = vtk.vtkWindowToImageFilter()
    w.SetInput(rw)
    w.Update()
    p = vtk.vtkPNGWriter()
    p.SetFileName(out)
    p.SetInputConnection(w.GetOutputPort())
    p.Write()


if __name__ == '__main__':
    out, az, el = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    render(sys.argv[4:], out, az, el)
