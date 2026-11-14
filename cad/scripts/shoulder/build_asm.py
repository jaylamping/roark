"""Left shoulder assembly (first pass): skeleton, printed parts, 6808, motors, torso corner and the frozen upper arm.

    python build_asm.py            build and save cad/shoulder/left/shoulder_left_asm.SLDASM at the neutral pose
    python build_asm.py check      interference detection in SolidWorks at the brief's poses -> _wip/.../interference.json

Every part is modelled in the (old-frame) torso coordinates and sits at the origin, fixed; motors, bearing and references
are placed by fixed transforms; poses are set by turning the joint groups about the skeleton axes (pose()).
The torso frame (rev A, torso_frame.step in its own coordinates) is the one exception: it hangs on three plane mates. The
X one, TORSO_X_SHIFT, a 38 mm distance mate (frame toward -X), is the single place where the shoulder sits against the frame.
"""
import json
import math
import sys

import numpy as np

from dims import *
from swk import *

ASM = OUT / 'shoulder_left_asm.SLDASM'
REF = OUT / 'ref'
BRG = CAD / 'vendor' / 'generic' / 'vendor_generic_6808_2rs.SLDPRT'


def Rx(a):
    t = math.radians(a); c, s = math.cos(t), math.sin(t)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    t = math.radians(a); c, s = math.cos(t), math.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    t = math.radians(a); c, s = math.cos(t), math.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def M4(R=np.eye(3), t=(0, 0, 0)):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t
    return M


def about(R, o):
    o = np.array(o, float)
    return M4(R, o - R @ o)


# placements of the purchased parts in the torso frame (column vectors, mm)
T_ROLL_RS03 = M4(Rz(180), (RX, RY, ROLL_OUT - 37.5))           # vendor output face z 37.5 -> Z 30.64
_CLK = 98.0 + (40.0 if RS02_RECLOCK else 0.0)   # plug pocket pp_r: the RS02 re-clocked +40 deg (in-use socket at 228 deg)
_c, _s = math.cos(math.radians(_CLK)), math.sin(math.radians(_CLK))
T_RS02 = M4(np.array([[_c, -_s, 0], [0, 0, -1], [_s, _c, 0]]), (RX, RS02_UNDER, YZ))  # vendor z (output +4) -> -Y; clock fitted to the placed STEP
T_BRG = M4(np.eye(3), (RX, RY, BRG_Z[1]))

PARTS = [  # (key, file, group, base transform, colour)
    ('skeleton', OUT / 'shoulder_skeleton_left.SLDPRT', 'fixed', None, None),
    ('cover', OUT / 'shoulder_pitch_loop_cover_left.SLDPRT', 'fixed', None, 'petg'),
    ('torso_frame', REF / 'shoulder_ref_torso_frame_left.SLDPRT', 'cage', None, 'frame'),   # rev A, its own frame: X - 38 here
    ('pitch_rs03', REF / 'shoulder_ref_pitch_rs03_left.SLDPRT', 'fixed', None, 'motor'),
    ('drum', OUT / 'shoulder_roll_drum_left.SLDPRT', 'pitch', None, 'petg'),
    ('ring', OUT / 'shoulder_pitch_flange_ring_left.SLDPRT', 'pitch', None, 'petg'),
    ('port_cap', OUT / 'shoulder_roll_drum_port_cap_left.SLDPRT', 'pitch', None, 'petg'),
    ('cap', OUT / 'shoulder_roll_cap_left.SLDPRT', 'pitch', None, 'petg'),
    ('cover_ring', OUT / 'shoulder_roll_cover_ring_left.SLDPRT', 'pitch', None, 'motor'),   # optional dark ring in the drum's lip (2026-11-14)
    ('bearing', BRG, 'pitch', T_BRG, 'steel'),
    ('roll_rs03', VENDOR / 'vendor_robstride_rs03.SLDPRT', 'pitch', T_ROLL_RS03, 'motor'),
    ('fork_front', OUT / 'shoulder_fork_front_left.SLDPRT', 'roll', None, 'petg'),
    ('fork_rear', OUT / 'shoulder_fork_rear_left.SLDPRT', 'roll', None, 'petg'),
    ('rs02', VENDOR / 'vendor_robstride_rs02.SLDPRT', 'roll', T_RS02, 'motor'),
    ('hub', OUT / 'shoulder_hub_left.SLDPRT', 'yaw', None, 'petg'),
    ('ua_front', REF / 'shoulder_ref_upper_arm_front_left.SLDPRT', 'yaw', None, 'arm'),
    ('ua_back', REF / 'shoulder_ref_upper_arm_back_left.SLDPRT', 'yaw', None, 'arm'),
    ('ua_ring', REF / 'shoulder_ref_upper_arm_rs02_ring_left.SLDPRT', 'yaw', None, 'motor'),
]
FRAME_SHIFT = 38.0      # rev A frame: the shoulder sits 38 mm further outboard than in the old-frame coordinates used here
COLOURS = dict(petg=(0.93, 0.93, 0.91), frame=(0.55, 0.57, 0.6), steel=(0.75, 0.76, 0.78), motor=(0.22, 0.23, 0.25), arm=(0.86, 0.86, 0.84))


