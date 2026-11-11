"""Shell opening at the left shoulder: option A (opening r 80, cover ring round the pitch motor) against option B (opening
r 60 kept, clock-spring cassette in front of the pitch output). Quick mock-up and pictures, rev A frame coordinates.

    python options.py OUTDIR

Inputs: the first-pass SolidWorks parts (STL in cad/_wip/shoulder-pass1/stl and STEP in .../step, old-frame coordinates,
moved +38 X here), the vendor RS02/RS03, the pitch RS03 as placed (cad/reference/shoulder), the frozen upper arm, and
J:/code/_transfer/shoulder/torso_frame.step and shell_inner.step (rev A coordinates). Rough geometry: the shell is drawn as
its inner surface (no wall thickness), cut at the opening radius round the pitch axis outboard of X 120.
"""
import math
import sys
from pathlib import Path

import cadquery as cq
import matplotlib
import numpy as np
import trimesh

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly

HERE = Path(__file__).resolve()
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO / 'cad' / 'scripts' / 'shoulder'))
from build_asm import T_ROLL_RS03, T_RS02  # noqa: E402
from check_clearance import named_solids, tess  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1]
OUT.mkdir(parents=True, exist_ok=True)
WIP = REPO / 'cad' / '_wip' / 'shoulder-pass1'
TR = Path(r'J:/code/_transfer/shoulder')
S = 38.0                                  # old frame -> rev A
RY, PZ = 424.86, 0.0
B_SHIFT = 16.0                            # option B: the shoulder moves this far further outboard (see OPTIONS.md)
WHITE, GREY, DARK, SHELL, FRAMEC = (0.93, 0.93, 0.91), (0.72, 0.73, 0.75), (0.25, 0.26, 0.28), (0.80, 0.80, 0.80), (0.55, 0.57, 0.60)
RED, BLUE = (0.85, 0.12, 0.10), (0.12, 0.30, 0.85)


def mv(m, dx):
    m = m.copy()
    m.apply_translation((dx, 0, 0))
    return m


def step_mesh(path, M=None, tol=0.2):
    s = cq.importers.importStep(str(path))
    m = trimesh.util.concatenate([tess(x, tol) for x in s.solids().vals()])
    if M is not None:
        m.apply_transform(M)
    return m


def pitch_ring(r0, r1, x0, x1, n=120):
    a = trimesh.creation.annulus(r_min=r0, r_max=r1, height=x1 - x0, sections=n) if r0 > 0 else trimesh.creation.cylinder(radius=r1, height=x1 - x0, sections=n)
    a.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
    a.apply_translation(((x0 + x1) / 2, RY, PZ))
    return a


def tube(pts, r, sections=12):
    """Chain of cylinders and spheres along a polyline (a cable passage)."""
    parts = []
    pts = np.asarray(pts, float)
    for a, b in zip(pts[:-1], pts[1:]):
        if np.linalg.norm(b - a) < 1e-6:
            continue
        parts.append(trimesh.creation.cylinder(radius=r, segment=np.array([a, b]), sections=sections))
    for p in pts:
        s = trimesh.creation.icosphere(subdivisions=1, radius=r)
        s.apply_translation(p)
        parts.append(s)
    return trimesh.util.concatenate(parts)


def spiral(r0, r1, turns, x, n=400):
    t = np.linspace(0, turns * 2 * math.pi, n)
    r = r0 + (r1 - r0) * t / t[-1]
    return np.c_[np.full(n, x), RY + r * np.cos(t), PZ + r * np.sin(t)]


# ----------------------------------------------------------------------------------------------------------------- load
print('loading', flush=True)
OLD = {k: trimesh.load(WIP / 'stl' / f'{k}.stl') for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'fork_cap', 'hub', 'cover')}
MOT = dict(roll_rs03=step_mesh(REPO / 'cad/vendor/robstride/vendor_robstride_rs03.stp', T_ROLL_RS03),
           rs02=step_mesh(REPO / 'cad/vendor/robstride/vendor_robstride_rs02.step', T_RS02),
           pitch_rs03=step_mesh(REPO / 'cad/reference/shoulder/torso_pitch_rs03_left.step', tol=0.4))
UA = trimesh.util.concatenate([step_mesh(REPO / f'cad/reference/shoulder/upper_arm_organic_{n}_left.step', tol=0.3) for n in ('front', 'back', 'rs02_ring')])
frame_parts, collar = [], []
for nm, sh in named_solids(str(TR / 'torso_frame.step')):
    bb = sh.BoundingBox()
    if bb.xmax < 40 or bb.ymax < 260 or bb.ymin > 540 or nm.startswith('actuator__rs03'):
        continue
    (collar if (nm.startswith('shellpart__collar') or nm.startswith('fastener__c1_')) else frame_parts).append(tess(sh, 0.4))
