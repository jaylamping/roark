import vtk, numpy as np, trimesh
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
UA='J:/code/roark-wt/left-arm-organic/cad/exports/upper-arm/'
TP='torso_parts/'
COL=dict(P1=(0.05,0.55,0.55),P2=(0.93,0.5,0.15),SPACER=(0.58,0.4,0.8),ROLL=(0.33,0.36,0.4),YAW=(0.33,0.36,0.4),
 PITCH=(0.33,0.36,0.4),HUB=(0.92,0.92,0.9),UA=(0.8,0.82,0.85),FRAME=(0.72,0.74,0.78),PBRK=(0.55,0.6,0.5))
def load_all(ua=True):
    d={}
    for k in ['P1','P2','SPACER','ROLL','YAW','HUB']: d[k]=trimesh.load(f'w/{k}.stl')
    d['PITCH']=trimesh.load(TP+'0037.stl'); d['PBRK']=trimesh.load(TP+'0038.stl')
    fr=[trimesh.load(TP+f'{i:04d}.stl') for i in (2,5,10,11,13,24,25,27,28,31,32,33,40)]
    d['FRAME']=trimesh.util.concatenate(fr)
    if ua:
        d['UA']=trimesh.util.concatenate([trimesh.load(UA+f) for f in ['upper_arm_organic_front_left.STL','upper_arm_organic_back_left.STL','upper_arm_organic_rs02_ring_left.STL']])
    return d
def poly(m):
    pts=vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices,dtype=float),deep=True))
    f=np.hstack([np.full((len(m.faces),1),3),m.faces]).astype(np.int64).ravel()
    ca=vtk.vtkCellArray(); ca.SetCells(len(m.faces),numpy_to_vtkIdTypeArray(f,deep=True))
    p=vtk.vtkPolyData(); p.SetPoints(pts); p.SetPolys(ca)
    n=vtk.vtkPolyDataNormals(); n.SetInputData(p); n.SetFeatureAngle(35); n.Update(); return n.GetOutput()
def render(items,out,pos,focal,up=(0,1,0),size=(1400,1000),scale=None,labels=()):
    r=vtk.vtkRenderer(); r.SetBackground(0.96,0.97,0.98)
    for m,c,*o in items:
        a=vtk.vtkActor(); mp=vtk.vtkPolyDataMapper(); mp.SetInputData(poly(m)); a.SetMapper(mp)
        a.GetProperty().SetColor(*c); a.GetProperty().SetSpecular(0.15); a.GetProperty().SetAmbient(0.25)
        if o: a.GetProperty().SetOpacity(o[0])
        r.AddActor(a)
    for txt,p,col in labels:
        t=vtk.vtkBillboardTextActor3D(); t.SetInput(txt); t.SetPosition(*p)
        tp=t.GetTextProperty(); tp.SetFontSize(22); tp.SetColor(*col); tp.SetBold(True); tp.SetBackgroundColor(1,1,1); tp.SetBackgroundOpacity(0.8)
        r.AddActor(t)
    cam=r.GetActiveCamera(); cam.SetPosition(*pos); cam.SetFocalPoint(*focal); cam.SetViewUp(*up)
    if scale: cam.ParallelProjectionOn(); cam.SetParallelScale(scale)
    r.ResetCameraClippingRange()
    w=vtk.vtkRenderWindow(); w.SetOffScreenRendering(1); w.AddRenderer(r); w.SetSize(*size); w.SetMultiSamples(8); w.Render()
    f=vtk.vtkWindowToImageFilter(); f.SetInput(w); f.Update()
    wr=vtk.vtkPNGWriter(); wr.SetFileName(out); wr.SetInputConnection(f.GetOutputPort()); wr.Write()
