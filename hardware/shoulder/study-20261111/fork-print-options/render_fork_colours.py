"""Colour options for the fork front and fork rear, on the assembled left shoulder with the outer body shell.

    python render_fork_colours.py        (under cad/scripts/shoulder/capped.py)

Fixed by Joey's colour rule of 2026-11-15: hub black, pitch loop cover (the band seen through the shell's opening) black,
shell white. Shown here as undecided parts in white: drum, flange ring, rear cap. Motors dark, upper arm white.
Options: A fork front and fork rear black; B both white; C fork front white, fork rear black.

Inputs: the parts' STLs (cad/_wip/shoulder-pass1/stl, as check_clearance.py reads them), motors and upper arm from git,
the rev A frame (FRAME_STEP, torso_frame.step) and the outer shell panels of 2026-11-06 (SHELL_DIR, marengo
cad/exports/shell/marengo_shell_*.STL), with the r 80 shoulder opening of option A drawn in by leaving out the triangles
inside it, as render_shoulder_with_shell.py does.
"""
import glob
import os
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / 'cad' / 'scripts' / 'shoulder'))
from build_asm import FRAME_SHIFT, T_ROLL_RS03, T_RS02  # noqa: E402
from check_clearance import FRAME_STEP, STL, UA, VENDOR, mesh_step, named_solids, need, tess  # noqa: E402
from dims import *  # noqa: E402

OUT = HERE.parent
SHELL_DIR = os.environ.get('SHELL_DIR', 'J:/code/marengo/cad/exports/shell')
T_SHELL = np.array([[0, 1, 0, -38.0], [0, 0, 1, -810.14], [1, 0, 0, 0], [0, 0, 0, 1.0]])      # marengo shell -> shoulder coordinates
WHITE, BLACK, DARK, FRAMEC, SHELLW = (0.94, 0.94, 0.92), (0.085, 0.085, 0.095), (0.27, 0.28, 0.30), (0.55, 0.57, 0.60), (0.97, 0.97, 0.96)
SIZE = (1800, 1800)


def font(sz, bold=False):
    try:
        return ImageFont.truetype('arialbd.ttf' if bold else 'arial.ttf', sz)
    except OSError:
        return ImageFont.load_default(size=sz)


def outer_shell(open_r=80.0):
    files = [f for f in sorted(glob.glob(str(Path(SHELL_DIR) / 'marengo_shell_*.STL')))
             if not Path(f).name.split('marengo_shell_')[-1].startswith(('bracket', 'coupon', 'screw', 'collar'))]
    if not files:
        raise SystemExit(f'no shell panels in {SHELL_DIR}: set SHELL_DIR')
    m = trimesh.util.concatenate([trimesh.load(f) for f in files])
    m.apply_transform(T_SHELL)
    v = m.vertices
    r = np.hypot(v[:, 1] - RY, v[:, 2] - PZ)
    inside = (r < open_r) & (v[:, 0] > 40.0)                    # the left socket's floor and inner cone
    return trimesh.Trimesh(v, m.faces[~inside[m.faces].all(axis=1)], process=False)


def frame():
    fr = []
    for nm, sh in named_solids(need(FRAME_STEP, 'rev A frame: set FRAME_STEP')):
        if nm.startswith(('actuator__rs03', 'shellpart')):
            continue
        fr.append(tess(sh, 0.5))
    m = trimesh.util.concatenate(fr)
    m.apply_translation((-FRAME_SHIFT, 0, 0))
    return m


def render(items, out, eye, focal, size=SIZE, angle=28.0):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.80, 0.82, 0.85); ren.SetBackground2(0.96, 0.97, 0.98); ren.GradientBackgroundOn()
    for m, col, op in items:
        pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices, float), deep=True))
        cells = vtk.vtkCellArray()
        cells.SetCells(len(m.faces), numpy_to_vtkIdTypeArray(np.hstack([np.full((len(m.faces), 1), 3), m.faces]).astype(np.int64).ravel(), deep=True))
        pd = vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(cells)
        nm = vtk.vtkPolyDataNormals(); nm.SetInputData(pd); nm.SetFeatureAngle(35); nm.ConsistencyOn()
        mp = vtk.vtkPolyDataMapper(); mp.SetInputConnection(nm.GetOutputPort())
        a = vtk.vtkActor(); a.SetMapper(mp)
        pr = a.GetProperty(); pr.SetColor(*col); pr.SetOpacity(op)
        dark = sum(col) < 1.0
        pr.SetSpecular(0.45 if dark else 0.22); pr.SetSpecularPower(22 if dark else 30); pr.SetDiffuse(0.85); pr.SetAmbient(0.28 if dark else 0.2)
        ren.AddActor(a)
        if col in (WHITE, BLACK, SHELLW):       # thin feature edges on the printed parts and the shell
            fe = vtk.vtkFeatureEdges(); fe.SetInputData(pd); fe.BoundaryEdgesOff(); fe.ManifoldEdgesOff(); fe.NonManifoldEdgesOff(); fe.SetFeatureAngle(40)
            em = vtk.vtkPolyDataMapper(); em.SetInputConnection(fe.GetOutputPort()); em.ScalarVisibilityOff()
            ea = vtk.vtkActor(); ea.SetMapper(em)
            ea.GetProperty().SetColor(*((0.42, 0.43, 0.46) if dark else (0.45, 0.46, 0.48))); ea.GetProperty().SetLineWidth(1.6)
            ea.GetProperty().SetOpacity(0.7 * op)
            ren.AddActor(ea)
    ren.SetUseDepthPeeling(1)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*focal); cam.SetPosition(*eye); cam.SetViewUp(0, 1, 0); cam.SetViewAngle(angle); ren.ResetCameraClippingRange()
    rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetAlphaBitPlanes(1); rw.SetMultiSamples(8); rw.AddRenderer(ren); rw.SetSize(*size)
    rw.Render()
    w = vtk.vtkWindowToImageFilter(); w.SetInput(rw); w.Update()
    pw = vtk.vtkPNGWriter(); pw.SetFileName(str(out)); pw.SetInputConnection(w.GetOutputPort()); pw.Write()
    return Image.open(out).convert('RGB')


