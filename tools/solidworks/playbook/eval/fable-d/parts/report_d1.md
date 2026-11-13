## D1. Buck board mount on the top front rail

`restate.md` was written first (08:42 to 08:44, before any modelling). Scripts: `d1_build.py` (models, exports, four
studies, one SolidWorks job), `d1_post.py` (stand-ins, pictures, clearance, open area, any-direction load),
`d1_conv.py` (three mesh sizes). Numbers: `d1_model.json`, `d1_post.json`, `d1_conv.json`.

### What I changed from the task, and why

**The envelope cannot be met, and I did not build as if it could.** The board is 60 mm wide; the envelope is 50 mm
wide and 45 mm high. With its keep-outs the board is a 60 x 18.6 mm rectangle in section, and no attitude fits
(table in `restate.md`: flat needs 60 in Y; tilted 55 degrees fits Y but needs 59.8 in Z; on edge needs 62 in Z;
hanging in front of the rail needs 18.6 in a 15 mm strip). I built the nearest thing: **board flat, centred, 5 mm over
the Y limit on each side, 23.6 mm high of the 45 allowed.** The printed part stays inside the board's own outline
(Y -30 to 30, Z 0 to 8). `envelope_ok` is false. One constant (`BOARD_Y0`) moves the overhang to one side.

### Two ideas that differ in kind

| | Idea A: posts and screws (chosen) | Idea B: pins and snap latches (crude model only) |
| --- | --- | --- |
| Board held by | four M3 screws through its own holes into brass inserts in four posts | dropped on four dia 3 pins, held down by two sprung hooks over the long edges |
| To get the board out | 2.5 mm hex key, four screws, lift | no tool: spread the two latches, lift |
| Y needed | 60 (the board) | 64.6 (latches stand 2.3 mm outside each long edge) |
| 10 g carried by | screws in brass, in every direction | upward: two 1.3 mm hooks in creeping, warm PETG; sideways: dia 3 pins in shear across layers |
| Needs to know | only the four holes | a clear 1.3 mm strip on both long edges of the board, which nobody has promised |
| Mass | 11.1 g | 14.8 g (crude model) |
| Picture | `pictures/d1_assembly_idea_a.png` | `pictures/d1_idea_b_snap.png` |

Chosen: A. It uses only what is known about the board, keeps the smaller excursion over the envelope, and holds the
board positively when the robot falls. B is the better idea only if the board comes out daily and its edges are bare.
A third idea, the board on edge in a card slot, was rejected on paper: 17 mm over the height limit and the slot would
sit on the edge the wires leave from.

### The chosen design (`buck_mount.SLDPRT`, `.step`, `.stl` in `cad/_wip/sw-eval/fable-d/`)

One printed piece, an H: a 12 mm wide, 4 mm thick spine along the rail top (X -42.5 to 42.5), a 20 x 16 mm tab at each
end with a dia 5.5 hole and a dia 10.5 x 0.5 spot face for the M5 (X +/-50.5, outside the board), and four 7 mm wide
arms out to the board holes at X +/-39, Y +/-26.5. Each arm ends in a dia 7 post, 8 mm high, with a dia 4.0 x 6 hole for
an M3 heat-set insert. Board underside at Z 8: 4 mm clear above the base where 3 mm are needed. R2 rounds where arms
and tabs meet the spine.

| Check | Hand | Model |
| --- | --- | --- |
| Volume | 9332.61 mm3 (spine 4080, tabs 2560, arms 2296, posts 923.63, insert holes -301.59, M5 -190.07, spot faces -62.83, rounds 27.47) | 9332.61 mm3 |
| Mass at 1.19 g/cm3 | 11.1 g | 11.1 g |
| Box | X -58.5 to 58.5, Y -30 to 30, Z 0 to 8 | the same |
| Bodies, rebuild errors | 1, 0 | 1, 0 |
| Insert holes, measured on the solid | dia 4.0 at (+/-39, +/-26.5), Z 2 to 8 | all four as specified |
| M5 holes, measured | dia 5.5 at (+/-50.5, 0), Z 0 to 3.5 | both as specified |
| Post tops | Z 8.0, dia 7.0 | all four |
| STL | watertight, 1 shell, volume 9331.24 (-0.015 %), box equal, in the model frame | pass |
| STEP | millimetres | pass |

