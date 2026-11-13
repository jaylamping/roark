# Benchmark run sonnet-b (set B)

Model: configured as `claude-sonnet-5-5[1m]` (fallbacks `claude-opus-5-5[1m]`, `claude-opus-5[1m]`). I could not read which model
served each turn, so the serving model may differ. Machine: holly-pc, SolidWorks 2026 SP0, `J:` already mapped, own worktree
`J:\code\roark-wt\sw-eval-sonnet-b` at `origin/claude/project-thread-3f5vlb` (d533ba0), claim `sw-eval-sonnet-b`.

**I kept to the rules for reading:** the only file under `tools/solidworks/playbook/eval/` I opened is `TASKS_B.md`; I opened no
other run's folder (fable-playbook, sonnet-playbook, sonnet-bare, t3-load-check, or any other). I read RULES.md, the playbook README
and pages 01 to 07, and `selftest.py` (read only, not run). Models and study files are in `cad/_wip/sw-eval/sonnet-b/` (not committed);
scripts, logs, measured json, `results.json` and this report are in this folder.

Times (from `date`, holly-pc clock):

| Task | Start | End | Minutes | Limit |
| --- | --- | --- | --- | --- |
| Setup and reading | 01:18 | 01:29 | 11 | |
| B1 hub | 01:19 | 01:28 | 9 (inside the reading time) | |
| B2 bracket | 01:29 | 01:44 | 15 | |
| B3 lighter | 01:44 | 01:58, plus the final convergence of S10 at 02:12 | 14, plus 2 | 45 |
| B4 tongue in a slot | 01:58 | 02:09 | 11 | 40 |
| B5 review and this report | 02:13 | 02:20 | 7 | |

Total about 62 minutes of work, well under the two hours aimed at.

Everything ran in one SolidWorks instance per script (one per step in B3). `sw_instance.py --status` showed another session's
instance `busy` at the start and none of mine afterwards.

## B1. Hub

`hub.SLDPRT`, `hub.step`, `hub.stl` (script `b1_hub.py`, 10 s of SolidWorks time).

| Check | Result |
| --- | --- |
| Volume | 21,865.54 mm3; hand 21,865.51 (flange + boss - bore - 6 holes - 2 dowels - keyway - set screw; the last two by numerical integration); 0.0001 % apart |
| Mass | 26.02 g at 1.19 g/cm3 |
| Box | X -30 to 30, Y -30 to 30, Z 0 to 25 |
| Bodies, rebuild | 1, no feature errors |
| STL | watertight, 1 shell, volume 21,811 (0.25 % under: facets, inside the 0.5 % limit), bounds in the model frame (y 29.99 only from chord of the Ø60 facets) |
| STEP | length unit milli-metre (`SI_UNIT` line with `.MILLI.`) |

Measured on the finished solid (cylinder faces, centre and radius, z range): flange R30 Z0-5, boss R13 Z5-25, bore R5 Z0-25 (box centre
x -0.115 because the keyway interrupts it), six R2.25 holes at (22, 0), (11, ±19.053), (-11, ±19.053), (-22, 0), two R2.75 holes at
(0, ±15), set-screw R2.0 axis at Z 22.6 (z range 20.6 to 24.6, y from the bore at 4.46 to 13). Keyway planes at y ±1.5, floor at x 6.4,
from the bore (x 4.77) to the floor, Z 0 to 25. Specification-only questions are in `results.json`; in short:

1. The Ø5.5 dowel holes on the Ø30 circle reach r = 12.25, 0.75 mm inside the Ø26 boss. Cut through the flange only, each leaves a 1.79 mm2
   crescent roof under the boss (faces found at z 5, y ±12.25 to ±13), so they are not full through holes.
2. The set-screw hole's top edge is at Z 24.6, 0.4 mm below the boss top: under the 0.6 mm minimum wall and under one hole diameter.
3. Set-screw hole has no thread or tap-drill size.
4. No fillet at the flange/boss junction; no print direction.

Decisions: dowel holes cut Z 0 to 5 only (as written: "through the flange"); set-screw hole only on +Y, from the axis to y = 14; the
keyway floor 6.4 is bore radius 5 + 1.4, which matches a 3 x 3 key (DIN 6885 groove depth 1.4), so I left it. Failed runs before it worked: 2, both my
script, not the helpers (a wrong `parents[]` depth for the import path; `np.trapz` removed in numpy 2).

