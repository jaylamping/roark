# The fork in finite elements: today's parts, the yoke, and the rear leg (2026-11-14)

**Status:** the checks are done and **the yoke, rim B, the stiffer rear leg and the cover ring are adopted (2026-11-14)**. The real set has its own figures below ("The adopted set").

## Short answer

- **The fork never had a finite-element case.** C_LOAD_SHARE.md used a beam model after the two-body model failed.
- **Combined model** (fork front and fork rear merged into one body, 6808 seat held radially): it solves, and it is the
  one to judge by. The RS02 seat moves 0.5 mm in it, against 2.9 to 6.6 mm when the fork front is analysed alone.
- **Today's adopted fork front passes everywhere:** lowest 1.74.
- **The yoke with a solid neck and a blend cone at the boss root passes everywhere with more room:** lowest 2.78 on the
  fork front. It is 8 g lighter than today's part and no softer (seat 0.47 mm against 0.49 mm).
- **The fork rear's thin leg is under target with either fork front:** 0.87 (today) and 0.98 (yoke) on layer tension in
  the sideways case, 1.26 and 1.37 forward. Target 1.5.
- **The fix:** the rear leg 2 mm wider each side and 2 mm deeper at its upper stations (the LEG2 section, drawn on
  2026-11-12 and never adopted). With it the thin section reads 3.2 or better and nothing in the design cases is under
  1.6. It adds 2.4 g, at the back.
- **The stop at a 60 N·m stall does not hold with any of these** (0.36 to 1.1). At the controller's 17 N·m limit the
  yoke with the stiffer leg reads 1.27 at the joint between the two fork parts and 1.66 or better elsewhere.
- **The boss root is a sharp corner in CAD on today's part.** The yoke gets a 4.5 mm cone there.

> **Corrected 2026-11-14, 03:10 local.** The first version of this page said today's fork front was under target at the
> neck (0.92 / 0.70). That came from the fork front analysed alone, in bounds that left the rear leg and the 6808 out.
> In the combined model the fork front passes. The alone-model tables further down are kept as bounds, not as a verdict.

## The adopted set (real parts, 2026-11-14)

Combined model on the real fork front and fork rear as released (530,413 nodes; the real fork front keeps its
driver-access bore, which the analysis builds above leave out). Von Mises / layer tension, worst 0.5 mm ball.

| Case | Boss root | Head and neck | Lower cheek | Joint | Rear leg | Seat moves |
|---|---|---|---|---|---|---|
| Forward, yaw +17 | 4.44 / 2.48 | 3.77 / 2.42 | 4.79 / 3.78 | 2.18 / 3.22 | 5.22 / 3.69 | 0.41 mm |
| Forward, yaw -17 | 4.25 / 4.78 | 4.04 / 2.75 | 5.84 / 4.07 | 2.03 / 2.34 | 5.29 / 2.76 | 0.43 mm |
| Sideways | 3.41 / 1.93 | 4.40 / 2.82 | 7.40 / 3.51 | 1.76 / 2.62 | 4.60 / 2.58 | 0.26 mm |
| Stop, 60 N·m stall | 0.40 / 0.30 | 0.78 / 0.50 | 0.61 / 0.53 | 0.38 / 0.33 | 0.97 / 0.47 | |
| Stop at the controller's 17 N·m | 1.41 / 1.06 | 2.75 / 1.77 | 2.15 / 1.87 | 1.34 / 1.16 | 3.42 / 1.66 | |

- **Design cases: everything at or above 1.76.** The lowest on the fork front is 1.93 (boss root, sideways, layer
  tension); the lowest of all is the joint region's 1.76.
- **The real set reads lower at the boss root than the analysis build** (4.44 / 2.48 against 5.92 / 4.20 forward):
  the driver-access bore passes through the neck beside the boss root, and the peak sits at the bore's edge
  (X offset -6 to -12, Y 399-401). It still passes. Open item 42.
- **The stop case is worse at the boss root for the same reason:** 0.40 / 0.30 at a stall, 1.41 / 1.06 at 17 N·m.
- The 13 mm rounds at the shoulder ends (9.5 in the look build) cost nothing: lower cheek 4.79 / 3.78 or better.

## The six-screw joint between fork front and fork rear (2026-11-14)

The adopted fork front and fork rear as **two bodies**, joined as built: six M4 button heads from the fork rear's
counterbores into the fork front's inserts, each a bolt connector with a preload, and no-penetration contact on the
joint pad. Boss fixed, 6808 seat held radially. Intel direct sparse, 185,490 nodes (3.5 mm, 1.5 mm in the joint zone),
40-odd contact iterations each. Read in the joint zone (Y 338-366, within 14 mm of the joint plane), without the nodes
within 2 mm of a screw's head seat or insert bore, where the connector ties in. Von Mises / layer tension, worst 0.5 mm
ball. `fea_shoulder.py` J_*, `run_joint.sh`, `joint_post.py`.

