"""Reference parts for the left shoulder assembly, imported into SolidWorks as multibody parts.

    python build_refs.py [UPPER_ARM_EXPORT_DIR]

- Vendor RS03 / RS02: cad/vendor/robstride/*.step re-written as one compound (so SolidWorks imports one multibody part, not
  an assembly) and saved as cad/vendor/robstride/vendor_robstride_rs03.SLDPRT / _rs02.SLDPRT, in the vendor frame.
- Old-frame torso (TORSO.step, 2026-11-05), cut by torso_corner.py: the 2020 cage corner with the pitch mount
  (torso_cage_left.step -> shoulder_ref_torso_cage_left.SLDPRT) and the pitch RS03 as placed (torso_pitch_rs03_left.step ->
  shoulder_ref_pitch_rs03_left.SLDPRT). The pitch motor goes with the shoulder; the cage hangs on one mate in the assembly.
- Frozen organic upper arm (left-arm-organic exports, torso frame): front and back halves and the RS02 ring ->
  cad/shoulder/left/ref/shoulder_ref_upper_arm_*_left.SLDPRT.
The placements of the motors in the torso frame are in build_asm.py.
"""
import shutil
import sys

import cadquery as cq

from swk import *

REF = OUT / 'ref'
REF.mkdir(parents=True, exist_ok=True)
RSTEP = CAD / 'reference' / 'shoulder'
TMP = WIP / 'ref'
TMP.mkdir(parents=True, exist_ok=True)


def compound(src, dst):
    s = cq.importers.importStep(str(src))
    cq.exporters.export(cq.Workplane().add(cq.Compound.makeCompound(s.solids().vals())), str(dst))
    return dst


def sw_import(step, target):
    """Import as one multibody part. The import options are shared with every SolidWorks on the PC (registry), so they are
    restored right after the import."""
    sw = app()
    sw.CloseAllDocuments(True)
    e = L()
    old_map, old_mb = sw.GetUserPreferenceIntegerValue(579), sw.GetUserPreferenceToggle(220)
    try:
        for mp in (1, 2, 0):
            sw.SetUserPreferenceIntegerValue(579, mp)
            sw.SetUserPreferenceToggle(220, False)
            d = sw.LoadFile4(str(step), 'r', sw.GetImportFileData(str(step)), e)
            if d is not None and d.GetType == 1:
                break
            if d is not None:
                sw.CloseAllDocuments(True)
    finally:
        sw.SetUserPreferenceIntegerValue(579, old_map)
        sw.SetUserPreferenceToggle(220, old_mb)
    if d is None:
        raise SystemExit(f'import failed {step} err {e.value}')
    if d.GetType != 1:
        raise SystemExit(f'{step} imported as type {d.GetType}, not a part')
    ee, ww = L(), L()
    ok = d.Extension.SaveAs(str(target), 0, 1, NUL, ee, ww)
    log('import', Path(step).name, '->', Path(target).name, ok, ee.value, 'bodies', len(d.GetBodies2(0, True) or []))
    sw.CloseDoc(d.GetTitle)
    return ok



if __name__ == '__main__':
    ua = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r'J:/code/roark-wt/left-arm-organic/cad/exports/upper-arm')
    for src, name in ((VENDOR / 'vendor_robstride_rs03.stp', 'vendor_robstride_rs03'), (VENDOR / 'vendor_robstride_rs02.step', 'vendor_robstride_rs02')):
        sw_import(compound(src, TMP / f'{name}.step'), VENDOR / f'{name}.SLDPRT')
    # made by torso_corner.py from the old TORSO.step (PART=cage / PART=pitch_rs03)
    sw_import(RSTEP / 'torso_cage_left.step', REF / 'shoulder_ref_torso_cage_left.SLDPRT')
    sw_import(RSTEP / 'torso_pitch_rs03_left.step', REF / 'shoulder_ref_pitch_rs03_left.SLDPRT')
    for part in ('front', 'back', 'rs02_ring'):
        src = ua / f'upper_arm_organic_{part}_left.step'
        dst = RSTEP / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        sw_import(dst, REF / f'shoulder_ref_upper_arm_{part}_left.SLDPRT')