## B2. Wall bracket

`wall_bracket.SLDPRT` (one body, 19,079.59 mm3 against hand 19,079.59, 22.705 g). The load patch must be its own face and the task says
one body, so the study ran on a twin (`wall_bracket_fea.SLDPRT`): arm to X 55, plus a second body X 55 to 65 bonded to it; its volume equals the one-body part's
(checked to 0.05 %).

Hand: M = 60 N x 55 mm = 3,300 N.mm, arm section 10 x 12 (I = 1,440 mm4): 13.75 MPa nominal at the root; a 3 mm fillet on a 12 mm
section is about Kt 1.4, so 19.4 MPa peak. Tip deflection F L3 / 3EI = 1.216 mm (no plate or shear). Predicted before the solve:
15k to 45k nodes at 2 mm, 1.2 to 1.6 mm, peak at the top root fillet. Got 36.7k nodes, 1.51 mm, peak at (7.3, 24.5, 52.1), the top
fillet. Check 3 (plain section): sigma_x on the arm top at X 30 is 6.98 MPa, hand 7.5 (7 %).

Both supports (the task does not say which; B3 names both):

| Support | Sizes | Peak vm outside 3 mm of fixtures | Reaction Fz |
| --- | --- | --- | --- |
| X0 face fixed | el 3.0 / 2.0 / 1.5: 17.96 / 18.88 / 19.46 (12.6k / 36.7k / 80.6k nodes); then el 2 with local 0.75 / 0.5 / 0.35 on the fillets: 19.43 / 19.33 / 19.48 | 19.5 | 59.999 |
| two screw-hole walls fixed | 16.12 / 16.72 (masked, see problem 2 below), el 1.5: 18.00; el 2 local 0.75 / 0.5 / 0.35: 18.10 / 18.41 / 18.47 | 18.4 (26 MPa at the hole mouth: the fixture singularity, excluded; the arm-top value is the same for masks from 1 to 3 mm) | 60.002 |

Von Mises is converged (last three local sizes within 0.8 %). Displacement 1.51 mm (wall) and 1.88 mm (screws) against hand 1.216: 24 %
over, which is the plate and root flexibility and shear that the cantilever hand value leaves out.

Failure measures by print direction (X0 support, el 1.5, outside 3 mm of the fixture):

| Layers stacked along | Tension across layers (allowable 22.5) | Interlayer shear (13) | Factors |
| --- | --- | --- | --- |
| X (arm standing up) | 20.1 | 7.3 | 1.12, 1.78 |
| **Y (on its side)** | 5.6 (8.9 at the finest local mesh) | 4.0 (5.3) | 4.0 and 3.3 (2.5 and 2.4) |
| Z (bed under the plate's edge) | 5.5 | 7.3 | 4.1, 1.79 |

The Y-direction layer values rise with refinement (5.6, 6.5, 6.9, 8.9 over the four meshes): they sit at the sharp inside edges where
the arm side faces meet the plate (X 5, y 15 or 25), which the 3 mm fillets do not cover. That is a singular edge, and a printed edge has
a radius of a few tenths of a millimetre; I report the finest-mesh value and give the factors from it. Where the peak is not at that
edge, tension across layers in Y is 5 to 6 MPa.

Load path: the 60 N goes through the arm top into the plate as bending (tension in the arm top, root fillet); the plate passes the
3,300 N.mm to the wall as a couple through the X0 face (or, with only the screws fixed, 92 N pull and push on the two screws).

Verdict: **pass, printed on its side (layers along Y)**, factors 2.31 yield, 2.5 tension across layers, 2.4 shear between layers
(finest mesh, both supports). It fails if printed standing up or on the plate's edge. Thinnest margin 2.31 on yield, and it is not much: 20 % more
load gives 1.93, a sharper printed corner would raise the fillet peak. Cheapest improvement: it is the orientation (zero mass); a
fillet on the arm's side edges at the plate would take away the singular edge. Not checked: bolt and wall-face behaviour (the wall can
push but not pull; both supports hold tension, so both are favourable at the bottom screw), creep, screw-head pull-through.

