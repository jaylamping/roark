# Upper arm R1: rebuild, fit and slices (holly-pc, 2026-11-11)

R1 = the reviewed geometry (v26) with the RS02 stop face 0.2 mm further outboard (`STOP_PLAY` 0.4), and the ring sliced
without a brim. Built on holly-pc from branch `left-arm-organic-r1`. FEA model names are v28.

## Rebuild against v26 (geometry check)

The R1 exports were compared with the v26 exports at 8e659be: volume, area, bounding box, boolean differences and two-way
surface distance from 200k–400k samples (`geom_diff_front.json`, `geom_diff_back.json`).

| Part | Volume change | Max surface distance | Where |
| --- | --- | --- | --- |
| Ring | 0 (STL byte-identical) | 0 | none |
| Front half | −365.2 mm³ | 0.20 mm | stop face, X 193.9 → 194.1, r 22.5–43.6 |
| Back half | −366.9 mm³ | 0.20 mm | stop face, X 193.9 → 194.1, r 22.5–43.6 |

Bounding boxes are unchanged. Away from the stop face everything is under 0.075 mm, and that is tessellation, not geometry.
The largest case is the front's Ø32/Ø40 stub bores at X 134–144: vertices sit on r 16.000/20.000 in both meshes, but v26
used 20 segments per half-circle and R1 uses 19, so the chord sag at r 20 is 0.076 mm against 0.055 mm.

holly-pc's SolidWorks did not match Joey-PC's in two settings. Both are now pinned in `organic_master.py`:
- STL export translated to positive space. This first moved the ring STL +35.27 mm in Z, and it broke the front half's
  seam posts, which find the skin from the master STL.
- The part template is MMGS where Joey-PC's was IPS. The v26 STEP files are in inches, the R1 ones in mm. Scaled by 25.4,
  all 1,732 ring STEP points match exactly.

## RS02 fit (vendor model)

From `rs02_fit.json` and `rs02_fit_shift_overlaps.json`. The stop and rib faces are now measured from the exported halves,
not typed in. They read X 194.1 and 153.8 in both halves, the same as the typed values.

- Axial freedom of the RS02 + ring between the rib and the stop: **0.5 mm nominal, 0.1 mm worst case, 0.9 mm best**. The
  worst case takes the ring 0.1 thicker per face and the cavity 0.2 shorter. It stays positive, so nothing binds.
- Overlaps between the ring and the halves: only the crush ribs, 0.15 mm thick, the same as v26. That holds at every
  reachable axial position (ring on the rib, −0.1, to RS02 on the stop, +0.4).
- The RS02 first touches the stop at +0.4 and lies fully on it at +0.45. At −0.2 the ring would sit 0.1 mm inside the rib
  face, which it can't reach, so that overlap is not a bind.
- Slide-in: the ring + RS02 + plug drop into the back half, and the front half closes over them. Both are clear down to the
  last 5 mm. From there the only overlap is the crush ribs (2.8 mm³ at 0).
- Plug pull-out with the front half off: clear. Plug and cable envelope against the halves and the ring: 0.
- Ring screws: M3 × 16 button heads, 6.2 mm into the RS02 (vendor depth 8).

## Slices (Bambu Studio 2.09.01.70)

| Plate | Time | Filament | Mesh gate | Notes |
| --- | --- | --- | --- | --- |
| Ring | 56 min | 18.5 g | PASS | no brim, 100%, 2.2 mm chamfer; 1,273 mm² on the bed |
| Back half | 5 h 09 | 119.2 g | PASS | 50%, 100% modifier to X 171 (checked in the 3MF) |
| Front half | 4 h 35 | 104.5 g | PASS | the same; 1 listed thin spot (see below) |
| Key coupon | 33 min | 10.0 g | PASS | 100% |

Front half thin spot: the end of the R2 round where the rib meets the drum wall, running out into the neck opening at rib
face X 153.8, φ −23°. Thinner than 0.6 mm over 1.3 mm² in the R1 mesh against 0.5 mm² in v26: the same geometry within
0.075 mm, cut into triangles differently. It was already whitelisted, and the box is widened to cover the R1 tessellation
(`print_whitelist.json`). It is hidden, carries no load and prints as part of the rib perimeters.

The four 8 mm² visible-support spots on the front's seam-post and hub-post insert holes are the same as in v26.

Picture sheets: `ring_sheet.png`, `back_sheet.png`, `front_sheet.png`, `key_coupon_sheet.png`.

## Tools

Smoke test before R1: HALFK0_fine and E34_fine (v26) were re-solved on holly-pc and compared with Joey-PC's results. Peak
von Mises −1.4 % and −2.0 %, layer stresses within 1.5 %, node counts within 0.2 %.
Slicer: re-slicing the reviewed ring reproduced the stored slice exactly (3,465 s, 19.04 g).