def pose_matrix(group, pitch=0.0, roll=0.0, yaw=0.0):
    M = np.eye(4)
    if group == 'yaw':
        M = about(Ry(yaw), (RX, 0, YZ)) @ M
    if group in ('yaw', 'roll'):
        M = about(Rz(roll), (RX, RY, 0)) @ M
    if group in ('yaw', 'roll', 'pitch'):
        M = about(Rx(-pitch), (0, RY, PZ)) @ M      # pitch +a = arm forward
    return M


_MOD = []


def swmod():
    """Early-bound SolidWorks type library: IMathUtility only works through it from Python."""
    if not _MOD:
        from win32com.client import gencache
        la = pythoncom.LoadTypeLib(r'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.tlb').GetLibAttr()
        _MOD.append(gencache.EnsureModule(str(la[0]), la[1], la[3], la[4]))
    return _MOD[0]


def sw_xform(M):
    sw = app()
    R = M[:3, :3]
    arr = [R[0, 0], R[1, 0], R[2, 0], R[0, 1], R[1, 1], R[2, 1], R[0, 2], R[1, 2], R[2, 2],
           M[0, 3] * m, M[1, 3] * m, M[2, 3] * m, 1.0, 0.0, 0.0, 0.0]
    mu = swmod().IMathUtility(sw.GetMathUtility._oleobj_)
    return mu.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in arr]))


def build_bearing():
    if BRG.exists():
        return
    d = new_part(BRG)
    pl = plane(d, 'Y', 0.0, 'Top Plane')
    with Sk(d, d.FeatureByName('Top Plane'), 'BRG') as s:
        s.rpoly([(20.0, 0, 0), (26.0, 0, 0), (26.0, 0, 7.0), (20.0, 0, 7.0)], [0.3] * 4)
        s.cline((0, 0, -5), (0, 0, 12))
    revolve(d, s.feat, 'BRG')
    stamp_props(d, dict(Description='Deep groove ball bearing 6808-2RS, 40 x 52 x 7 (envelope)'))
    save(d)
    app().CloseDoc(d.GetTitle)


def open_asm():
    sw = app()
    sw.CloseAllDocuments(True)
    e, w = L(), L()
    d = sw.OpenDoc6(str(ASM), 2, 1, '', e, w)
    if d is None:
        raise SystemExit(f'open failed {e.value}')
    return d


def comps(d):
    out = {}
    for c in d.GetComponents(True):
        out[Path(c.GetPathName).name.lower()] = c
    return {k: out[Path(p).name.lower()] for k, p, *_ in PARTS}


def set_pose(d, C, pitch=0.0, roll=0.0, yaw=0.0):
    for k, p, g, T0, col in PARTS:
        if g == 'cage':
            continue
        M = pose_matrix(g, pitch, roll, yaw) @ (T0 if T0 is not None else np.eye(4))
        C[k].Transform2 = sw_xform(M)
    d.ForceRebuild3(False)