Failed runs: 2 (study name with a dot, error 2 and a misleading message; a typo in my own count check in the refinement script: expected 7 picks, there are 6). Measured results: `data/b2_measured.json`, `data/b2_refine.json`.

## B3. Lighter

45 minute limit, used 14 plus 2. Mass 22.705 g to **7.819 g, minus 65.6 %** (`wall_bracket_light.SLDPRT`, one body, rebuild clean).

What I took the fixed items to mean: screw holes unchanged (Ø4.5 at Y20, Z12 and Z48), the X0 face stays the planar wall contact face
(trimmed outline, but the same plane, same hole positions), the load patch X55-65, Y15-25, Z52 unchanged. Everything else changed.
I printed it on its side (layers along Y) from the start, because B2 showed it is the only direction that works, and every cut is
through Y so nothing needs support. Each step was solved with both supports (X0 face fixed, hole walls fixed), 60 N normal on the
patch, one study per support at el 1.5 with 0.75 mm on the fillets; factors are the worst of the two supports and are quoted against
yield 45, tension across layers 22.5, interlayer shear 13.

| Step | Change | Mass g | Yield | Tension across layers | Shear |
| --- | --- | --- | --- | --- | --- |
| S0 | B2 as specified | 22.71 | 2.31 | 4.0 | 3.2 |
| S1 | plate trimmed to 24 x 51 | 15.71 | 2.32 | 2.78 | 2.81 |
| S2 | arm depth tapered 13 to 4 | 13.20 | 2.44 | 2.86 | 3.00 |
| S3 | plate 4 mm | 11.94 | 2.39 | 2.84 | 2.89 |
| S4 | plate narrowed to a 14 mm strip | 9.51 | 2.20 | 4.64 | 3.60 |
| S5 | R5 root fillets, root depth 11 | 8.84 | **1.96** | 5.43 | 4.56 |
| S7 | rectangular web slot through the arm | 7.91 | **1.19** | | |
| S8 | longer web slot | 7.87 | **1.04** (43 MPa at the slot end) | | |
| S9 | pointed-end web slot X13-39 | 8.43 | 2.23 | | |
| S10 | window 8 x 16 in the plate | 7.82 | **2.08** | 3.55 | 2.47 |
| S11 | strip 12 wide, tip depth 3, window larger | 6.95 | 2.01 | 4.71 | **1.98** |
| S12 | S10 with root depth 12 | 7.52 | **1.94** | | |

Steps S5, S7, S8, S12 failed the requirement and were dropped; S11 is the lightest that nearly passes, but its yield factor is 2.01
(peak 22.0, 22.4, 22.0, 22.4 over four meshes) and the interlayer shear at the sharp plate/arm edge reads 1.98 at the finest mesh and
rises with refinement (4.8, 5.5, 6.1, 6.6), so it was **not accepted**. S10 was solved at four meshes (16.8k to 48.8k nodes): von
Mises 21.28, 21.58, 21.36, 21.64 (screws fixed), 19.7 (X0 face fixed); tension across layers 4.0, shear 5.3 (screws) and 6.3, 4.1 (X0 face).
So S10 at the finest mesh and the worse support: yield 2.08, tension across layers 3.55, shear between layers 2.47.

Governing requirement at the end: von Mises against yield with the hole walls fixed, at the top of the arm just outside the root fillet
(6.5, 20, 52). On S11 it reads the same 22.2 for masks from 1.5 to 3 mm from the hole walls (S9 the same, 20.4 to 20.2), so it is not set by the mask. The steps from S10
to S11 gain 11 % of mass and S11 then sits at the limit, so no further step was run (two steps in a row under 3 % was never needed).

Caveats: the arm tip depth of 4 mm and the slot flange of 2 mm are thin for printing (0.4 mm nozzle: five perimeters) but over 0.6 mm; the
S10 plate strip has 2.5 mm side strips beside the window; the shear and layer values at the sharp plate/arm edge are mesh-dependent as
in B2; displacement is 3.5 mm at the tip (the specification gave no stiffness requirement); the stresses under the screw-fixed support depend on the screws being rigid.

Failed runs: S3 failed with error 24 as the fifth study of one instance (at 17 GB free; the same inputs solved in a fresh instance), so
from S4 on each step ran in its own instance; the wall-face pick missed once because the window removed the pick point; S7, S8 and S12
failed on stress, not on the tools.