def titled(im, text, sub=None):
    d = ImageDraw.Draw(im)
    f = font(54, True)
    w = d.textlength(text, font=f)
    d.rectangle((24, 22, 24 + w + 28, 22 + 78), fill=(255, 255, 255), outline=(110, 110, 110), width=2)
    d.text((38, 30), text, fill=(20, 20, 20), font=f)
    if sub:
        f2 = font(36)
        w2 = d.textlength(sub, font=f2)
        d.rectangle((24, 108, 24 + w2 + 28, 108 + 56), fill=(255, 255, 255), outline=(150, 150, 150))
        d.text((38, 116), sub, fill=(40, 40, 40), font=f2)
    return im


def main():
    print('loading', flush=True)
    P = {k: trimesh.load(need(STL / f'{k}.stl', f'part STL "{k}"')) for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'hub', 'cover', 'port_cap')}
    M = dict(roll_rs03=mesh_step(VENDOR / 'vendor_robstride_rs03.stp', T_ROLL_RS03, tol=0.2), rs02=mesh_step(VENDOR / 'vendor_robstride_rs02.step', T_RS02, tol=0.2),
             pitch_rs03=mesh_step(UA / 'torso_pitch_rs03_left.step', tol=0.4))
    arm = {n: mesh_step(UA / f'upper_arm_organic_{n}_left.step', tol=0.25) for n in ('front', 'back', 'rs02_ring')}
    for m in arm.values():
        m.apply_translation((0.0, -HUB_ARM_DROP, 0.0))          # hub rev E1: the arm hangs this much lower than its exports
    sh, fr = outer_shell(), frame()
    opts = [('a_fork_black', 'A  Fork black', 'fork front and fork rear black', BLACK, BLACK),
            ('b_fork_white', 'B  Fork white', 'fork front and fork rear white', WHITE, WHITE),
            ('c_front_white_rear_black', 'C  Front white, rear black', 'fork front white, fork rear black', WHITE, BLACK)]
    F = np.array([RX - 20.0, RY - 45.0, 0.0])
    views = [('front', 'front three-quarter', F + np.array([330.0, 110.0, 440.0]), F, 27, True),
             ('rear', 'rear three-quarter', F + np.array([300.0, 90.0, -470.0]), F + np.array([0.0, 0.0, -10.0]), 27, True),
             ('front_no_shell', 'front, shell left out', F + np.array([330.0, 110.0, 440.0]), F, 27, False),
             ('rear_no_shell', 'rear, shell left out', F + np.array([300.0, 90.0, -470.0]), F + np.array([0.0, 0.0, -10.0]), 27, False)]
    sheet = {}
    for tag, name, sub, cf, cr in opts:
        col = dict(drum=WHITE, ring=WHITE, cap=WHITE, port_cap=WHITE, fork_front=cf, fork_rear=cr, hub=BLACK, cover=BLACK)
        base = [(m, col[k], 1.0) for k, m in P.items()] + [(m, DARK, 1.0) for m in M.values()]
        base += [(m, WHITE if n != 'rs02_ring' else DARK, 1.0) for n, m in arm.items()]
        for vt, vname, eye, foc, ang, shell in views:
            it = base + ([(sh, SHELLW, 1.0)] if shell else [(fr, FRAMEC, 1.0)])
            p = OUT / f'fork_colour_{tag}_{vt}.png'
            im = titled(render(it, p, eye, foc, angle=ang), name, f'{sub}; {vname}')
            if shell:
                im.save(p, optimize=True)
            else:
                p.unlink()          # the views without the shell are kept on the sheet only
            sheet[(tag, vt)] = im
            print(p.name, flush=True)
    # one sheet: columns = options, rows = views
    g, w, h = 20, SIZE[0], SIZE[1]
    head = 150
    S = Image.new('RGB', (3 * w + 4 * g, head + 4 * h + 5 * g), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.rectangle((0, 0, S.width, head), fill=(32, 60, 110))
    d.text((30, 22), 'Left shoulder: colour options for the fork front and fork rear', fill=(255, 255, 255), font=font(64, True))
    d.text((30, 98), 'Fixed: hub and pitch loop cover black, shell white. Shown white, not decided: drum, flange ring, rear cap. Motors dark, upper arm white. '
                     'Shell: outer panels of 2026-11-06 with the r 80 opening drawn in.', fill=(215, 225, 240), font=font(30))
    for c, (tag, *_r) in enumerate(opts):
        for r_, (vt, *_v) in enumerate(views):
            S.paste(sheet[(tag, vt)], (g + c * (w + g), head + g + r_ * (h + g)))
    S = S.resize((S.width // 2, S.height // 2), Image.LANCZOS)
    S.save(OUT / 'fork_colour_options.png', optimize=True)
    print('saved fork_colour_options.png', S.size)


if __name__ == '__main__':
    main()