FRAME = trimesh.util.concatenate(frame_parts)
COLLAR = trimesh.util.concatenate(collar)
sh = cq.importers.importStep(str(TR / 'shell_inner.step'))
SH = trimesh.util.concatenate([tess(f, 0.4) for f in sh.faces().vals()])
c = SH.triangles_center
SH.update_faces((c[:, 0] > 30) & (c[:, 1] > 260) & (c[:, 1] < 540) & (c[:, 2] > -150) & (c[:, 2] < 150))
SH.remove_unreferenced_vertices()
SH = SH.subdivide_to_size(2.0, max_iter=12)
c = SH.triangles_center
SH.update_faces((c[:, 0] > 60) & (c[:, 1] > 280) & (c[:, 1] < 520) & (c[:, 2] > -140) & (c[:, 2] < 140))
SH.remove_unreferenced_vertices()


def shell_cut(r):
    m = SH.copy()
    c = m.triangles_center
    rr = np.hypot(c[:, 1] - RY, c[:, 2] - PZ)
    m.update_faces(~((c[:, 0] > 120) & (rr < r)))
    m.remove_unreferenced_vertices()
    return m


# --------------------------------------------------------------------------------------------------------------- option A
def option_a():
    moving = {k: mv(OLD[k], S) for k in ('drum', 'ring', 'cap', 'fork_front', 'fork_rear', 'fork_cap', 'hub')}
    fixed = {'cover': mv(OLD['cover'], S)}
    mot = {'roll_rs03': mv(MOT['roll_rs03'], S), 'rs02': mv(MOT['rs02'], S), 'pitch_rs03': mv(MOT['pitch_rs03'], S)}
    # cable route (rev A): feed up the void, run under the cover, loop in the channel, trunk over the drum, cap channel,
    # stub, fork rear arm, yaw exit under the RS02, hub window
    RX, YZ = 170.49 + S, 5.99
    p = [(107, 300, -6), (107, 337.6, -6), (126, 337.6, -6), (126, 358.9, -6)]
    for a in np.linspace(0, math.pi, 41):                          # angle from straight down to straight up, round the front
        p.append((126 + 6 * a / math.pi, RY - 66 * math.cos(a), 66 * math.sin(a) * 0.15 - 6))
    p += [(138.5, 489, -6), (178, 489, -6), (178, 489, -33.9), (RX, RY + 4.5, -33.9), (RX, RY + 4.5, -51.3), (RX - 6, 400, -51.3),
          (RX - 6, 319.5, -51.3), (RX - 6, 319.5, YZ - 37), (RX - 20, 319.5, YZ - 25), (RX - 30, 319.5, YZ), (RX - 20, 319.5, YZ + 25),
          (RX + 4, 312, YZ + 3), (RX, 290, YZ)]
    power = np.array(p, float)
    signal = power + np.array([0, 0, 15.0])
    signal[-14:] = power[-14:] + np.array([4.0, -1.0, 0])
    return dict(moving=moving, fixed=fixed, motors=mot, arm=mv(UA, S), shell=shell_cut(80.0), collar=None, power=power, signal=signal,
                name='A', title='A: shell opening r 80, cover ring round the pitch motor')


# --------------------------------------------------------------------------------------------------------------- option B
CASE = dict(r_hub=(22.0, 27.0), r_case=(56.8, 58.0), x0=135.0, decks=[('power', 7.0), ('power', 7.0), ('signal', 8.0)], sep=1.0, wall=1.2, gap=0.6)


def cassette():
    x = CASE['x0']
    parts, decks = [], []
    parts.append(pitch_ring(27.6, CASE['r_case'][1], x, x + CASE['wall']))                       # floor (fixed)
    x += CASE['wall']
    for i, (kind, w) in enumerate(CASE['decks']):
        decks.append((kind, x + CASE['gap'], x + CASE['gap'] + w))
        x += w + 2 * CASE['gap']
        if i < len(CASE['decks']) - 1:
            parts.append(pitch_ring(27.6, CASE['r_case'][1], x, x + CASE['sep']))                 # deck separators (fixed)
            x += CASE['sep']
    parts.append(pitch_ring(27.6, CASE['r_case'][1], x, x + CASE['wall']))                        # lid (fixed)
    x += CASE['wall']
    parts.append(pitch_ring(CASE['r_case'][0], CASE['r_case'][1], CASE['x0'], x))                  # outer wall
    hub = pitch_ring(CASE['r_hub'][0], CASE['r_hub'][1], CASE['x0'] + 0.5, x + 2.0 + 4.0)           # moving hub tube on the pad
    return trimesh.util.concatenate(parts), hub, decks, x