## B4. Tongue in a slot

Done in 11 of 40 minutes, solved. Script `b4_tongue.py`. Model: block with the slot (one body), tongue as two bonded bodies split at Z 30
so that the load patch Z 30 to 40 is a face of its own, four soft pads (Ø1.8 x 3, E 0.5 MPa, bonded to the tongue's Y faces at x ±2, z 24,
outer faces fixed, clear of both walls and of the load patch); bottom of the block fixed; two no-penetration sets (each wall with the
tongue face facing it), direct sparse solver, 80 N normal on the load face; materials PETG, pads soft.

Hand: rigid tongue, contacts at the top edge of the +X wall (z 20) and the tongue's bottom edge on the -X wall (z 8.1). Moments about
the lower contact: F_top = 80 x (35 - 8.1) / (20 - 8.1) = 180.8 N on the +X wall, F_bottom = 100.8 N on the -X wall. Rigid tilt then puts
the top 0.44 mm to +X. Predicted nodes 20k to 80k.

| Mesh (global / local) | Nodes | Reaction Fx | Shear through the tongue above contacts (z 26 / 28) | Shear between contacts (z 10 to 18) | Tip ux |
| --- | --- | --- | --- | --- | --- |
| 3.0 / 1.2 | 35,651 | -80.0 | 80.0 / 79.7 | -104.6 | 0.829 |
| 2.5 / 0.8 | 78,380 | -80.0 | 80.0 / 79.8 | -103.9 | 0.826 |
| 2.0 / 0.6 | 149,727 | -80.0 | 80.0 / 80.0 | -103.3 | 0.826 |

The shear force through the tongue (integral of tau_xz over a section) is 80 N where only the load lies above (it recovers the load to 0.1 %,
so the method is checked) and 103.3 N between the contacts. The balance gives wall forces **183.3 N on the +X wall and 103.3 N on the -X wall**,
against hand 180.8 and 100.8 (1.4 % and 2.5 %). Integrating the nodal normal stress over the wall faces instead gave 170 and 80 N
(sum 90, 11 % from equilibrium): nodal stress is too noisy at a contact edge, so I did not use it. Tip displacement 0.826 mm
(rigid hand 0.44 + tongue bending 0.08, then the +X wall's top edge moves 0.067 mm and is locally compressed; I expected 0.5 and got 0.83: the
wall is less stiff than the hand value assumed).

Validity checks:

- Reaction equals load: Fx -80.0 (three meshes).
- Contact engaged, with no penetration: tongue and wall faces approach to -0.002 to +0.0004 mm at z 20 on the +X wall and -0.0016 to -0.012
  mm at z 8.2 on the -X wall, and are 0.1 to 0.28 mm apart elsewhere. A reversed 0.001 N load moves the tongue 0.11 mm to the other wall
  (about the 0.1 mm gap), so the sets are contact, not bonds.
- Pads: all nodal reaction magnitudes on the pad faces add up to 0.38 N of 80 (0.5 %); the net is 0.08 N (0.1 %). Pads are far softer than I
  estimated by hand (0.009 N/mm from the reversed load against 0.58 N/mm by hand): one element through the pad.
- Floor not touched: the tongue's +X bottom edge drops 0.085 mm against the 0.1 mm clearance, so about 15 micrometres remain. A frictionless floor
  could carry no force anyway (nothing pushes the tongue down), so leaving it out is exact.
- No excessive-displacement warning.

Block peak von Mises: 35.0, 37.5, 41.0 MPa over the three meshes, at the top edge of the +X wall (4.1, -2.7, 20.0), a sharp convex edge pressed by a flat
face: it rises with refinement and is a singularity. The stresses that converge: 3.9 MPa 3 mm below the edge, 2.5 MPa mid-wall, 6 to 8 MPa at the slot
floor corner (also sharp). A Hertz line-contact estimate at 9.2 N/mm with an edge radius of 0.2 to 1 mm gives 127 to 57 MPa, so the edge will indent
and the printed edge needs a chamfer or a radius whatever the mesh says. `valid`: forces, displacement and equilibrium yes; the block peak as a
design number no. Not done: the tongue/wall contact friction (zero friction assumed; PETG on PETG would reduce the wall forces a little), a creep or yield
check of the edge, a second pad layout.

## B5. Review of the motor-plate report

