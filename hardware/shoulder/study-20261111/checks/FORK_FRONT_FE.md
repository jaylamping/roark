# Fork front: first finite-element cases, the yoke, and where the work stopped (2026-11-14)

**Status: work in progress, stopped at 01:09 local on 2026-11-14 for a reboot of holly-pc.** This page holds the results
so far and the queue to resume. Nothing real is changed: every build here is a look or analysis build.

## Short answer so far

- **The fork front never had a finite-element case.** C_LOAD_SHARE.md used a beam model after the two-body model failed.
- **Today's adopted fork front reads under target at the neck** for the design load: 0.92 on von Mises and 0.70 on layer
  tension with the joint to the fork rear held along Y, on a 0.7 mm mesh at the boss root. Target 1.5.
- **It is not an artefact of the rigid fixture.** Held by its six screw-head seats and three pins with the boss face
  free to slide, the figures are the same (0.92 / 0.72).
- **The boss root is a sharp corner in CAD** (the boss r 22 meets the cheek's back face at Z 39 with no blend), and the
  dome pockets begin 2.5 mm outside it (r 24.5).
- **The yoke with pockets reads about the same as today at the neck** and worse in the lower cheek.
- **The yoke with a solid neck and a 4.5 mm blend cone at the boss root reads about twice today's part at the neck,**
  is 8 g lighter than today's part and 30 % stiffer. It is the yoke on the sheet.
- **Still to do:** the same fine-mesh check on the solid-neck builds, and the combined model with the rear leg and the
  6808, which says how the loads really share. Until then no fork front should be printed for load.

## What the design load is

The arm's design load of check (a), applied through the RS02 seat about the arm's hub point (X 170.49, Y 292, Z 5.99):

- 310 N along -Y
- 23 N·m bending, about X (arm forward: cases MX) or about Z (sideways, the roll motor's own torque: case MZ)
- 17 N·m about Y: the yaw torque. This is the RS02's own peak (manual 260713 §4.1.2, MIT T ±17), **not a software cap**.
- Stop: 60 N·m about the roll axis, the RS03's peak at a stall (B_ROLL_STOPS.md; Joey's call whether that is a design case).

## The models

| Name | What |
|---|---|
| FF_* | The fork front alone, 2.0 mm mesh, boss face on the RS03 output fixed |
| "unsupported" (FF_MX, FF_MXn, FF_MZ, FF_SIDE) | Nothing else holds it: the RS03 takes everything. The bound that loads the fork front most |
| "supported" (FF_MXb, FF_MXnb) | The joint face to the fork rear also held along Y: the rear leg and 6808 take the forward moment's couple |
| FF_STOPM | 60 N·m about the roll axis as a pure couple from the joint face to the boss |
| P_* | As FF_*, with a 0.7 mm mesh round the boss root (478,066 nodes on today's part) |
| P_MXbs | P_MXb with the boss held as the screws hold it: six head seats fixed, three pin holes radial, face sliding |
| F2_* | Fork front and fork rear combined into one body, 6808 seat held radially. **Not run yet** |

- FFEPlus, linear (no contact in any of these). Read-out: worst 0.5 mm ball among each region's 300 highest nodes.
- Layer tension is σy against 22.5 MPa (the part prints Y up); von Mises against 45 MPa.
- The two Ø7 driver-access bores are suppressed (FF_*) or left out (analysis builds): they are plugged in service, and
  today's part does not mesh with them (code 8 at every size and tolerance tried).

## Results so far: safety factor, von Mises / layer tension

Fork front alone, 2.0 mm mesh (FF_*), by region.

| Case | Region | Today | Yoke with pockets | Yoke, solid neck and root cone |
|---|---|---|---|---|
| Supported, yaw +17 | Head and neck | 0.92 / 0.64 | 0.86 / 0.65 | **1.92 / 1.08** |
| | Lower cheek | 1.94 / 1.15 | 0.79 / 0.82 | 1.59 / 1.64 |
| | Sleeve | 8.61 / 4.52 | 6.77 / 3.45 | 8.95 / 4.58 |
| Supported, yaw -17 | Head and neck | 0.91 / 0.75 | (as +17) | 1.89 / 1.10 |
| | Lower cheek | 2.00 / 1.20 | | 1.57 / 1.31 |
| Unsupported, yaw +17 | Head and neck | 0.53 / 0.48 | 0.52 / 0.43 (trimmed build) | 1.22 / 0.75 |
| | Lower cheek | 0.87 / 0.54 | 0.35 / 0.27 (trimmed build) | 0.74 / 1.32 |
| Sideways moment (MZ), unsupported | Head and neck | 0.48 / 0.27 | 0.53 / 0.23 | 1.09 / 0.49 |
| | Lower cheek | 0.81 / 0.49 | 0.61 / 0.37 | 1.04 / 0.67 |
| 100 N sideways (SIDE) | Head and neck | 0.82 / 0.36 | 0.69 / 0.32 | 1.76 / 0.77 |
| Stop couple 60 N·m (STOPM) | Head and neck | 0.69 / 0.35 | 0.34 / 0.23 | 1.95 / 1.01 |
| | Lower cheek | 0.45 / 0.28 | 0.34 / 0.20 | 0.53 / 0.35 |
| | Sleeve | 0.48 / 0.31 | 0.45 / 0.28 | 0.50 / 0.31 |

Seat deflection (mean of the RS02 seat face, mm): supported 2.91 today, 4.18 yoke with pockets, **2.04** solid-neck
yoke. Unsupported 6.57, 8.47 (trimmed build), 4.25.

Today's part with the 0.7 mm mesh at the boss root (P_*, analysis build ffT):

| Case | Boss root | Head and neck | Lower cheek | Sleeve |
|---|---|---|---|---|
| Supported, yaw +17 (P_MXb) | 0.93 / 0.70 | 0.92 / 1.11 | 1.91 / 1.20 | 8.59 / 4.48 |
| Supported, yaw -17 (P_MXnb) | 0.92 / 0.68 | 0.92 / 1.14 | 1.96 / 1.18 | 7.13 / 4.73 |
| Supported, held by seats and pins (P_MXbs) | 0.92 / 0.72 | 0.93 / 1.14 | 1.93 / 1.22 | 8.71 / 4.53 |
| Unsupported, yaw +17 (P_MX) | 0.72 / 0.60 | 0.53 / 0.51 | 0.95 / 0.52 | 4.38 / 2.07 |
| Unsupported, yaw -17 (P_MXn) | 0.72 / 0.61 | 0.52 / 0.52 | 0.94 / 0.75 | 3.83 / 2.18 |

**Read:**
- The finer mesh did not move the boss root figure (0.92 → 0.93), and the softer fixture did not either. It is a real
  low spot of today's part in these bounds.
- The stop case's low figures in the lower cheek and sleeve are the same on all three builds: the fork front alone
  carrying 60 N·m from the joint face is not how the stop works (the 6808 holds the rear leg radially). The combined
  model is needed before reading them.
- The unsupported and sideways figures are bounds for a fork front with no rear leg at all. The combined model decides
  how near the truth they are.

## Two mistakes of mine found on the way

- I trimmed the yoke's lower body to the cuff's width to tidy the shoulder ends. That took away the two strips that
  stand outside the drum's envelope and run full depth beside the drum. The lower cheek fell from 1.94 / 1.15 to
  0.60 / 0.55. The width is back (`YOKE['half_w'] = 0`).
- My first stop case put the tooth's 1714 N on the fork front with no 6808. It read 0.1 and meant nothing. Replaced by
  the pure couple (FF_STOPM) and, for the real answer, F2_STOP on the combined body.

## The yoke design

- `cad/scripts/shoulder/yoke.py`: one outline. Today's lower cheek below two shoulder lines 36° under the horizontal,
  the hub disc r 30, a 22 mm blend between them, 9.5 mm rounds at the shoulder ends. The crowned edge runs all round it.
- Six of the drum's eight lip screws show, evenly, 6.6 mm clear of the yoke's edge. They are already 0.2 mm under the
  lip's face (counterbored), so nothing stands proud.
- Builds: `LOOK=yoke` (two lower pockets kept, 134.3 g), `LOOK=yokeS` (solid neck and a 4.5 × 4.5 blend cone at the boss
  root, **147.2 g**, clean mesh). Today's part: 155.2 g.
- Print: Y up as today. Three pocket ceilings fewer to support; the hub's head overhangs the neck by less than 45°.
- Sweep with the solid-neck yoke and rim B on the flange ring (`clearance_yoke_rimB.json`): drum ↔ fork front 1.98 (as
  today, by design), fork front ↔ hub 2.19, ring ↔ fork front 2.03 at the -11° stop (2.13 with today's flat ring),
  ring ↔ cover 2.00. Nothing under the 2.0 rule beyond what today has.
- **What the opened area shows:** the RS03's turning output face out to r 36, then a 7 mm slot between it and the lip's
  bore (r 43) that goes deep into the motor. Today the dome hides it. No wire and no pocket is exposed. The slot is
  between a turning cylinder and a fixed bore (they shear, they do not close), but it is an open way into the motor for
  dirt and small fingers. A dark cover ring pressed into the lip (r 24.5-43, 2.5 thick) closes it; drawn on the sheet as
  an option, not built.
- **Pinch:** the yoke's back face passes 3.0 mm over the lip's face at every roll angle (too small for a finger to
  enter). The shoulder edges sweep over the slot; with the cover ring there is nothing under them but a flat face.
- **Looks worse than the quick cut:** a small notch at the top of the hub's head, where the driver-access bore for one
  RS02 screw comes out (today it comes out on top of the dome). And the shoulder ends are the tops of the two side
  strips: from above they read as the corners of a plate standing in front of the drum.
- Sheet: [size_audit/YOKE.png](size_audit/YOKE.png) (draft: the figures block is not on it yet).

## Rim B and the white band

- `LOOK=rimB`: the flange ring with the rolled rim (4.2 deep, R3.2 roll, eased to the 1.8 web by r 68.3). 38.1 g
  against 29.3 g. Prints flat on its inboard face, no support. Clean mesh. Clearance: above.
- Cover and ring in the visible white: PRINT_NOTES.md.

## To resume (in this order, one SolidWorks instance at a time)

All from `cad/scripts/shoulder`. The runners take a claim and beat it with the instance's PID.

1. `bash run_p.sh` with `NOSWEEP=1 TAGS="ffTS ffYS"`: builds the two solid-neck analysis builds and runs the P_* cases
   on them (about 20 minutes each). Then `NOSWEEP=1 NOBUILD=1 TAGS=ffT CASES_P=P_MZ CASES_F= bash run_p.sh` for the
   one case of today's part that was not reached.
2. Remove the line `until grep -q "proper check all done" ...` from `run_f2.sh` (or leave it and let step 1 write that
   line), then `bash run_f2.sh`: combines each fork front with the fork rear (`fork2_fea_part.py`, not yet proven: the
   combine call was fixed after its first failure and has not run since) and runs F2_MX, F2_MXn, F2_MXs, F2_MZ, F2_STOP.
3. `python ff_proper_post.py ffT ffTS ffYS`: the table by region for today, today with solid neck, yoke with solid neck;
   supported, unsupported, combined.
4. Write the figures block (`cad/_wip/shoulder-pass1/yoke_figs.json`, `{"lines": [...]}`) and re-render:
   `python render_yoke.py ../../../../../cad/_wip/shoulder-pass1/stl_look_rimB/ring.STL` from
   `hardware/shoulder/study-20261111/cad-pass1/scripts`.
5. If today's part is confirmed under target: the smallest fix (solid neck and root cone on today's outline is build
   ffTS) goes into the yoke design and into OPEN_ASSUMPTIONS.md item 40.

Results on disk (not in git): `cad/_sim/shoulder/FF_*_{today,yoke,yokeT,yokeS}.npz`, `P_*_ffT.npz`;
`cad/_wip/shoulder-pass1/ff_post.json`, `ff_proper.json`, `FF_*.txt`, `P_ffT.txt`, `queue5.log`.

## Open questions

- Is the 60 N·m stall a design case for the fork front, or only the software-limited 17 N·m of the roll controller?
- The share of the 17 N·m yaw torque between the RS03 output and the rear leg: the combined model.
- The yoke STL with pockets (`LOOK=yoke`) is not watertight after export (3 non-manifold edges); the solid-neck build
  is clean. Only the solid-neck build should go further.