def option_b():
    case, hub, decks, x_end = cassette()
    need = x_end + 2.0                                       # moving parts 2 mm clear of the fixed lid
    drum_x_now = 113.5 + S                                   # drum inboard face at the pitch axis height
    print(f'option B: cassette X {CASE["x0"]}-{x_end:.1f}, moving parts from X {need:.1f}; drum at X {drum_x_now + B_SHIFT:.1f} after +{B_SHIFT}', flush=True)
    # drum without its old pad, neck, spokes and trunk start (old X < 113): replaced by the hub tube and a web
    dr = cq.importers.importStep(str(WIP / 'step' / 'drum.step')).val().cut(cq.Solid.makeBox(33.0, 400, 400, cq.Vector(80.0, 250, -200)))
    dm = mv(tess(dr, 0.2), S + B_SHIFT)
    web = pitch_ring(22.0, 46.0, x_end + 2.0, drum_x_now + B_SHIFT + 4.0)
    moving = {'drum': dm, 'web': web, 'hub_tube': hub}
    for k in ('cap', 'fork_front', 'fork_rear', 'fork_cap', 'hub'):
        moving[k] = mv(OLD[k], S + B_SHIFT)
    mot = {'roll_rs03': mv(MOT['roll_rs03'], S + B_SHIFT), 'rs02': mv(MOT['rs02'], S + B_SHIFT), 'pitch_rs03': mv(MOT['pitch_rs03'], S)}
    # feed: up the void under the step, outboard under the housing inside the shell, along the housing bottom in the r 53-60
    # annulus to the case wall
    feed_duct = trimesh.util.concatenate([
        trimesh.creation.box(extents=(10.8, 50, 26), transform=trimesh.transformations.translation_matrix((107, 330, 0))),
        trimesh.creation.box(extents=(14, 7.0, 26), transform=trimesh.transformations.translation_matrix((119, 358.4 - 6, 0))),
        trimesh.creation.box(extents=(20, 7.0, 26), transform=trimesh.transformations.translation_matrix((125, RY - 56.5, 0)))])
    fixed = {'case': case, 'feed': feed_duct}
    RX, YZ = 170.49 + S + B_SHIFT, 5.99
    dk = {k: (a + b) / 2 for k, a, b in decks}
    xp = [a for k, a, b in decks if k == 'power'][0] + 3.5
    xs = dk['signal']
    power = [(107, 300, -6), (107, 345, -6), (118, 352, -6), (128, RY - 56.5, -6), (xp, RY - 56.5, -6)]
    power = np.r_[np.array(power), spiral(56.0, 28.0, 2.6, xp)[::4]]
    power = np.r_[power, [(xp, RY + 26, 0), (x_end + 4, RY + 32, 0), (x_end + 8, RY + 64, 0), (RX - 30, 489, -6), (RX - 30, 489, -33.9),
                          (RX, RY + 4.5, -33.9), (RX, RY + 4.5, -51.3), (RX - 6, 400, -51.3), (RX - 6, 319.5, -51.3), (RX - 6, 319.5, YZ - 37),
                          (RX - 20, 319.5, YZ - 25), (RX - 30, 319.5, YZ), (RX - 20, 319.5, YZ + 25), (RX + 4, 312, YZ + 3), (RX, 290, YZ)]]
    signal = [(107, 300, 9), (107, 345, 9), (118, 352, 9), (128, RY - 56.5, 9), (xs, RY - 56.5, 9)]
    signal = np.r_[np.array(signal), spiral(56.0, 28.0, 2.6, xs)[::4]]
    signal = np.r_[signal, [(xs, RY + 26, 4), (x_end + 4, RY + 32, 6), (x_end + 8, RY + 64, 9), (RX - 30, 489, 9), (RX - 30, 489, -33.9 + 4),
                            (RX, RY - 3.5, -33.9), (RX, RY - 3.5, -51.3), (RX + 9, 400, -51.3), (RX + 9, 356, -51.3)]]
    vol = lambda m: abs(m.volume) if m.is_volume else float('nan')
    print('B masses g (PETG 1.27):', {k: round(vol(m) * 1.27e-3, 1) for k, m in dict(case=case, hub_tube=hub, web=web, drum_cut=dm, feed=feed_duct).items()},
          'drum as built', round(abs(OLD['drum'].volume) * 1.27e-3, 1), flush=True)
    return dict(moving=moving, fixed=fixed, motors=mot, arm=mv(UA, S + B_SHIFT), shell=shell_cut(60.0), collar=COLLAR, power=power,
                signal=np.asarray(signal, float), decks=decks, x_end=x_end, name='B',
                title=f'B: shell opening r 60 kept, clock-spring cassette, shoulder +{B_SHIFT:.0f} mm outboard')