Verdict on the report: **not ready to print**; its pass does not follow from its own numbers. Fourteen problems, most serious first.

1. **The verdict contradicts its numbers.** Von Mises factor 45 / 41.0 = 1.1; it is waved away because the peak is "at a hole edge". The hole
   edge is where the load or support enters and where printed parts break. Either it is a fixture singularity (then say how large the excluded
   value was, over what distance, and judge the part away from it with a second support) or it is real (then it fails). No pass mark is stated.
2. **Tension across layers uses the wrong component and the wrong allowable.** Printed flat means layers are stacked along Z, so the stress across them
   is sigma_z (`layer_stress((0,0,1))`), not sigma_x; and the allowable across layers is 22.5 MPa, not 45. Even taking their 19.5 MPa, the factor would
   be 22.5 / 19.5 = 1.15, not 2.3.
3. **Interlayer shear (13 MPa) is not reported at all.**
4. **The STL is in inches.** 16,700 mm3 / 25.4^3 = 1.019 in3: the 1.02 is the part's volume in cubic inches, not "rounding". The print file is 25.4 times too small
   in each direction. It must be re-exported in mm and checked (watertight, volume within 0.5 %, bounds in the model frame).
5. **The reaction is 96 N for 120 N applied, 20 % short.** Check 1 allows 1 %. "Close enough" means the load or the support is not what was meant
   (a face missing from the load or fixture, part of the load on a loose body), and every other number in the report is suspect.
6. **Hand estimate and FE differ by a factor of 11 and nobody notices** (3.4 MPa against 37.6 to 41.0). The hand section is also unclear: I = 4 x 40^3 / 12 is bending
   in the plane of a 4 mm plate; if +X is out of plane the right value is 40 x 4^3 / 12 = 213 mm4 and 33.8 MPa. Either way the 20 % rule fires and
   was not applied. It also treats the plate as a cantilever from a root when it is held at four hole walls, and gives no hand value for the hole (nominal x 3).
7. **Displacement never compared.** FE 0.9 mm; the hand values are 0.027 mm (in plane, I = 21,333) or 2.7 mm (out of plane, I = 213): neither agrees, check 2 not run.
8. **The node counts do not fit the part.** 16,700 mm3 at a 2.0 mm global mesh gives roughly 25,000 to 35,000 nodes (the 19,080 mm3 bracket gave 36,700 with fillet controls), not 212,000 (six to eight times too many).
   That is the signature of a study that solved a different problem (extra bodies, wrong geometry, mesh control on everything). The playbook asks for the
   expected node count before the solve; none was written.
9. **Convergence is claimed on two meshes with a 9 % change.** The limit is 5 %, three sizes, the same exclusion distance, and the governing measure (tension across
   layers), not just von Mises. A peak at a fixed hole edge that rises 9 % under refinement is the textbook singularity, so the number is not a stress at all.
10. **The fine solve (520,000 nodes) is over the 450,000 limit and was run overnight beside the forearm solve.** Solves of that size run one at a time
    (rule 6; two 390k-node solves crashed this machine, a 800k-node one ran out of memory and reported error 24). Whatever it returned was not under control.
11. **Support: four whole hole walls fixed.** That makes a singular edge at every hole mouth (the peak rises with refinement, as seen). No second support
    (fixing the ring under each screw head) was tried, and the excluded value and distance are not given.
12. **Load: "on the motor face" without saying how.** A rigid (remote) load stiffens the plate round the holes and can hide the governing stress, which the playbook found on its
    benchmark bracket; the load was not run a second way (even force on the screw holes where the motor sits).
13. **One print direction only.** No table of the three measures for the other directions, and no attempt to improve the design (print on edge, a radius at the hole, wider
    ligaments) before approving; a stressed part that fails in yield needs the changes tried cheapest first.
14. **Nothing to check the work against.** No model file or hash, no solver, no fixture and load node boxes (to see that the faces were right), no load-path sentence, no
    list of what was not checked, no statement of the requirement.

What has to be redone: re-export the STL in mm and verify it; write the expected nodes, displacement and peak location before a new solve; rerun the study with the load on
the faces that really bear (and again as an even force), the support in two ways, three mesh sizes with one exclusion distance, a reaction within 1 % of 120 N, then
report tension across layers (sigma_z), interlayer shear and von Mises against 22.5, 13 and 45 for each print direction, with the hand values reconciled (an 11-fold gap
first); one solve at a time, under 450,000 nodes. Until then: not approved.

