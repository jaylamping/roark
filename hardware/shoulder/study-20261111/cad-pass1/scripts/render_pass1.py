"""Pictures of the left shoulder, first SolidWorks pass (roll drum and fork).

    python render_pass1.py [OUTDIR]

Inputs: STL exports of the SolidWorks parts (cad/_wip/shoulder-pass1/stl, written by build_parts.py), the vendor motors
placed as in build_asm.py, the pitch RS03, the frozen upper arm, the rev A frame (J:/code/_transfer/shoulder/torso_frame.step,
moved -38 X into the old-frame coordinates of the parts) and today's shoulder (cad/reference/shoulder) for the comparison.
"""
import math
import sys
from pathlib import Path

import matplotlib
import numpy as np
import trimesh

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve()
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO / 'cad' / 'scripts' / 'shoulder'))
from build_asm import T_ROLL_RS03, T_RS02, T_BRG, FRAME_SHIFT  # noqa: E402
from check_clearance import named_solids, tess  # noqa: E402
from dims import *  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1]
STL = REPO / 'cad' / '_wip' / 'shoulder-pass1' / 'stl'
REF = REPO / 'cad' / 'reference' / 'shoulder'
WHITE, CAPC, DARK, GREY, FRAMEC = (0.93, 0.93, 0.91), (0.86, 0.87, 0.88), (0.24, 0.25, 0.27), (0.72, 0.73, 0.75), (0.58, 0.60, 0.63)
STEEL, RED, BLUE, OLDC = (0.78, 0.79, 0.81), (0.85, 0.12, 0.10), (0.12, 0.30, 0.85), (0.93, 0.62, 0.30)
FONT = ImageFont.load_default(size=26)


def step_mesh(path, M=None, tol=0.2):
    import cadquery as cq
    s = cq.importers.importStep(str(path))
    m = trimesh.util.concatenate([tess(x, tol) for x in s.solids().vals()])
    if M is not None:
        m.apply_transform(M)
    return m


SRC = np.array([[-1, 0, 0, 97], [0, 0, 1, 424.860667548201], [0, 1, 0, -0.0141253439872], [0, 0, 0, 1]], float)   # left source -> torso
print('loading', flush=True)
P = {k: trimesh.load(STL / f'{k}.stl') for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'fork_cap', 'hub', 'cover')}
brg = trimesh.creation.annulus(r_min=20.0, r_max=26.0, height=7.0, sections=96)
brg.apply_translation((RX, RY, (BRG_Z[0] + BRG_Z[1]) / 2))
M = dict(roll_rs03=step_mesh(REPO / 'cad/vendor/robstride/vendor_robstride_rs03.stp', T_ROLL_RS03),
         rs02=step_mesh(REPO / 'cad/vendor/robstride/vendor_robstride_rs02.step', T_RS02),
         pitch_rs03=step_mesh(REF / 'torso_pitch_rs03_left.step', tol=0.4), bearing=brg)
UA = {n: step_mesh(REF / f'upper_arm_organic_{n}_left.step', tol=0.25) for n in ('front', 'back', 'rs02_ring')}
fr = []
for nm, sh in named_solids(r'J:/code/_transfer/shoulder/torso_frame.step'):
    bb = sh.BoundingBox()
    if bb.xmax < 40 or bb.ymax < 300 or bb.ymin > 520 or nm.startswith('actuator__rs03') or nm.startswith('shellpart') or nm.startswith('fastener__c1_'):
        continue
    fr.append(tess(sh, 0.4))
FRAME = trimesh.util.concatenate(fr)
FRAME.apply_translation((-FRAME_SHIFT, 0, 0))
TODAY = dict(p1=step_mesh(REF / 'shoulder_pitch_bracket_left_l01.step', SRC), p2=step_mesh(REF / 'shoulder_roll_bracket_left_l04b.step', SRC),
             spacer=step_mesh(REF / 'shoulder_roll_spacer_left_pf03.step', SRC), hub=step_mesh(REF / 'upper_arm_hub_left.step'))