Clearance, tested by sampling points against the STL (`sheet.inside`), share of points inside the mount:
board and the 14 mm above it 0 of 22,800; the 3 mm below it outside the dia 7 lands 0 of 14,856; the rail 0 of 5,800;
the T-slot 0 of 4,212; a dia 6 tool path over each M3 up to Z 45: 0; a dia 9.5 path over each M5 head up to Z 45: 0;
insert holes and M5 holes clear. Post walls and the material under the M5 heads are solid (all points inside).
The M5 heads clear the ends of the board by 3.25 mm.

**Open area:** the mount covers 31.8 % of the underside in plan, so 68.2 % is open (hand: 67.2 %); the top face has only
the four screw heads on it, 98.1 % open. `open_area_share` is the lower: 0.68. Counting the rail itself, 8 mm below the
board, as cover, the underside is still 57.1 % open.

### Fasteners

- 2 x M5 x 8 button head (ISO 7380) with 2 x M5 T-nuts in the rail's top slot: 3.5 mm of plastic under the head,
  4.5 mm of thread into the nut.
- 4 x M3 heat-set inserts (dia 4.0 x 6 hole) in the posts.
- 4 x M3 x 6 socket cap screws through the board: 1.6 mm of board, 4.4 mm in the insert.

### Board in, board out, and which tool reaches which screw

Mount first, once: drop two T-nuts into the top slot, lay the mount on the rail, two M5 from above with a **3 mm hex
key** at X +/-50.5. Both heads stay reachable from above with the board in place (3.25 mm beyond its ends).

Board out, mount stays on the rail (picture `pictures/d1_board_out.png`):

1. Power off. Leave the wires on if there is slack; otherwise undo the two pairs at the +X end.
2. Undo the four M3 screws from above with a **2.5 mm hex key**. Each has a clear dia 6 path straight up to Z 45.
3. Lift the board straight up. Nothing hooks it: the posts end under the board.

Board in: lower it onto the four posts, four M3, snug (0.4 N.m at most into brass in PETG).

### The 9 N case

Load path: board, through the four screws, into the post tops; each post bends its arm; the arms hand the load to
the spine; the spine to the two tabs; the tabs to the M5 heads. Support in the studies: only the two spot faces under
the M5 heads are held, so the rail gives no help (it would in pushing down). The fixed faces are the real clamped
faces, not a hole wall, so there is no second support to try.

**Hand, weakest section:** an arm at its root. 9 N over four posts is 2.25 N; arm 20.5 mm from the spine to the post
centre, section 7 x 4 mm, I = 37.33 mm4: M = 46.1 N.mm, **2.47 MPa** nominal, about 3.2 at the R2 round;
half way along the arm 1.235 MPa; deflection of the arm alone 0.091 mm, about twice that with spine and tab.

Four studies at 1.2 mm elements, 78,212 nodes each (predicted 66,565), reaction 9.000 N in each:

| Case | Load | Displacement mm | Peak von Mises MPa, where | Tension across Z layers | Shear between Z layers |
| --- | --- | --- | --- | --- | --- |
| Z, even force on the four post tops | 9 N down | 0.157 | **2.92** at (42.6, -11.5, 4.0), the round where an arm meets a tab | 0.25 | **0.96** |
| Z, rigid load at the board's centre of mass | 9 N down | 0.039 | 1.77 at a post foot | 0.65 | 0.85 |
| X, rigid | 9 N | 0.020 | 1.24 at a post foot | 0.60 | 0.67 |
| Y, rigid | 9 N | 0.072 | 1.45 at an arm root round | 0.95 | 0.63 |
| any direction, rigid, worst per node | 9 N | | 2.04 at a post foot, direction (0.31, -0.41, 0.86) | **2.38** at a post foot (39, 23, 4) | 0.94 |

- **Prediction against result.** Nodes 66,565 against 78,212 (1.17 times). The first study (rigid) gave 0.039 mm where
  I had written about 0.18: off by 4.7 times, so I stopped before reading stresses. Cause: a rigid load holds the four
  post tops level, which turns each arm from a cantilever into a guided beam (a quarter of the deflection, half the
  root moment: hand 0.023 mm and 1.23 MPa for the arm alone). The even-force study, where the posts are free to tip,
  gave 0.157 mm and 2.92 MPa against the hand 0.18 and 3.2. This is the playbook's warning about rigid loads, seen
  here; the real board is between the two, and I report the higher.