## Where the playbook and helpers were wrong, unclear or missing

1. **`static()` name with a dot fails, with a misleading message.** A study called `B2_wall_1.5` failed with `study not created (2); a study of the same name
   already in the model?`. Nothing of the sort existed: renaming it `B2_wall_1p5` fixed it, so SolidWorks refuses the dot. `static()` should replace or reject characters
   it cannot take, and 05-fea.md should say studies are named without dots (the examples all use letters, digits and underscores, which hid it). A related trap: the study tag
   is `name[:24]`, so two long names with the same first 24 characters collide.
2. **`converge()` hides the real peak next to a fixture, and stops after two sizes.** It uses one exclusion distance of 2 x the coarsest size (6 mm for sizes up to 3), which on
   the screw-fixed bracket put the arm's fillet peak inside the mask: it reported 16.1 and 16.7 and "converged" while the same model gave 18.0 to 18.5. And it returns
   as soon as two rows agree, although the doc says give three sizes and that two agreeing rows can stop before a slow climb. I wrote my own loop with a fixed 3 mm mask and
   a local-size series.
3. **Error 24 on a later study of the same instance.** The fifth study (third model) of one instance failed with error 24 at 17 GB free; the same model and inputs solved in a fresh
   instance. 01-session says one job is one instance but not how many studies or models an instance can take. I ran one step per instance afterwards.
4. **No helper or recipe for contact force or section force.** 07-done requires the contact force summed from the results against the applied load, and 05-fea asks the pad share
   to be bounded, but neither says how to read either. I used a section integral of tau_xz in numpy (it recovered the load to 0.1 %) and the `post=` hook with
   `st.Mesh.GetNodes` plus the reaction array to split pad reactions by position; both worked but are undocumented. A `section_force(r, z0)` helper and an example of `post=` would
   save a lot. Integrating nodal stress over a contact face did not work (11 % off equilibrium).
5. **One-body requirement against a load on part of a face.** TASKS_B says one solid body and loads a 10 mm patch of a longer face; 05-fea says build touching bodies. The
   playbook does not say that the twin model must be proved equal to the one-body part (I compared volumes, 0.05 %), nor that the twin's name for the main body is the
   name of its last feature (the body was called `SCREWS`, not what `materials=` keys expect). `insert_body` needs one body per file, so the four pads are four files.
6. **`pick(..., at=...)` on a face that a later design change cut away fails with "got 0, expected 1" and nothing else**; fine, but a hint would help when it goes wrong after a geometry change.
7. **Fixture singularity: the defaults mislead.** `Result.peak()` and `away()` take two elements, `converge()` takes two coarsest elements, 05-fea says "a fixed distance"
   without a number. On a hole wall the peak depends on the mask (on the 14 mm strip, S4: 1 mm reads 25.8, 1.5 to 3 mm reads 20.4 flat, 5 mm reads 14.7); a recommended distance, or a scan of the peak against
   mask distance as I did from the saved nodes (it is cheap with `r.s` and `r.pos`), belongs in the page.
8. **Wall-force noise at a contact edge:** nodal stress on a contact face is unusable for forces (see 4). `Result` has no per-node contact pressure and `GetContactForces`-type
   results were not tried; 05-fea contact rule 6 mentions bolt tension from a section but not this.
9. **Missing from 04-export.md in practice:** `record_export.py` and `check_cad_layout.py` apply to promoted parts; for `_wip` models there is nothing to run, which the page says,
   so I did not run them.
10. Not wrong but worth saying: the hidden-window launches took 3 to 20 s each (fifteen launches), the other session's instance was `busy` at the start and never blocked a launch; the `--status`
    and claims commands behaved as documented; `selftest.py` is a good worked example and the `pick`/`face_info`/`Sk` helpers did everything I asked of them first time.

## What I did not do

Did not run `selftest.py`; did not promote any model to a region folder or run `record_export.py`; did not open any other folder in `eval/`; did not edit `sw_instance.py` or any
helper; installed nothing; touched no process that was not mine. The models stay in `cad/_wip/sw-eval/sonnet-b/` (gitignored).