COL = dict(drum=WHITE, ring=WHITE, cap=WHITE, fork_front=WHITE, fork_rear=WHITE, fork_cap=CAPC, hub=WHITE, cover=GREY,
           roll_rs03=DARK, rs02=DARK, pitch_rs03=DARK, bearing=STEEL)


def cable_paths():
    """Centre lines of the power and signal passages (old-frame coordinates), from the feed to the hub window or the RS02 tap."""
    f = FEED
    loop = np.linspace(math.pi, 0.25, 30)

    def route(off, rl):
        p = [(f['x_rise'], f['y0'], off), (f['x_rise'], f['y_run'], off), (f['x_up'], f['y_run'], off), (f['x_up'], RY - rl, off)]
        p += [(f['x_up'] + 6 * (1 - a / math.pi), RY - rl * math.cos(a), rl * math.sin(a)) for a in loop]   # round the pitch housing
        p += [(101.0, TRUNK_Y, off), (TRUNK_X, TRUNK_Y, off), (TRUNK_X, TRUNK_Y, CAPZ)]
        return p
    pw = route(P_OFF, 66.0) + [(RX, RY + 4.5, CAPZ), (RX, RY + 4.5, RZ), (RX + P_OFF, 400, RZ), (RX + P_OFF, Y_EX, RZ), (RX - 6, Y_EX, YZ - 37),
                               (RX - 25, Y_EX, YZ - 20), (RX - 31, Y_EX, YZ + 5), (RX - 18, Y_EX, YZ + 25), (RX + 25, 317, YZ + 4),
                               (RX + 20, 300, YZ + 3), (RX, 280, YZ)]
    sg = route(S_OFF, 60.0) + [(RX, RY - 3.5, CAPZ), (RX, RY - 3.5, RZ), (RX + S_OFF, 400, RZ), (RX + S_OFF, SEAT_Y[0] + 5, RZ),
                               (RX + 3, SEAT_Y[0] + 5, RZ), (RX + P_OFF, SEAT_Y[0] + 3, RZ)]
    return np.array(pw, float), np.array(sg, float)


def tube(pts, r):
    parts = []
    for a, b in zip(pts[:-1], pts[1:]):
        if np.linalg.norm(np.subtract(b, a)) > 1e-6:
            parts.append(trimesh.creation.cylinder(radius=r, segment=np.array([a, b]), sections=10))
    for p in pts:
        s = trimesh.creation.icosphere(subdivisions=1, radius=r)
        s.apply_translation(p)
        parts.append(s)
    return trimesh.util.concatenate(parts)


def render(items, out, eye, focal, up=(0, 1, 0), size=(1600, 1200), angle=28.0, title=None):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.83, 0.84, 0.86); ren.SetBackground2(0.98, 0.98, 0.99); ren.GradientBackgroundOn()
    for m, col, op in items:
        pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices, float), deep=True))
        cells = vtk.vtkCellArray()
        cells.SetCells(len(m.faces), numpy_to_vtkIdTypeArray(np.hstack([np.full((len(m.faces), 1), 3), m.faces]).astype(np.int64).ravel(), deep=True))
        pd = vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(cells)
        nm = vtk.vtkPolyDataNormals(); nm.SetInputData(pd); nm.SetFeatureAngle(35); nm.ConsistencyOn()
        mp = vtk.vtkPolyDataMapper(); mp.SetInputConnection(nm.GetOutputPort())
        a = vtk.vtkActor(); a.SetMapper(mp)
        pr = a.GetProperty(); pr.SetColor(*col); pr.SetOpacity(op); pr.SetSpecular(0.25); pr.SetSpecularPower(30); pr.SetDiffuse(0.8); pr.SetAmbient(0.2)
        ren.AddActor(a)
        if col in (WHITE, CAPC, GREY):          # thin feature edges, as in the organic arm pictures
            fe = vtk.vtkFeatureEdges(); fe.SetInputData(pd); fe.BoundaryEdgesOff(); fe.ManifoldEdgesOff(); fe.NonManifoldEdgesOff(); fe.SetFeatureAngle(40)
            em = vtk.vtkPolyDataMapper(); em.SetInputConnection(fe.GetOutputPort()); em.ScalarVisibilityOff()
            ea = vtk.vtkActor(); ea.SetMapper(em); ea.GetProperty().SetColor(0.45, 0.46, 0.48); ea.GetProperty().SetLineWidth(1.0); ea.GetProperty().SetOpacity(0.6 * op)
            ren.AddActor(ea)
    ren.SetUseDepthPeeling(1)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*focal); cam.SetPosition(*eye); cam.SetViewUp(*up); cam.SetViewAngle(angle); ren.ResetCameraClippingRange()
    rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetAlphaBitPlanes(1); rw.SetMultiSamples(0); rw.AddRenderer(ren); rw.SetSize(*size)
    rw.Render()
    w = vtk.vtkWindowToImageFilter(); w.SetInput(rw); w.Update()
    pw = vtk.vtkPNGWriter(); pw.SetFileName(str(out)); pw.SetInputConnection(w.GetOutputPort()); pw.Write()
    if title:
        im = Image.open(out).convert('RGB'); d = ImageDraw.Draw(im); d.text((24, 20), title, fill=(20, 20, 20), font=FONT); im.save(out)


