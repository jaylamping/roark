"""Measure the fixed items on the finished solid in SolidWorks (faces by geometry)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *
with job() as j:
    d = open_doc(j.sw, WIP / 'link_organic.SLDPRT')
    out = {}
    h = pick(d, kind='cyl', r=1.7)
    out['holes_r1.7'] = [(round(float(np.hypot((i['box'][0]+i['box'][3])/2, (i['box'][2]+i['box'][5])/2)), 3),
                          round(float(np.degrees(np.arctan2((i['box'][5]+i['box'][2])/2, (i['box'][3]+i['box'][0])/2)) % 360), 1),
                          round(i['box'][1], 2), round(i['box'][4], 2)) for i in map(face_info, h)]
    b = pick(d, kind='cyl', r=15.0)
    out['bore_r15'] = [[round(v, 2) for v in face_info(f)['box']] for f in b]
    p = pick(d, kind='cyl', r=4.0, inside=[-5, -30, -204.1, 5, 30, -195.9])
    out['pin_r4'] = [[round(v, 2) for v in face_info(f)['box']] for f in p]
    out['inner_cheek_planes'] = [(round(face_info(f)['box'][1], 3), round(face_info(f)['area'], 1)) for f in
                                 pick(d, kind='plane', normal=(0, -1, 0)) + pick(d, kind='plane', normal=(0, 1, 0))
                                 if abs(abs(face_info(f)['box'][1]) - 16) < 0.01 and abs(face_info(f)['box'][4] - face_info(f)['box'][1]) < 0.01]
    ring = [f for f in pick(d, kind='plane', normal=(0, -1, 0)) if abs(face_info(f)['box'][1] + 4.0) < 0.02]
    out['ring_faces_area_mm2'] = [round(face_info(f)['area'], 1) for f in ring]
    out['ring_box'] = [[round(v, 2) for v in face_info(f)['box']] for f in ring]
    out['volume_mm3'] = volume(d); out['bodies'] = len(bodies(d)); out['feature_errors'] = len(feature_errors(d))
    close(j.sw, d)
json.dump(out, open(Path(__file__).resolve().parent / 'measure.json', 'w'), indent=1, default=str)
print(json.dumps(out, default=str))
