"""Idea B: a flat leaf (one outline, thin in Y, rounded edges) that opens into the same wrist. Quick model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2build import *
if __name__ == '__main__':
    with job() as j:
        d = new_part(j.sw, WIP / 'idea_b.SLDPRT')
        with Sk(d, plane(d, 'Y', 0, 'DISC_P'), 'DISC') as s:
            s.circle((0, 0, 0), 33.0)
        extrude(d, s.feat, 'DISC', 8.0, mode=MID)
        # leaf outline in XZ, symmetric, closed spline: widest 40 near the elbow, waist 26, wrist 36
        half = [(8, -17), (9, -26), (19, -45), (20, -62), (17, -100), (13.5, -140), (15, -165), (17, -180), (17, -213)]
        pts = [(x, 0, z) for x, z in half] + [(-x, 0, z) for x, z in reversed(half)]
        with Sk(d, plane(d, 'Y', 0, 'LEAF_P'), 'LEAF') as s:
            s.spline(pts)
        extrude(d, s.feat, 'LEAF', 12.0, mode=MID)
        with Sk(d, plane(d, 'Y', 0, 'WRIST_P'), 'WRIST') as s:
            s.rect((-17, 0, -165), (17, 0, -213))
        extrude(d, s.feat, 'WRIST', 43.0, mode=MID)
        save(d)
        features(d)
        export(j.sw, d, WIP / 'idea_b.stl'); save(d); close(j.sw, d)
