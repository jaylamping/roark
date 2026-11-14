"""T2: open the saved bracket.SLDPRT, add four counterbores and a slot, save as bracket_b.SLDPRT."""
import hashlib
import math

from common import BASE_HOLES, D_BASE, OUT, Clock, beat, hand_volume, put
from swkit import (MID, Sk, bbox, bodies, close, expect, extrude, face_info, feature_errors, job, log, open_doc, pick, plane,
                   save, save_as, single_body, volume)

D_CB, CB_DEPTH = 10.0, 3.0                    # counterbore from the top of the base, Z 6 down to Z 3
SLOT_L, SLOT_W, SLOT_C = 20.0, 6.0, (45.0, 25.0)      # overall length along X, width, centre (X, Y)

dv_cb = 4 * math.pi * ((D_CB / 2) ** 2 - (D_BASE / 2) ** 2) * CB_DEPTH
straight = SLOT_L - SLOT_W                    # 14 between the end-arc centres
dv_slot = (straight * SLOT_W + math.pi * (SLOT_W / 2) ** 2) * 6
hand = hand_volume() - dv_cb - dv_slot

ck = Clock()
src = OUT / 'bracket.SLDPRT'
sha0 = hashlib.sha256(src.read_bytes()).hexdigest()
with job() as j:
    beat('T2 bracket_b', j.inst.pid)
    d = open_doc(j.sw, src)
    expect('opened part volume', volume(d), hand_volume(), 0.001)
    save_as(d, OUT / 'bracket_b.SLDPRT')      # from here the open document is bracket_b; bracket.SLDPRT is not written
    assert d.GetPathName.lower().endswith('bracket_b.sldprt'), d.GetPathName

    # counterbores: the tool runs Z 3 to 7, 1 mm above the base top into empty space
    with Sk(d, plane(d, 'Z', 5.0, 'CBORE_P'), 'CBORE') as s:
        for x, y in BASE_HOLES:
            s.circle((x, y, 5.0), D_CB / 2)
    extrude(d, s.feat, 'CBORE', 4.0, cut=True, mode=MID, expect_dv=dv_cb)
    save(d)

    # slot: the straight part, then a round end each side (full circles: half of each is already cut away)
    x0, x1 = SLOT_C[0] - straight / 2, SLOT_C[0] + straight / 2
    y0, y1 = SLOT_C[1] - SLOT_W / 2, SLOT_C[1] + SLOT_W / 2
    with Sk(d, plane(d, 'Z', 3.0, 'SLOT_P'), 'SLOT') as s:
        s.rect((x0, y0, 3.0), (x1, y1, 3.0))
    extrude(d, s.feat, 'SLOT', 8.0, cut=True, mode=MID, expect_dv=straight * SLOT_W * 6)
    with Sk(d, plane(d, 'Z', 3.0, 'SLOT_ENDS_P'), 'SLOT_ENDS') as s:
        s.circle((x0, SLOT_C[1], 3.0), SLOT_W / 2)
        s.circle((x1, SLOT_C[1], 3.0), SLOT_W / 2)
    extrude(d, s.feat, 'SLOT_ENDS', 8.0, cut=True, mode=MID, expect_dv=math.pi * (SLOT_W / 2) ** 2 * 6)
    save(d)

    vol = volume(d)
    expect('volume against the hand value', vol, hand, 0.001)
    b = bbox(d)
    for k, want in enumerate((0, 0, 0, 80, 50, 46)):
        expect(f'box[{k}]', b[k], want, 0.01)
    # counterbore floors: annular planes facing up, each centred on a base hole; their Z is the floor
    floors = [f for f in pick(d, kind='plane', normal=(0, 0, 1)) if abs(face_info(f)['area'] - dv_cb / 4 / CB_DEPTH) < 0.5]
    expect('counterbore floor faces', len(floors), 4, 0)
    zs = sorted({round(face_info(f)['box'][2], 4) for f in floors})
    log('counterbore floors at Z', zs, 'centres',
        sorted((round((face_info(f)['box'][0] + face_info(f)['box'][3]) / 2, 2),
                round((face_info(f)['box'][1] + face_info(f)['box'][4]) / 2, 2)) for f in floors))
    assert zs == [3.0], zs
    expect('counterbore walls (r 5)', len(pick(d, kind='cyl', r=D_CB / 2, inside=[15, 0, 2.9, 75, 50, 6.1])), 4, 0)   # the R5 corner rounds are r 5 too
    expect('remaining hole walls (r 2.75)', len(pick(d, kind='cyl', r=D_BASE / 2)), 4, 0)
    # the slot: overall X 35 to 55, Y 22 to 28, through Z 0 to 6
    ends = pick(d, kind='cyl', r=SLOT_W / 2)
    expect('slot end faces', len(ends), 2, 0)
    sb = [min(face_info(f)['box'][k] for f in ends) for k in range(3)] + [max(face_info(f)['box'][k + 3] for f in ends) for k in range(3)]
    log('slot ends span', [round(v, 3) for v in sb])
    for k, want in enumerate((35, 22, 0, 55, 28, 6)):
        expect(f'slot extent[{k}]', sb[k], want, 0.01)
    expect('rebuild errors', len(feature_errors(d)), 0, 0)
    single_body(d)
    nb = len(bodies(d))
    save(d)
    close(j.sw, d)

same = hashlib.sha256(src.read_bytes()).hexdigest() == sha0
log('bracket.SLDPRT unchanged:', same)
assert same
put('T2', dict(volume_mm3=round(vol, 2), hand_volume_mm3=round(hand, 2), counterbore_floor_z_mm=zs[0], bodies=nb, status='done',
               notes='Opened bracket.SLDPRT, saved as bracket_b first, then added CBORE, SLOT, SLOT_ENDS on top; '
                     'bracket.SLDPRT SHA-256 unchanged. Slot built as a rectangle cut plus two round-end cuts (three '
                     'features, same geometry as one slot). Slot extent and counterbore floors measured on the model.'), ck.s())