| Case | Preload per screw | Joint zone, fork rear side | Joint zone, fork front side |
|---|---|---|---|
| Preload alone | 400 N | **1.01** / 3.14 | 3.86 / 4.74 |
| Forward, yaw +17 | 400 N | 1.02 / 3.44 | 3.19 / 3.75 |
| Forward, yaw -17 | 400 N | 0.99 / 2.38 | 3.15 / 2.10 |
| Sideways | 400 N | 1.04 / 3.31 | 3.07 / 2.08 |
| Sideways | 200 N | 2.11 / 3.13 | 3.03 / 2.09 |
| Stop at the controller's 17 N·m | 400 N | 0.98 / 1.29 | 2.29 / 1.37 |
| Stop at the controller's 17 N·m | 200 N | 1.88 / **1.34** | 2.33 / **1.41** |

- **The joint is stiff:** the RS02 seat moves 0.42 mm forward and 0.25 mm sideways, the same as with the joint solid
  (0.41 and 0.26). The six screws add no real compliance, so the merged model's load share stands.
- **The screws' own preload is the largest load on the joint.** At 400 N per screw (about 0.3 N·m on an M4) the
  counterbore floor under the head at X +20, Y 345.5 reads 1.01 on von Mises with no outside load at all, and 0.7 right
  at the head's edge. That floor is 3.0 mm thick; the head bears on a 29 mm² ring. At 200 N (about 0.15 N·m) it reads
  2.1.
- **Design loads:** with 200 N of preload the joint zone reads 2.09 or better sideways. The design loads add little to
  what the preload does.
