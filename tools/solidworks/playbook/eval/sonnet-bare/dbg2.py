import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    doc = new_part(sw)
    print("default mat", repr(doc.MaterialIdName))
    for cfg in ("", "Default"):
        try:
            doc.SetMaterialPropertyName2(cfg, SLDMAT, "PETG printed")
        except Exception as e: print("err", e)
        print(cfg, "mat now", repr(doc.MaterialIdName), doc.GetMaterialPropertyName2("Default", None) if False else "")
    print(sw.GetUserPreferenceIntegerValue(211), sw.GetUserPreferenceToggle(71), sw.GetUserPreferenceToggle(69))
