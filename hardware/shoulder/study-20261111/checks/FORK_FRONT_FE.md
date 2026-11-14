# Fork front: first finite-element cases, the yoke, and where the work stopped (2026-11-14)

**Status: work in progress, stopped at 01:25 local on 2026-11-14 for a reboot of holly-pc.** This page holds the results
so far and the queue to resume. Nothing real is changed: every build here is a look or analysis build.

## Short answer so far

> **Corrected 2026-11-14, 03:10 local.** The first version of this page said today's fork front was under target at the
> neck (0.92 / 0.70). That came from the fork front analysed alone, in bounds that left the rear leg and the 6808 out.
> In the combined model the fork front passes. The alone-model tables below are kept as bounds, not as a verdict.

- **The fork never had a finite-element case.** C_LOAD_SHARE.md used a beam model after the two-body model failed.
- **Combined model** (fork front and fork rear merged into one body, 6808 seat held radially): it solves, and it is the
  one to judge by. The RS02 seat moves 0.5 mm in it, against 2.9 to 6.6 mm in the alone bounds.
- **Today's adopted fork front passes everywhere:** lowest 1.74 (lower cheek, layer tension, sideways case). Boss root
  3.90 / 3.29 forward and 3.64 / 1.84 sideways.
- **The fork rear's thin leg does not:** 2.13 / 1.26 forward, 1.80 / 1.55 with the yaw reversed, **1.73 / 0.87
  sideways** (von Mises / layer tension, target 1.5). It is where the leg holds the cable channel (Y 384-392, back face).
- **The boss root is a sharp corner in CAD** (the boss r 22 meets the cheek's back face at Z 39 with no blend). In the
  combined model it still reads 1.84 or better on today's part.
- **A solid neck with a 4.5 mm cone, on today's outline, makes the sideways case worse at the boss root** (2.24 / 1.16
  against 3.64 / 1.84): the cone's rim lands on the upper dome pocket's inner edge. Today's part needs no change there.
- **The stop at a 60 N·m stall does not hold anywhere along the fork** (0.34 to 0.64). At the controller's 17 N·m limit
  the same figures are 1.2 to 2.3, still under 1.5 on layer tension at the boss root, the joint and the rear leg.
- **Still to do:** the yoke with solid neck in the combined model (running), then the fix for the rear leg.

## Combined model: today's adopted part and today's part with the solid neck

Safety factor, von Mises / layer tension, worst 0.5 mm ball. 0.7 mm mesh at the boss root. "Joint" is the region below
Y 362 (the sleeve and the joint between the two fork parts, which is solid in this model: an upper bound for six screws).

| Case | Region | Today as adopted (590,071 nodes) | Today with solid neck and cone (628,642 nodes) |
|---|---|---|---|
| Forward, yaw +17 (F2_MX) | Boss root | 3.90 / 3.29 | 3.99 / 2.27 |
| | Head and neck | 3.19 / 3.24 | 4.48 / 3.73 |
| | Lower cheek | 6.54 / 3.75 | 8.31 / 4.61 |
| | Joint | 1.88 / 2.99 | 2.19 / 3.39 |
| | **Rear leg** | **2.13 / 1.26** | 2.57 / 1.53 |
| Forward, yaw -17 (F2_MXn) | Boss root | 4.13 / 3.04 | 4.05 / 2.31 |
| | Rear leg | 1.80 / 1.55 | 2.09 / 1.85 |
| Forward, held by seats and pins (F2_MXs) | Boss root | 4.16 / 3.90 | 3.94 / 2.27 |
| Sideways (F2_MZ) | Boss root | 3.64 / 1.84 | **2.24 / 1.16** |
| | Head and neck | 2.58 / 1.85 | 4.57 / 2.42 |
| | Lower cheek | 3.10 / 1.74 | 7.22 / 3.56 |
| | Joint | 1.40 / 2.35 | 1.60 / 2.56 |
| | **Rear leg** | **1.73 / 0.87** | 1.90 / 0.96 |
| Stop, 1714 N on the tooth (F2_STOP) | Boss root | 0.51 / 0.36 | 0.93 / 0.88 |
| | Head and neck | 0.57 / 0.53 | 0.74 / 0.64 |
| | Lower cheek | 0.64 / 0.49 | 0.69 / 0.80 |
| | Joint | 0.36 / 0.34 | 0.43 / 0.42 |
| | Rear leg | 0.45 / 0.42 | 0.52 / 0.46 |

