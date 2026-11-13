# REPORT, benchmark run sonnet-c2 (set C)

Model id: claude-sonnet-5-5. Worktree pinned at f03828d. Kept to the rules: the only file under `playbook/eval/` that I opened was `TASKS_C.md` (not `EVAL.md`, not other runs' folders, not the files linked from 05-fea.md). One instance per script through `job(wait_s=1800)`, no `timeout`, no process of anyone else touched, no helper edited.

## Step 0 and times
- Selftest: `PASS model beam rod extras loads contact`, 103 `ok` checks, no FAIL, no traceback (`selftest.log`).
- C1 clock start 09:35 (from `date`). C1 done 09:36. C2 start 09:37, restate.md 09:39, checkpoint_01 09:41. Last solve finished 10:48, report written about 10:58. About 83 minutes from the start of C1; C2 itself was cut short of 100 min only by me stopping. Of that, about 20 minutes were launches waiting behind other sessions' solves (the 3-run series at 10:36 sat 9 minutes before its first solve).

## C1, the link as it is
Volume 219,436.04 mm3 against hand 219,436.19 (0.00 %), mass 261.03 g (1.19 g/cm3), one body, STL watertight, STL volume 219,351.8 (-0.04 %), box in the model frame (-35, -22, -215 to 35, 22, 35). Shape: flat_share 0.91, largest_flat 0.144, sharp_per_area 12.3. Picture: `pictures/c1_boxy.png`: a round disc with a bore and six small holes, a square beam, a block with two flat cheeks and a pin hole; all flat plates. Script `c1_boxy.py`.

## C2, what the form is
One solid: a revolved elbow flange (D70, 8 mm, rim rounded with polyline arcs, back dished with a raised lip outside r 28.6), a ridge on the back that follows the cable passage, and one stem lofted through eight superellipse sections (14.5 x 12.5 at the root, waist 12.5 x 11.5, swelling to 14.5 x 23 at the wrist, rounded end at Z -212). The slot between the cheeks, the pin hole and a straight D6 cable bore (axis X 0, Y +2, from the Ø30 bore at Z -15 down into the slot) are cuts. Shape numbers: flat_share 0.91 to 0.205, sharp_per_area 12.3 to 6.51 (the faceted revolve and the sharp loft ends keep the second number up). Mass 148.1 g against 261.0 g. One body, watertight, volume STL 124,484 vs SolidWorks 124,901 (-0.33 %), STEP in mm (`.MILLI.`), STL in the model frame (box -34.9..34.9, -23.7..23.7, -212..35).

How the section through the shaft was made (the elbow-to-wrist cable passage, and the bone itself): sections are closed splines on parallel Z planes from `sec()` in `c2common.py`: a superellipse |x/a|^n + |y/b|^n = 1 with 24 points at equal angle and the same start point, so the loft never twisted. The squareness n goes from 2.0 at the root to 3.5 at the cheeks, which keeps the cheeks flat enough to hold 9 mm of material round the pin. The passage is a Ø6 cut along Z.

## Fixed items, measured on the exported STL (`c2_checks.py`, point-in-solid, all pass)
Ring solid at Y -3.9 and empty at Y -4.1 over r 15.3 to 30.8 (288 points each, 0 wrong); six D3.4 holes clear (144 points) with solid walls at r 1.85; D30 bore clear; D7 x Y 4.2..13.8 screw clearances clear (360 points); pin D8 clear over Y -30..30; material at r 4.1 to 9.0 round the pin solid at Y 16.2, 17, 18, 19, 20, 21; both cheek inner faces at Y +-16 flat over D16 (solid behind at 16.1, clear in front at 15.9, 100 points each); slot clear |Y| < 15.9 from Z -183.2 down and the D30 swing disc clear; passage clear over Z -15 to -183 and walled at r 3.4 (wall 3.0 mm in the flange, 3.8 to 10.7 below Z -34; the checker prints 0.6 because its first section sits on the opening into the bore, which is not a wall). Not measured on the native solid with `pick` + `face_info`, only on the STL.

## Loads: 60 N at the pin, ring held (`c2_fea.py`)
Support: the whole Y -4 ring face fixed. Load: rigid `remote` force on the two pin-hole faces at (0, 0, -200), mesh 3 mm with 1.2 mm on the pin faces. Predicted before the run: nodes about 78k (got 93k), tip displacement about 3 mm (got 2.6 mm for X, 5.3 mm for +Y; by hand F L^3 / 3 E I with I = 15,000 mm4 gives 3 mm for the weaker plane), peak at the stem root (it was). Reaction equals the load in every case (60.0 N). Stress is read outside two elements of the fixture and load (the fixture edge itself reads 45 to 58 MPa and is excluded as singular).

| case | von Mises MPa (factor on 45) | layers X / Y / Z: tension MPa (factor on 22.5) | layers X / Y / Z: shear MPa (factor on 13) |
|---|---|---|---|
| +X | 10.2 (4.4) | 5.5 (4.1) / 4.3 (5.2) / 10.9 (2.07) | 3.4 (3.8) / 1.4 (9.2) / 3.5 (3.7) |
| -X | 10.2 (4.4) | 5.2 (4.3) / 4.2 (5.4) / 11.4 (1.98) | 3.4 (3.8) / 1.4 (9.2) / 3.5 (3.7) |
| +Y | 21.1 (2.13) | 3.4 (6.7) / 9.0 (2.5) / 5.6 (4.0) | 5.9 (2.2) / 6.6 (1.96) / 7.9 (1.65) |

Print direction chosen: on its side, layers stacked along X. Lowest factors there: von Mises 2.13 (+Y), tension across layers 4.12 (+X), shear between layers 2.21 (+Y). Printing with Y up gives shear 1.96, and standing up (Z) gives layer tension 1.98 and shear 1.65: both fail, so X is the only direction that clears 2.0 on all three, and only on the 3 mm mesh. Supports: tree supports under the stem's lower flank where the oval is steeper than 45 degrees (a band about 6 mm wide each side of the lowest line), under the flange's lower rim (it stands on edge) and the top of the Ø30 bore; the Ø3.4 and Ø8 holes are horizontal and print as they are. Part is 247 mm long in Z, so it lies along a bed diagonal or an edge of a 256 mm bed with 4 mm to spare per side: tight.

## Convergence and the second support: the requirement is NOT shown
+Y, ring held, peak outside the exclusion: 4 mm 29.7 MPa (61k nodes), 3 mm 21.1 (93k), 2.5 mm 23.2 (125k nodes), factors 1.52, 2.13, 1.94. It is not monotone and the last step moved +10 %, so by 07-done.md the verdict is "not shown", and the finest value is under 2.0. Support tried a second way: the six screw-hole walls fixed instead of the ring (3 mm): 29.1 MPa (1.55), peak at the fixture edge (8.3, -4.0, -31.7), so the ring-held 21 is optimistic. Tension and shear convergence were not run (no time). Not converged also because the stem start against the flange ridge is a sharp loft end with no radius. So: gate not passed on the requirement line, passed on fixed items, one body, mass and watertightness. The cheapest improvement I did not try: a 3 to 4 mm radius (or a longer loft ramp) where the stem meets the ridge at Z -32; it is the peak at every mesh size.

## Runs that failed before it worked, and why
1. First C1 run: path bug in my script (`parents[4]` for a file five levels deep). 2. C1 second run: my hand volume subtracted an overlap between the block and the beam that does not exist (the beam ends at Z -170 where the block starts); `expect_dv` caught it (17,600 against 5,600). 3. Several PowerShell command errors of mine (a heredoc, `.Replace` with a count, `&&`). 4. Junction fillet between stem and flange: no round built (22 edges after the revolved flange; 4 edges with the first extruded flange where it rounded the flange rim instead of the junction). 5. `edges_where` found 0 edges on the flange rim circles. 6. A loft whose sections move in Y (y0 steps of 1 to 2 mm) failed on every such pair ("loft failed"). 7. Thicker root and lip each moved the peak only from 44 to 29 MPa; the cause of 29 was a 1 mm skin from my own cable passage through the 8 mm flange (peak sat at Y 4.2 beside it), found only after reading where the nodes were. 8. A first-section tweak at Z -24 pushed the -Y surface proud of the mounting ring (the STL check caught it; 10 points wrong); reverted.

## Where the playbook or a helper was wrong, unclear or missing
- `03-modelling.md` says the loft recipe holds while the sections keep one shape. It does, with the superellipse and equal-angle points. It does not say that a section whose Y centre moves breaks the loft; that was the second-biggest loss of time.
- `edges_where` cannot find the full circles of a revolved or extruded disc, though the page says a closed loop is tested in the middle. A fillet of the rim needs another route (I drew the rounds into a revolved profile). The page should say so.
- `fillet()` returns None on failure with no reason; there is no way to see which edge refuses.
- `bbox(d)` of a loft is the control-point box: SolidWorks said Y +-26.4, the mesh is +-23.7. The page says to match `bbox` against the STL within 0.1 mm; that is false for splines.
- `sheet.py` has no section view; for a passage and the ligament round the pin I had to write point-in-solid checks myself. A `--section` option (a plane through the part) would have saved time. Its `sharp_per_area` counts the facets of a revolved polyline as sharp edges, which makes a smoothed flange look sharp.
- 07-done.md asks for the print direction table from one result. `Result.layer_stress` / `layer_shear` return a tuple `(value, [x y z])`, not a number; `05-fea.md` says so only in the helper's docstring.
- The rigid remote load on the pin faces holds both cheeks level and stiffens the wrist; I did not run the half-hole second way.
- `job(wait_s=1800)` waits silently. The tool's 10-minute limit then moves the command to the background; a note on running such jobs with `run_in_background` would have saved a bad first reading of my own 9-minute wait.
- RULES.md and 01-session.md are consistent with what I did. I found nothing wrong in 02-com.md.

## What I did not check
Tension and shear convergence; a finer mesh at the stem root; buckling (the stem is stocky, slenderness low); the load on the half-hole that bears; the native-file measurement with `pick`/`face_info`; support volume and print time; a real print orientation check with a slicer; whether the cable bends at the slot ceiling into the swinging part; whether the faceted flange rim matters.

## Files
`c1_boxy.py`, `c2_ideas.py`, `c2_build.py`, `c2_checks.py`, `c2_fea.py`, `c2common.py`; `c1.json`, `c2_checks.json`, `c2_fea_*.json`; `restate.md`, `DESIGN.md`, `results.json`, `pictures/` (c1_boxy, checkpoint_01 to 07, idea_a, idea_b, c2_before_after). Models and exports are in `cad/_wip/sw-eval/sonnet-c2/` and are not committed.