# ------------------------------------------------------------------------------------------------------------- pictures
def render(opt, out, shell_opacity=1.0, cables=False, size=(1600, 1200)):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.83, 0.84, 0.86); ren.SetBackground2(0.98, 0.98, 0.99); ren.GradientBackgroundOn()

    def add(m, col, op=1.0, spec=0.25):
        pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices, float), deep=True))
        cells = vtk.vtkCellArray()
        cells.SetCells(len(m.faces), numpy_to_vtkIdTypeArray(np.hstack([np.full((len(m.faces), 1), 3), m.faces]).astype(np.int64).ravel(), deep=True))
        pd = vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(cells)
        nm = vtk.vtkPolyDataNormals(); nm.SetInputData(pd); nm.SetFeatureAngle(35); nm.ConsistencyOn()
        mp = vtk.vtkPolyDataMapper(); mp.SetInputConnection(nm.GetOutputPort())
        a = vtk.vtkActor(); a.SetMapper(mp)
        pr = a.GetProperty(); pr.SetColor(*col); pr.SetOpacity(op); pr.SetSpecular(spec); pr.SetSpecularPower(30); pr.SetDiffuse(0.8); pr.SetAmbient(0.2)
        if op < 1:
            pr.BackfaceCullingOff()
        ren.AddActor(a)
    for k, m in opt['moving'].items():
        add(m, WHITE)
    for k, m in opt['fixed'].items():
        add(m, GREY if k != 'feed' else (0.66, 0.67, 0.69))
    for k, m in opt['motors'].items():
        add(m, DARK)
    add(opt['arm'], (0.95, 0.95, 0.93))
    add(FRAME, FRAMEC)
    if opt['collar'] is not None:
        add(COLLAR, (0.70, 0.70, 0.70), shell_opacity if shell_opacity < 1 else 1.0)
    if cables:
        add(tube(opt['power'], 3.0), RED, spec=0.1)
        add(tube(opt['signal'], 2.5), BLUE, spec=0.1)
    add(opt['shell'], SHELL, shell_opacity, spec=0.1)
    ren.SetUseDepthPeeling(1); ren.SetMaximumNumberOfPeels(8)
    cam = ren.GetActiveCamera()
    f = np.array([175.0, 395.0, 0.0])
    cam.SetFocalPoint(*f)
    cam.SetPosition(*(f + np.array([480.0, 70.0, 600.0])))
    cam.SetViewUp(0, 1, 0)
    cam.SetViewAngle(30)
    ren.ResetCameraClippingRange()
    rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetAlphaBitPlanes(1); rw.SetMultiSamples(0); rw.AddRenderer(ren); rw.SetSize(*size)
    rw.Render()
    w = vtk.vtkWindowToImageFilter(); w.SetInput(rw); w.Update()
    pw = vtk.vtkPNGWriter(); pw.SetFileName(str(out)); pw.SetInputConnection(w.GetOutputPort()); pw.Write()