Seat deflection: 0.49 mm forward, 0.36 mm sideways (today); 0.39 and 0.31 mm with the solid neck.

The stop figures at the roll controller's 17 N·m limit are these times 3.53: today 1.80 / 1.27 at the boss root,
2.0 / 1.9 head and neck, 2.3 / 1.7 lower cheek, 1.27 / 1.20 joint, 1.59 / 1.48 rear leg.

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

## The fork front alone (bounds only): safety factor, von Mises / layer tension

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

## Stopped a second time, 01:25 local, for the reboot

Between the two stops the queue ran hidden (`SW_VISIBLE=0`, a switch in `swk.py`: no window on the screen; it works
with Simulation) and got this far:

- **The fork front and the fork rear do merge into one body** (`fork2_fea_part.py`, build ffTS: 188,033 mm³ kept of
  188,029). So the combined model can be solved; no F2 case has run yet.
- **Today's part with a solid neck and the root cone** (build ffTS, 172 g with its access bores; 516,351 nodes), boss
  root: supported 1.34 / 0.82 (yaw +17), 1.43 / 0.89 (yaw -17), 1.31 / 0.81 held by seats and pins. Today as adopted:
  0.93 / 0.70. Better, but its peak has moved to where the upper dome pocket (140-200°) meets the cone, at r 27: on
  today's outline the upper pockets' inner edge needs to move out as well. The yoke has no upper pockets.
- Seat deflection, supported: 1.45 mm (today 2.93).
- Not kept: P_MX on ffTS had solved but its result file was not complete when I stopped; re-run it.

## To resume (in this order, one SolidWorks instance at a time, hidden)

All from `cad/scripts/shoulder`. The runners take a claim and beat it with the instance's PID. `export SW_VISIBLE=0`.

1. `NOSWEEP=1 NOBUILD=1 TAGS=ffTS CASES_P="P_MX P_MXn P_MZ" bash run_p.sh`: the rest of ffTS and its five F2 cases
   (its combined part `cad/_sim/shoulder/fork2_ffTS.SLDPRT` exists). About 25 minutes.
2. `NOSWEEP=1 TAGS=ffYS bash run_p.sh`: builds the yoke with solid neck as an analysis build, merges it with the fork
   rear, six P cases and five F2 cases. About 40 minutes.
3. `NOSWEEP=1 NOBUILD=1 TAGS=ffT CASES_P=P_MZ CASES_F=F2_MX bash run_p.sh`: today's part, the one P case not reached
   (the F2 case named there fails at once, because today's merged part is made in the next step; that is harmless).
4. `bash run_f2.sh`: merges today's part (ffT) with the fork rear and runs its five F2 cases. About 20 minutes.
5. `python ff_proper_post.py ffT ffTS ffYS`: the table by region for today, today with solid neck, yoke with solid
   neck; supported, unsupported, combined.
6. Write the figures block (`cad/_wip/shoulder-pass1/yoke_figs.json`, `{"lines": [...]}`) and re-render:
   `python render_yoke.py ../../../../../cad/_wip/shoulder-pass1/stl_look_rimB/ring.STL` from
   `hardware/shoulder/study-20261111/cad-pass1/scripts` (under `capped.py`, with `PYTHONPATH=.`).
7. If today's part is confirmed under target: the smallest fix goes into the yoke design and into
   OPEN_ASSUMPTIONS.md item 40.

`cad/_wip/shoulder-pass1/resume.sh` chains steps of this kind; read it before using it, it was written for the first
stop.

Results on disk (not in git): `cad/_sim/shoulder/FF_*_{today,yoke,yokeT,yokeS}.npz`, `P_*_ffT.npz`,
`P_{MXb,MXnb,MXbs}_ffTS.npz`; `cad/_wip/shoulder-pass1/ff_post.json`, `ff_proper.json`, `FF_*.txt`, `P_ffT.txt`,
`P_ffTS.txt`, `queue5.log`.

## Open questions

- Is the 60 N·m stall a design case for the fork front, or only the software-limited 17 N·m of the roll controller?
- The share of the 17 N·m yaw torque between the RS03 output and the rear leg: the combined model.
- The yoke STL with pockets (`LOOK=yoke`) is not watertight after export (3 non-manifold edges); the solid-neck build
  is clean. Only the solid-neck build should go further.