def build():
    build_bearing()
    sw = app()
    sw.CloseAllDocuments(True)
    d = sw.NewDocument(TPL_ASM, 0, 0, 0)
    e, w = L(), L()
    d.Extension.SaveAs(str(ASM), 0, 1, NUL, e, w)
    for k, p, g, T0, col in PARTS:
        e2, w2 = L(), L()
        pd = sw.OpenDoc6(str(p), 1, 1 | 2, '', e2, w2)     # silent, read-only: only to load it for the insertion
        c = d.AddComponent5(str(p), 0, '', False, '', 0, 0, 0)
        if c is None:
            raise SystemExit('add failed ' + str(p))
        if T0 is not None:
            c.Transform2 = sw_xform(T0)
        if col:
            r, g_, b = COLOURS[col]
            c.SetMaterialPropertyValues2(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [r, g_, b, 0.5, 0.8, 0.3, 0.3, 0.0, 0.0]), 1, NUL)
        sw.CloseDoc(Path(p).name)
        log('  added', k, c.Name2)
    d.ForceRebuild3(False)
    C = comps(d)
    d.ClearSelection2(True)
    for k, *_ in PARTS:
        if k != 'torso_frame':
            C[k].Select4(True, NUL, False)
    d.FixComponent()
    cage = C['torso_frame'].Name2
    asm = d.GetTitle.split('.')[0]
    for pl, name, dist in (('Front Plane', 'TORSO_Z', 0.0), ('Top Plane', 'TORSO_Y', 0.0), ('Right Plane', 'TORSO_X_SHIFT', FRAME_SHIFT)):
        for flip in (False, True):
            d.ClearSelection2(True)
            a = d.Extension.SelectByID2(f'{pl}@{cage}@{asm}', 'PLANE', 0, 0, 0, False, 1, NUL, 0)
            b = d.Extension.SelectByID2(pl, 'PLANE', 0, 0, 0, True, 1, NUL, 0)
            err = L()
            mt = d.AddMate5(5 if dist else 0, 0, flip, dist * m, dist * m, dist * m, 0, 0, 0, 0, 0, False, False, 0, err)
            d.ForceRebuild3(False)
            tx = C['torso_frame'].Transform2.ArrayData[9] * 1e3
            if not dist or abs(tx + dist) < 0.01:
                break
            d.EditUndo2(1)
        log('  frame X offset', round(C['torso_frame'].Transform2.ArrayData[9] * 1e3, 3))
        if mt is None:
            raise SystemExit(f'mate {name} failed: sel {a} {b} err {err.value}')
        d.FeatureByPositionReverse(0).Name = name
        log('  mate', name, err.value)
    d.ForceRebuild3(False)
    d.ShowNamedView2('*Isometric', 7)
    d.ViewZoomtofit2()
    save(d)
    return d


def check():
    d = open_asm()
    C = comps(d)
    d.ClearSelection2(True)
    for k, *_ in PARTS:
        if k != 'torso_frame':
            C[k].Select4(True, NUL, False)
    d.UnfixComponent()          # poses move the parts; the file on disk keeps them fixed
    poses = [(p, r, y) for r in (0.0, ROLL_STOP_IN, 45.0, ROLL_STOP_OUT) for p in (-30.0, 0.0, 90.0) for y in (-90.0, 0.0, 90.0)]
    res = []
    for (p, r, y) in poses:
        set_pose(d, C, p, r, y)
        idm = d.InterferenceDetectionManager
        idm.TreatCoincidenceAsInterference = False
        idm.TreatSubAssembliesAsComponents = True
        idm.IncludeMultibodyPartInterferences = False
        idm.MakeInterferingPartsTransparent = False
        idm.CreateFastenersFolder = False
        idm.IgnoreHiddenBodies = True
        ints = idm.GetInterferences or []
        found = []
        for it in ints:
            names = sorted(Path(c.GetPathName).stem for c in it.Components)
            found.append(dict(parts=names, volume_mm3=round(it.Volume * 1e9, 2)))
        idm.Done()
        res.append(dict(pitch=p, roll=r, yaw=y, interferences=found))
        log(f'pose pitch {p:+.0f} roll {r:+.0f} yaw {y:+.0f}: {len(found)}', [(f["parts"], f["volume_mm3"]) for f in found])
    set_pose(d, C, 0, 0, 0)
    sw = app()
    sw.CloseAllDocuments(True)      # not saved: the file stays at neutral with its parts fixed
    (WIP / 'interference.json').write_text(json.dumps(res, indent=1))
    return res


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        check()
    else:
        build()