def section(opt, ax):
    """Plane Y = 424.86 (through the pitch axis), seen from above: X to the right, Z up (front)."""
    items = [(m, WHITE, k) for k, m in opt['moving'].items()] + [(m, GREY, k) for k, m in opt['fixed'].items()] + \
            [(m, DARK, k) for k, m in opt['motors'].items()] + [(opt['arm'], (0.95, 0.95, 0.93), 'arm'), (FRAME, FRAMEC, 'frame')]
    if opt['collar'] is not None:
        items.append((COLLAR, (0.7, 0.7, 0.7), 'collar'))
    for m, col, k in items:
        s = m.section(plane_origin=(0, RY, 0), plane_normal=(0, 1, 0))
        if s is None:
            continue
        for e in s.discrete:
            ax.add_patch(MPoly(e[:, [0, 2]], closed=True, fc=col, ec='#2a2d31', lw=0.4, zorder=2))
    s = opt['shell'].section(plane_origin=(0, RY, 0), plane_normal=(0, 1, 0))
    if s is not None:
        for e in s.discrete:
            ax.plot(e[:, 0], e[:, 2], color='#666', lw=1.6, zorder=3)
    if opt['name'] == 'A':
        for z in (+1, -1):
            ax.add_patch(plt.Rectangle((77.4 + S, z * 57.4 if z > 0 else -73.5), 25.1, 16.1, fc=(1, 0.85, 0.85), ec='none', zorder=1))
        ax.annotate('pitch loop channel r 57.4-73.5\n(power red, signal blue loop here)', (105 + S, 66), (60, 120), fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5))
        ax.annotate('fixed cover ring r 55-75.9', (90 + S, -75), (40, -125), fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5))
        ax.annotate('moving flange ring r 77.5', (105.4 + S, -77), (150, -128), fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5))
        ax.annotate('shell opening r 80', (122, 82), (60, 150), fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5))
    else:
        for kind, a, b in opt['decks']:
            col = (1, 0.8, 0.8) if kind == 'power' else (0.8, 0.85, 1)
            for z in (1, -1):
                ax.add_patch(plt.Rectangle((a, 27.6 if z > 0 else -56.8), b - a, 29.2, fc=col, ec='none', zorder=1))
                for k in range(3):                                       # a few band turns, schematic
                    rr = 30 + 9 * k
                    ax.add_patch(plt.Rectangle((a, z * rr - (0 if z > 0 else 4)), b - a, 4 if kind == 'power' else 2.2,
                                               fc=RED if kind == 'power' else BLUE, ec='none', zorder=4))
        ax.annotate('clock-spring cassette, 3 decks\n(power 4 x 7, power 4 x 7, signal 2.2 x 8)\nband space r 27-56.8', (150, 45), (60, 125), fontsize=8,
                    arrowprops=dict(arrowstyle='-', lw=0.5))
        ax.annotate('fixed case on the pitch housing rim', (136, -58), (40, -128), fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5))
        ax.annotate(f'moving hub on the pad, web to the drum\n(shoulder +{B_SHIFT:.0f} mm outboard)', (opt['x_end'] + 4, 30), (175, 125), fontsize=8,
                    arrowprops=dict(arrowstyle='-', lw=0.5))
        ax.annotate('shell opening r 60, collar X 135-137', (136, 60), (60, 160), fontsize=8, arrowprops=dict(arrowstyle='-', lw=0.5))
    ax.axhline(0, color='#999', lw=0.4, ls='--')
    ax.set_xlim(60, 250); ax.set_ylim(-140, 170); ax.set_aspect('equal')
    ax.set_xlabel('X (rev A, mm)'); ax.set_ylabel('Z (forward, mm)')
    ax.set_title(opt['title'] + '\nsection Y = 424.86 through the pitch axis, seen from above', fontsize=9, loc='left')


def main():
    from PIL import Image, ImageDraw, ImageFont
    opts = [option_a(), option_b()]
    font = ImageFont.load_default(size=26) if hasattr(ImageFont, 'load_default') else None
    for o in opts:
        n = o['name']
        render(o, OUT / f'{n}1_look.png')
        render(o, OUT / f'{n}2_cables.png', shell_opacity=0.25, cables=True)
        fig, ax = plt.subplots(figsize=(7.5, 10), dpi=200)
        section(o, ax)
        fig.savefig(OUT / f'{n}3_section.png', bbox_inches='tight', pad_inches=0.15); plt.close(fig)
        for k in ('1_look', '2_cables'):
            im = Image.open(OUT / f'{n}{k}.png').convert('RGB')
            d = ImageDraw.Draw(im)
            d.text((24, 20), o['title'] + ('' if k == '1_look' else '  (shell translucent, power red, signal blue)'), fill=(20, 20, 20), font=font)
            im.save(OUT / f'{n}{k}.png')
        print('pictures', n, flush=True)
    for k, nm in (('1_look', 'AB_look.png'), ('3_section', 'AB_section.png')):
        a, b = Image.open(OUT / f'A{k}.png').convert('RGB'), Image.open(OUT / f'B{k}.png').convert('RGB')
        h = max(a.height, b.height)
        sheet = Image.new('RGB', (a.width + b.width, h), 'white')
        sheet.paste(a, (0, 0)); sheet.paste(b, (a.width, 0))
        sheet.save(OUT / nm)


if __name__ == '__main__':
    main()
