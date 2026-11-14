import json, math, sys
from pathlib import Path
WT = r"J:\code\roark-wt\sw-eval-sonnet"
sys.path.insert(0, WT + r"\tools\solidworks")
from swkit import *
from t1 import OUT, R
DIR = int(sys.argv[1]) if len(sys.argv) > 1 else 1
with job() as j:
    d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
    v_in = volume(d)
    save_as(d, OUT / 'bracket_b.SLDPRT')     # work on the copy, not the original
    log('now', d.GetPathName)
    with Sk(d, plane(d, 'Z', 4.5, 'CB_P'), 'CBORE') as s:
        for x, y in ((25, 10), (25, 40), (65, 10), (65, 40)):
            s.circle((x, y, 4.5), 5.0)
            s.circle((x, y, 4.5), 2.75)
    # concentric circles make rings: cut the annulus only
    extrude(d, s.feat, 'CBORE', 3.0, cut=True, mode=MID, expect_dv=4 * math.pi * (25 - 2.75 ** 2) * 3)
    save(d)
    with Sk(d, plane(d, 'Z', 3.0, 'SL_P'), 'SLOT') as s:
        a, b = (38.0, 25.0, 3.0), (52.0, 25.0, 3.0)      # centres of the end arcs
        s.poly([(38, 22, 3.0), (52, 22, 3.0)], closed=False)
        s.poly([(52, 28, 3.0), (38, 28, 3.0)], closed=False)
        s.arc(b, (52, 22, 3.0), (52, 28, 3.0), DIR)
        s.arc(a, (38, 28, 3.0), (38, 22, 3.0), DIR)
    extrude(d, s.feat, 'SLOT', 20.0, cut=True, mode=MID, expect_dv=(14 * 6 + math.pi * 9) * 6)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    save(d)
    hv = 32974.02416773479 - 4 * math.pi * (25 - 2.75 ** 2) * 3 - (14 * 6 + math.pi * 9) * 6
    vol = volume(d)
    expect('volume vs hand', vol, hv, 0.002)
    fl = [face_info(f) for f in pick(d, kind='plane', normal=(0, 0, 1))]
    floors = sorted({round(i['box'][5], 3) for i in fl if i['box'][5] < 5.99 and i['box'][5] > 0.1})
    log('upward planar face tops below z6:', floors)
    res = dict(volume_mm3=vol, hand_volume_mm3=hv, counterbore_floor_z_mm=floors[0] if floors else None, bodies=len(bodies(d)),
               floors_seen=floors, input_volume=v_in)
    print(res)
    (R / 't2_result.json').write_text(json.dumps(res, indent=1))
    close(j.sw, d)
