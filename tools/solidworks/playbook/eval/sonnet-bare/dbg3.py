import sys; sys.path.insert(0, r"J:\code\roark-wt\sw-eval-bare\eval-sonnet-bare")
from common import *
with launch() as inst:
    sw = inst.sw; prep(sw)
    doc = open_part(sw, os.path.join(WIP, "bracket.SLDPRT"))
    for q, dev, ang in ((2,0,0),(3,0.005,5),(3,0.02,10),(1,0,0)):
        sw.SetUserPreferenceIntegerValue(78, q)
        if q==3:
            sw.SetUserPreferenceDoubleValue(2, dev*MM); sw.SetUserPreferenceDoubleValue(3, math.radians(ang))
        p = os.path.join(WIP, f"t_q{q}_{dev}.stl")
        print(q, dev, save_as(doc, p), stl_check(p))
    for chk in (True,):
        sw.SetUserPreferenceToggle(73, chk)
        sw.SetUserPreferenceIntegerValue(78, 2)
        p = os.path.join(WIP, "t_chk.stl"); print("chk", save_as(doc, p), stl_check(p))