- **Plain section.** Top face of an arm half way along (even force): 1.237 MPa over 37 surface nodes, hand 1.235.
  (My first reading, `r.average()` over a 1.5 mm ball, gave 0.97: a ball round a surface point takes in nodes below
  the surface, where bending stress falls. Surface nodes only is the right check for bending.)
- **Any direction.** The three rigid cases share one mesh, so the stress for a 9 N load along any unit direction n is
  nx Sx + ny Sy + nz Sz. Per node I took the worst n: for von Mises and for layer shear the largest eigenvalue of a
  3 x 3 form, for layer tension the length of the three-case vector. That is the table's last row.
- **Convergence** (even force along Z, the governing case; one exclusion distance, 4 mm):

| Element mm | Nodes | von Mises | Shear between layers | Tension across layers |
| --- | --- | --- | --- | --- |
| 2.0 | 19,093 | 2.864 | 0.919 | 0.298 |
| 1.4 | 45,075 | 2.904 | 0.923 | 0.234 |
| 1.0 | 117,242 | 2.881 | 0.938 | 0.260 |

  Last step: von Mises 0.8 %, shear 1.6 %: converged. Tension across layers moves 11 % but is 0.26 MPa against 22.5
  allowed, so by the playbook's rule it is "not shown" for that measure in that case; it cannot change the verdict.
- **The post foot was not converged, and it is the lowest factor.** 2.38 MPa across layers at the sharp inside edge
  where a post meets its arm, only under the rigid load (it is the arm's end moment going up the post into a board
  assumed rigid). Within 0.5 mm there are 2 nodes; the mean within 1 mm is 1.06 MPa (26 nodes), within 2 mm 0.60: by
  the playbook's rule a corner, not a section. Hand for the section: (23 + 9) N.mm on a dia 7 / dia 4 tube, 1.06 MPa.
  I report the corner value as it stands.

**Factors (printed flat, layers stacked along Z):** yield 45 / 2.92 = **15.4**; across layers 22.5 / 2.38 = **9.4**;
between layers 13 / 0.96 = **13.6**. `sf_min` 9.4, governing: tension across the layers at a post foot. Requirement
taken as 2.0: met with 4.7 times to spare.

Print directions from the same results (lowest factor over the four cases and the any-direction row):

| Layers stacked along | Yield | Across layers | Between layers | Prints |
| --- | --- | --- | --- | --- |
| Z (flat on its underside) | 15.4 | 9.4 | 13.6 | no supports |
| X (on end) | 15.4 | 14.8 | 11.4 | supports under every arm, 117 mm tall on a 4 x 20 mm foot |
| Y (on its side) | 15.4 | 7.5 | 11.2 | supports under spine and arms |

On-end reads better across layers, but it is not printable sensibly and every factor is far above need. Flat it is.

### How it prints

Flat, underside (Z 0) on the bed, no supports: everything is a vertical extrusion; insert holes and M5 holes are
vertical. 0.2 mm layers, 4 perimeters, 40 % infill is ample; the 0.5 mm spot face is a top-surface step. PETG as
asked; ASA or PC if the board runs above 60 C at its holes. Inserts go in from above with an iron after printing.
Not sliced: no print project was asked for.

### Not the end

- **Thinnest margin:** 9.4, across the layers at a post foot, and only if the board is stiff. A fall is a shock, not
  10 g static: at 4.7 times the load it would reach the requirement.
- **Cheapest improvement found:** the part is over-strong, so mass. Base 3 mm thick in place of 4 scales arm stress by
  (4/3)^2 to 5.2 MPa (factor 8.7) and saves about 2.2 g of 11.1 (20 %); not built, because the 3 mm keep-out under the
  board and the 6 mm insert depth then leave no floor under the insert (the hole would go through: acceptable, but a
  change of detail I did not have time to prove). A 1 mm round at each post foot would remove the corner that governs.
- **Not checked:** the board's own stiffness and resonance on four posts; creep of PETG under the M5 clamp when warm;
  insert pull-out (by hand only: 2.25 N per insert against some hundreds); wire strain relief (none is provided: the
  wires are tied to the rail, which was not asked); the fit on a real rail (slot width, T-nut type); a printed part.