def shoulder_items(offsets=None, with_arm=True, with_frame=True, cover=True, op=1.0):
    off = offsets or {}

    def mv(k, m):
        if k in off:
            m = m.copy(); m.apply_translation(off[k])
        return m
    items = [(mv(k, m), COL[k], op) for k, m in P.items() if cover or k != 'cover']
    items += [(mv(k, m), COL[k], 1.0) for k, m in M.items()]
    if with_arm:
        items += [(mv('arm', m), (0.95, 0.95, 0.93) if n != 'rs02_ring' else DARK, 1.0) for n, m in UA.items()]
    if with_frame:
        items.append((FRAME, FRAMEC, 1.0))
    return items


def main():
    F = np.array([RX - 25, RY - 40, 0.0])
    eye_front = F + np.array([420.0, 90.0, 560.0])
    render(shoulder_items(), OUT / 'P1_look_front_outboard.png', eye_front, F, title='Left shoulder, first SolidWorks pass, dressed: front-outboard, neutral, frozen upper arm, rev A frame')
    eye_back = F + np.array([380.0, 140.0, -560.0])
    render(shoulder_items(), OUT / 'P2_back.png', eye_back, F, title='Back: rear cap with the stub, stop lugs (roll -11 / +110), fork rear cheek')
    ex = dict(cover=(-45, 0, 0), ring=(-25, 0, 0), roll_rs03=(0, 0, -95), cap=(0, 0, -150), bearing=(0, 0, -185), fork_rear=(0, 0, -215),
              fork_front=(35, -30, 95), fork_cap=(35, -30, 135), rs02=(35, -75, 95), hub=(35, -125, 95), arm=(35, -175, 95))
    Fe = np.array([RX, RY - 70, -20.0])
    render(shoulder_items(ex, with_frame=False), OUT / 'P3_exploded.png', Fe + np.array([700.0, 260.0, 600.0]), Fe + np.array([-20.0, -60.0, -40.0]), size=(1600, 1700), angle=40,
           title='Exploded: cover and flange ring, drum, roll RS03 out to the rear, cap, 6808, fork rear; fork front with RS02, hub, arm')
    # section through the roll axis, sagittal plane X = RX, with the cable path
    fig, ax = plt.subplots(figsize=(9, 11), dpi=180)
    pw, sg = cable_paths()
    items = [(m, COL[k], k) for k, m in P.items()] + [(m, COL[k], k) for k, m in M.items() if k != 'pitch_rs03'] + \
            [(m, (0.95, 0.95, 0.93), n) for n, m in UA.items()]
    for m, col, k in items:
        s = m.section(plane_origin=(RX, 0, 0), plane_normal=(1, 0, 0))
        if s is None:
            continue
        for e in s.discrete:
            ax.add_patch(MPoly(e[:, [2, 1]], closed=True, fc=col if col != WHITE else (0.90, 0.90, 0.87), ec='#2a2d31', lw=0.45, zorder=2))
    for path, col, nm in ((pw[35:], RED, 'power 16 x 6'), (sg[35:], BLUE, 'signal 10 x 5')):   # from the trunk on (the feed and pitch loop are far off this plane)
        ax.plot(path[:, 2], path[:, 1], color=col, lw=2.2, zorder=4, label=f'{nm} passage (centre line, projected)')
    lab = [((BRG_Z[0] - 3.5, RY + 23), '6808-2RS 40x52x7\n(floating, on the cap stub)', (-120, 470)),
           ((CAPZ, RY + 30), 'cap radial channel', (-120, 510)), ((-43, RY), 'stub OD 40, bore 25', (-125, 430)),
           ((RZ, 395), 'fork rear arm channels', (-125, 380)), ((YZ - 30, Y_EX), 'yaw exit under the RS02', (-125, 330)),
           ((YZ + 20, 316), 'hub dish and window into the arm', (60, 300)), ((ROLL_OUT + 4, RY + 20), 'fork front boss on the roll output', (55, 470)),
           ((-10, RY + 30), 'roll RS03 in the drum', (30, 520)), ((5, 340), 'yaw RS02', (60, 350))]
    for xy, t, to in lab:
        ax.annotate(t, xy, to, fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5), zorder=5)
    ax.axhline(RY, color='#999', lw=0.4, ls='--'); ax.axvline(YZ, color='#999', lw=0.4, ls=':')
    ax.set_xlim(-130, 110); ax.set_ylim(250, 540); ax.set_aspect('equal')
    ax.set_xlabel('Z (forward, mm)'); ax.set_ylabel('Y (up, mm)')
    ax.legend(loc='lower left', fontsize=8)
    ax.set_title('Section X = 170.49 through the roll axis (old-frame coordinates), seen from outboard', fontsize=10, loc='left')
    fig.savefig(OUT / 'P4_section_roll_axis.png', bbox_inches='tight', pad_inches=0.15); plt.close(fig)
    # side by side with today's shoulder (same camera)
    today = [(m, OLDC if k != 'hub' else WHITE, 1.0) for k, m in TODAY.items()] + [(M['roll_rs03'], DARK, 1.0), (M['rs02'], DARK, 1.0), (M['pitch_rs03'], DARK, 1.0),
                                                                                   (FRAME, FRAMEC, 1.0)] + [(m, (0.95, 0.95, 0.93) if n != 'rs02_ring' else DARK, 1.0) for n, m in UA.items()]
    for nm, items, t in (('today', today, "Today: P1 L01, PF03 spacer, P2 L04B, hub (orange: today's printed parts)"),
                         ('new', shoulder_items(), 'First SolidWorks pass: roll drum and fork')):
        for view, eye in (('front', eye_front), ('back', eye_back)):
            render(items, OUT / f'_{nm}_{view}.png', eye, F, size=(1200, 1000), title=t)
    rows = []
    for view in ('front', 'back'):
        a, b = Image.open(OUT / f'_today_{view}.png'), Image.open(OUT / f'_new_{view}.png')
        row = Image.new('RGB', (a.width + b.width, a.height), 'white'); row.paste(a, (0, 0)); row.paste(b, (a.width, 0)); rows.append(row)
    sheet = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)), 'white')
    y = 0
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height
    sheet.save(OUT / 'P5_today_vs_pass1.png')
    for f in OUT.glob('_*.png'):
        f.unlink()
    # dressed views without the frame, and bare (first commit of this pass) against dressed
    render(shoulder_items(with_frame=False), OUT / 'D2_front_clean.png', eye_front, F, title='Dressed: front-outboard, no frame or shell')
    render(shoulder_items(with_frame=False), OUT / 'D3_back_clean.png', eye_back, F, title='Dressed: back, no frame or shell')
    # whole arm (upper arm and forearm of left-arm-organic, read-only exports) for the family look, and the elbow beside it
    FA = Path(r'J:/code/roark-wt/left-arm-organic/cad/exports/forearm')
    fore = [(trimesh.load(f), (0.95, 0.95, 0.93) if 'cap' not in f.name else (0.86, 0.87, 0.88), 1.0) for f in sorted(FA.glob('*.STL'))]
    Fw = np.array([RX - 10, 300.0, 10.0])
    render(shoulder_items(with_frame=False) + fore, OUT / 'D5_whole_arm.png', Fw + np.array([620.0, 120.0, 820.0]), Fw, size=(1400, 1800), angle=34,
           title='Dressed shoulder with the whole organic left arm (front-outboard)')
    elbow_png = Path(r'J:/code/roark-wt/left-arm-organic/cad/_wip/organic-arm/cad/a2_90_q34.png')
    if elbow_png.exists():
        a = Image.open(OUT / 'D2_front_clean.png').convert('RGB')
        b = Image.open(elbow_png).convert('RGB')
        b = b.resize((int(b.width * a.height / b.height), a.height))
        row = Image.new('RGB', (a.width + b.width, a.height), 'white'); row.paste(a, (0, 0)); row.paste(b, (a.width, 0))
        ImageDraw.Draw(row).text((a.width + 24, 20), "The organic arm's own render (left-arm-organic, a2_90_q34)", fill=(20, 20, 20), font=FONT)
        row.save(OUT / 'D6_shoulder_vs_arm_render.png')
    # top-down and the camera of Joey's screenshot: front-outboard, looking down on the drum top
    Ft = np.array([RX - 20, RY - 10, -5.0])
    render(shoulder_items(with_frame=False), OUT / 'D7_top_down.png', Ft + np.array([60.0, 650.0, 120.0]), Ft, up=(0, 0, -1), size=(1600, 1300),
           title='Top-down: the drum top, swell and bell (no frame or shell)')
    Fs = np.array([RX - 15, RY + 20, 0.0])
    render(shoulder_items(with_frame=False), OUT / 'D8_drum_top_view.png', Fs + np.array([330.0, 300.0, 420.0]), Fs, size=(1600, 1200),
           title='Front-outboard, looking down on the drum top (the camera of the review screenshot)')
    Fb = np.array([RX - 10, RY - 45, -20.0])
    render(shoulder_items(with_frame=False), OUT / 'D9_back_straight.png', Fb + np.array([0.0, 20.0, -700.0]), Fb, size=(1400, 1500), angle=30,
           title='Straight from behind (no frame or shell)')
    render(shoulder_items(with_frame=False), OUT / 'D10_back_below.png', Fb + np.array([420.0, -330.0, -520.0]), Fb, size=(1600, 1300), angle=32,
           title='From behind and below, three-quarter (no frame or shell)')
    bare = [Path(p) for p in sys.argv[2:4]] if len(sys.argv) > 3 else []
    if bare:
        rows = []
        for b, n in zip(bare, ('P1_look_front_outboard.png', 'P2_back.png')):
            a, c = Image.open(b).convert('RGB'), Image.open(OUT / n).convert('RGB')
            row = Image.new('RGB', (a.width + c.width, a.height), 'white'); row.paste(a, (0, 0)); row.paste(c, (a.width, 0))
            ImageDraw.Draw(row).text((24, 60), 'BARE (first pass)', fill=(150, 20, 20), font=FONT)
            ImageDraw.Draw(row).text((a.width + 24, 60), 'DRESSED', fill=(20, 110, 20), font=FONT)
            rows.append(row)
        sheet = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)), 'white')
        y = 0
        for r in rows:
            sheet.paste(r, (0, y)); y += r.height
        sheet.save(OUT / 'D4_bare_vs_dressed.png')
    print('done', flush=True)


if __name__ == '__main__':
    main()
