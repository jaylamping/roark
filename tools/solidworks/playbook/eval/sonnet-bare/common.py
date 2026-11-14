import sys, os, json, time, math
sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\tools\solidworks")
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT
from sw_instance import launch

WIP = r"J:\code\roark-wt\sw-eval-bare\cad\_wip\sw-eval\sonnet-bare"
EV = r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare"
TEMPLATE = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot"
SLDMAT = os.path.join(WIP, "eval_materials.sldmat")
NOTHING = VARIANT(pythoncom.VT_DISPATCH, None)
MM = 1e-3

SLDMAT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<mstns:materials xmlns:mstns="http://www.solidworks.com/sldmaterials" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2008.03">
  <classification name="Eval">
    <material name="PETG printed" matid="1" envdata="0">
      <physicalproperties>
        <EX displayname="Elastic Modulus" value="1.9E+09" />
        <NUXY displayname="Poisson's Ratio" value="0.38" />
        <GXY displayname="Shear Modulus" value="6.884E+08" />
        <DENS displayname="Density" value="1190" />
        <SIGXT displayname="Tensile Strength" value="4.5E+07" />
        <SIGYLD displayname="Yield Strength" value="4.5E+07" />
      </physicalproperties>
    </material>
    <material name="Steel pin" matid="2" envdata="0">
      <physicalproperties>
        <EX displayname="Elastic Modulus" value="2.1E+11" />
        <NUXY displayname="Poisson's Ratio" value="0.28" />
        <GXY displayname="Shear Modulus" value="8.2E+10" />
        <DENS displayname="Density" value="7800" />
        <SIGXT displayname="Tensile Strength" value="4.0E+08" />
        <SIGYLD displayname="Yield Strength" value="2.5E+08" />
      </physicalproperties>
    </material>
  </classification>
</mstns:materials>
"""

def write_mat():
    os.makedirs(WIP, exist_ok=True)
    with open(SLDMAT, "w", encoding="utf-8") as f:
        f.write(SLDMAT_XML)

def prep(sw):
    """holly-pc defaults per cad.md section 9: STL positive-space off, binary, mm; STEP AP203."""
    sw.SetUserPreferenceToggle(71, True)   # do not translate to positive space
    sw.SetUserPreferenceToggle(69, True)   # binary
    sw.SetUserPreferenceIntegerValue(211, 0)  # units mm (swExportStlUnits_e: 0 = inches? set below by check)
    sw.SetUserPreferenceIntegerValue(75, 203)
    sw.SetUserPreferenceIntegerValue(78, 3)   # custom quality
    sw.SetUserPreferenceDoubleValue(2, 0.005*MM)   # deviation 0.005 mm
    sw.SetUserPreferenceDoubleValue(3, math.radians(5))  # angle 5 deg

def new_part(sw):
    doc = sw.NewDocument(TEMPLATE, 0, 0, 0)
    doc.SetUserPreferenceIntegerValue(263, 5)  # swUnitsLinear = mmgs
    return doc

def select_plane(doc, name):
    ok = doc.Extension.SelectByID2(name, "PLANE", 0, 0, 0, False, 0, NOTHING, 0)
    assert ok, name

def ext(fm, depth_mm, merge=True, both=False, flip=False):
    # Sd=True is single-ended. T1=0 blind.
    return fm.FeatureExtrusion3(not both, flip, False, 0, 0, depth_mm*MM, depth_mm*MM, False, False, False, False,
                                0, 0, False, False, False, False, merge, True, True, 0, 0, False)

def cut(fm, through=True, depth_mm=0, both=False, flip=False):
    t = 1 if through else 0   # 1 = through all
    return fm.FeatureCut4(not both, flip, False, t, t, depth_mm*MM, depth_mm*MM, False, False, False, False, 0, 0,
                          False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)

def fillet(fm, radius_mm):
    emp = VARIANT(pythoncom.VT_DISPATCH, None)
    return fm.FeatureFillet3(195, radius_mm*MM, 0, 0, 0, 0, 0, emp, emp, emp, emp, emp, emp, emp)

def sel_edge(doc, x, y, z, append=True):
    ok = doc.Extension.SelectByID2("", "EDGE", x*MM, y*MM, z*MM, append, 1, NOTHING, 0)
    assert ok, ("edge", x, y, z)

def mass_props(doc):
    mp = doc.Extension.CreateMassProperty2
    return mp

def bbox(doc):
    b = doc.GetPartBox(True)
    return [round(x/MM, 4) for x in b]

def stamp(msg, t0=[time.time()]):
    print(f"[{time.time()-t0[0]:7.1f}s] {msg}", flush=True)

def open_part(sw, path, read_only=False):
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0); w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    doc = sw.OpenDoc6(path, 1, 1 if read_only else 0, "", e, w)
    assert doc is not None, (path, e.value)
    return doc

def save_as(doc, path):
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0); w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ok = doc.Extension.SaveAs3(path, 0, 1, NOTHING, NOTHING, e, w)
    return ok, e.value, w.value

def stl_check(path):
    import trimesh
    m = trimesh.load(path, process=False); m.merge_vertices()
    return dict(watertight=bool(m.is_watertight), volume=float(m.volume), bounds=m.bounds.round(4).tolist())

RESULTS = os.path.join(EV, "results.json")
def record(task, **kw):
    d = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {}
    d.setdefault(task, {}).update(kw)
    json.dump(d, open(RESULTS, "w"), indent=2)

def g(obj, name, *a):
    """pywin32 dynamic dispatch sometimes returns a zero-arg COM method's value, sometimes a bound method."""
    v = getattr(obj, name)
    import types; return v(*a) if isinstance(v, types.MethodType) else v