- **Stop at 17 N·m:** 1.88 / 1.34 on the fork rear side (the pad's lower corner by the -27 and -22 screws) and
  2.33 / 1.41 on the fork front side (the insert boss at -27). Under 1.5 on layer tension, by a little, where the tooth's
  load crosses the joint. At a 60 N·m stall it would be about 0.4.
- **What to do:** tighten the six joint screws to **0.15 N·m**, not more (PRINT_NOTES now says so). If the stop at
  17 N·m is to clear 1.5, the lower pair's counterbore floors and the pad's lower corners want about 1 mm more material;
  that is a small change to the fork rear's skirt and can ride with the next fork rear revision.
- **Not read:** the bolt forces under load and the gap opening on the pad. The contact converged every time.
- These runs use a coarser mesh than the merged model and no fine zone at the boss root, so their figures outside the
  joint zone are not to be compared with the tables above.

## Verdict

| Question | Answer |
|---|---|
| Is the yoke with solid neck fit to adopt? | **Yes.** Lowest figure on the fork front in the design cases 2.78 (today 1.74). Clearances as today |
| Does it need a fix of its own? | **No.** The solid neck and the root cone are already in the look build `yokeS` |
| What is still under 1.5? | **The fork rear's thin leg**, with either fork front. Not a yoke question, but the yoke should not be adopted without it |
| Smallest change that clears it | **LEG2 on the fork rear:** +2 mm each side and +2 mm depth at the stations Y 380 and 402. Thin section from 0.98 to 3.22 (sideways), 1.37 to 5.5 (forward). +2.4 g |
| What would today's adopted fork front need, if kept? | Nothing at the fork front. The same LEG2 on the fork rear |
| Should today's part get the solid neck and cone? | **No.** On today's outline the cone's rim meets the upper dome pocket and the sideways case drops from 3.64 / 1.84 to 2.24 / 1.16 |
| Stop at a 60 N·m stall | Does not hold (0.36 at the joint, 0.47 to 1.1 elsewhere). Joey's software-limit decision, as before |
| Stop at the controller's 17 N·m | Yoke and stiffer leg: joint 1.27 / 1.34, lower cheek 2.3 / 1.9, rear leg 3.3 / 1.66, boss root 3.4 / 3.0. The joint between the two fork parts stays under 1.5 |

## Combined model: the yoke with solid neck, and with the stiffer rear leg

Safety factor, von Mises / layer tension, worst 0.5 mm ball. 0.7 mm mesh at the boss root. Analysis builds `ffYS`
(yoke, 501,813 nodes) and `ffYS` with the fork rear look build `frL2` (504,187 nodes).

| Case | Region | Today as adopted | Yoke, solid neck | Yoke and stiffer rear leg |
|---|---|---|---|---|
| Forward, yaw +17 (F2_MX) | Boss root | 3.90 / 3.29 | 5.92 / 4.20 | 6.41 / 4.74 |
| | Head and neck | 3.19 / 3.24 | 5.79 / 3.41 | 6.24 / 3.65 |
| | Lower cheek | 6.54 / 3.75 | 5.85 / 3.57 | 6.19 / 3.86 |
| | Joint | 1.88 / 2.99 | 2.04 / 3.19 | 2.02 / 3.23 |
| | Rear leg, thin section | **2.13 / 1.26** | **2.31 / 1.37** | 9.3 / 5.5 |
| | Rear leg, whole | 2.13 / 1.26 | 2.31 / 1.37 | 5.30 / 3.69 |
| Forward, yaw -17 (F2_MXn) | Boss root | 4.13 / 3.04 | 6.41 / 4.17 | 7.11 / 4.19 |
| | Lower cheek | 6.61 / 3.84 | 5.96 / 4.34 | 6.32 / 4.47 |
| | Joint | 1.75 / 2.31 | 1.88 / 2.51 | 1.87 / 2.47 |
| | Rear leg, whole | 1.80 / 1.55 | 1.92 / 1.64 | 5.61 / 2.87 |
| Forward, held by seats and pins (F2_MXs) | Boss root | 4.16 / 3.90 | 7.14 / 4.39 | not run |
| Sideways (F2_MZ) | Boss root | 3.64 / 1.84 | 5.82 / 2.78 | 6.34 / 3.04 |
| | Head and neck | 2.58 / 1.85 | 5.72 / 2.95 | 5.86 / 3.02 |
| | Lower cheek | 3.10 / 1.74 | 7.20 / 3.61 | 7.85 / 3.70 |
| | Joint | 1.40 / 2.35 | 1.62 / 2.63 | 1.62 / 2.68 |
| | Rear leg, thin section | **1.73 / 0.87** | **1.94 / 0.98** | 6.27 / 3.22 |
| | Rear leg, whole | 1.73 / 0.87 | 1.94 / 0.98 | 4.88 / 2.58 |
| Stop, 1714 N on the tooth (F2_STOP) | Boss root | 0.51 / 0.36 | 1.03 / 0.85 | 0.97 / 0.85 |
| | Head and neck | 0.57 / 0.53 | 1.01 / 0.61 | 1.11 / 0.67 |
| | Lower cheek | 0.64 / 0.49 | 0.65 / 0.52 | 0.66 / 0.54 |
| | Joint | 0.36 / 0.34 | 0.39 / 0.36 | 0.36 / 0.38 |
| | Rear leg, whole | 0.45 / 0.42 | 0.48 / 0.44 | 0.94 / 0.47 |

- Seat deflection, forward / sideways: today 0.49 / 0.36 mm; yoke 0.47 / 0.30 mm; yoke and stiffer leg 0.41 / 0.25 mm.
- "Joint" is everything below Y 362: the sleeve and the joint between the two fork parts, which is one solid in this
  model. Its figures are an upper bound for the real six-screw joint.
- The thin section's low figure on today's fork rear sits beside the cable channel at X ±13, Z -53 to -54: a thin wall
  between the channel and the skin. Two millimetres more width and depth roughly double that wall, which is why the
  gain is so large.
- Why the yoke reads higher than today's part at the neck although it has less material above the hub: its neck is
  solid and blended where today's has two pockets and a sharp root; the dome above the hub carried next to nothing.

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
- Sweep: in the adoption plan below. Nothing closer than today.
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
- Sheet: [size_audit/YOKE.png](size_audit/YOKE.png): today above, the yoke with rim B and the white band below, the yoke at
  roll +90, -11 and +45, the opened area with and without the cover ring, the 150 mm opening as a what-if, the figures.

## Rim B and the white band

- `LOOK=rimB`: the flange ring with the rolled rim (4.2 deep, R3.2 roll, eased to the 1.8 web by r 68.3). 38.1 g
  against 29.3 g. Prints flat on its inboard face, no support. Clean mesh. Clearance: above.
- Cover and ring in the visible white: PRINT_NOTES.md.

## Adoption plan (run on 2026-11-14: CAD_NOTES "Adopted 2026-11-14: yoke fork front")

**What would change on the real parts:**

| Part | Change | Mass | Source |
|---|---|---|---|
| Fork front | The yoke outline (`yoke.py`), solid neck, 4.5 mm cone at the boss root | 155.2 → 147.2 g | `LOOK=yokeS` |
| Flange ring | Rolled rim B (4.2 deep, R3.2, eased to the 1.8 web by r 68.3) | 29.3 → 38.1 g | `LOOK=rimB` |
| Fork rear | LEG2: leg +2 mm each side and +2 mm depth at the stations Y 380 and 402 | 63.7 → 66.1 g | `LEG2=1` |
| Cover ring (new, optional) | Dark PETG ring pressed into the drum's lip: OD 86 (the lip's bore), bore Ø52, 2.5 thick at Z 33.5-36 with a 3.5 mm skirt on its outside for grip | about 14 g | not built |
| Pitch loop cover, flange ring | Printed in the visible white (colour only) | | PRINT_NOTES.md |

**Steps, in order:**

1. `dims.py`: three defaults switched on, each with its date and Joey's words: `FORK_YOKE = True` (the fork front builds
   as `yokeS` does now without `LOOK`), `RIM_B = True`, `LEG2` on in `envelope.py`. The `LOOK` names stay for comparison.
2. Real builds of fork front, fork rear and flange ring (`build_parts.py fork_front fork_rear ring`), integrity scan of
   each. The yoke's STL had a zero-area triangle in two of its look builds and was clean in `yokeS`: the scan decides.
3. Clearance sweep on the real set (`check_clearance.py`), compared pair by pair with the adopted set of 2026-11-14 and
   with the look-build sweep on this page. Stop if any pair is under 2.0 that was not before.
4. The shell skin check (`check_shell_trim.py`): the yoke is smaller than today's fork front above the hub and the same
   below, so it can only gain; the 2.46 mm finding at pitch -30, yaw -90 stays as it is.
5. Exports: `cad/exports/shoulder/shoulder_fork_front_left`, `shoulder_fork_rear_left`, `shoulder_pitch_flange_ring_left`
   (STEP and STL), each recorded with `tools/cad/record_export.py`; layout check 0 errors.
6. Assembly: rebuild the shoulder assembly (not done at the hub adoption either: one rebuild covers both).
7. Docs: PRINT_NOTES.md (summary table masses; fork front section: yoke, three pocket ceilings fewer, the driver-access
   bore now comes out at the top of the hub's head; flange ring: rim B, still flat on its inboard face; fork rear: leg),
   CAD_NOTES.md ("Adopted" entry with masses and the sweep table), SIZE_AUDIT.md (mass line, the fork front's face),
   C_LOAD_SHARE.md (a pointer to this page in place of "the beam model is the result"), OPEN_ASSUMPTIONS item 40
   settled.
8. The cover ring, if wanted: a new small part (`shoulder_roll_cover_ring_left`), built, swept (2.0 to the fork front's
   cone at Z 36, 2.86 to the motor's turning face, 3.0 to the yoke's back), exported, a line in PRINT_NOTES ("dark PETG,
   flat, no support, press in after the eight lip screws"). It needs nothing from the other parts.
9. One commit for the adoption (the pre-commit layout check wants the parts and their records together), then the push.

**Not in the plan:** the stop path at a stall (Joey's decision), the six-screw joint's own check, the right shoulder.

**Look-build sweep, all three changes together** (`clearance_yoke_adopt.json`: yoke with solid neck, rim B ring,
fork rear with the stiffer leg; brief poses and the stops):

| Pair | Adopted set of 2026-11-14 | With the three changes |
|---|---|---|
| Drum ↔ fork front | 1.98 | 1.98 (by design: the drum's 2 mm envelope) |
| Fork front ↔ hub | 2.19 | 2.19 |
| Fork front ↔ port cap | 2.62 | 2.66 |
| Flange ring ↔ cover | 2.00 | 2.00 |
| Flange ring ↔ fork front | 2.13 | 2.03 (rim B, at the -11° stop) |
| Rear cap ↔ fork rear, roll 0 and 45 | 2.00 / 1.99 | 1.99 / 1.99 |
| Rear cap ↔ fork rear at the stops | 0.03-0.05 (the stop's contact) | 0.03-0.10 (the same contact) |

Nothing moved by more than the sweep's accuracy except the ring's rim, which is still over 2.0. The stiffer leg changes
no clearance: its extra width and depth are behind and beside the leg, away from the cap.

## Open questions

- Is the 60 N·m stall a design case for the fork front, or only the software-limited 17 N·m of the roll controller?
- The share of the 17 N·m yaw torque between the RS03 output and the rear leg: the combined model.
- The yoke STL with pockets (`LOOK=yoke`) is not watertight after export (3 non-manifold edges); the solid-neck build
  is clean. Only the solid-neck build should go further.
