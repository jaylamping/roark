# REPORT, run sonnet-c (model id: claude-sonnet-5-5)

I kept to the rules: the only file I read under `eval/` was `TASKS_C.md`. I opened nothing of other runs, other task files or `EVAL.md`.

## Times (`date` on holly-pc)
- 04:40 start, reading 04:40-04:41. C1 built, exported and pictured 04:41-04:45 (one 16 s SolidWorks run).
- Restate 04:45. C2 start 04:44. checkpoint_01 04:50 (6 min). Ideas A and B 04:50-04:52.
- Shape work 04:53-05:17 (loft failure, silhouettes, dome). First FEA 05:05. Redesign FEA 05:17.
- Final build 06:00, final FEA 06:04-06:06, report 06:12. Total about 92 minutes; two launches waited 2 to 2.5 minutes behind other sessions.

## C1
Boxy link as specified. Volume 219,436 mm3 against hand 219,436 (beam-disc overlap integrated); STL 219,352 (0.04 % lower), watertight, one body, mass 261.1 g.
`sheet.py`: flat_share 0.91, largest_flat 0.144, sharp_per_area 12.3. `pictures/c1_boxy.png` shows a disc, a box beam and a fork, as drawn.

## C2 result
`link_organic.SLDPRT/.step/.stl` are in `cad/_wip/sw-eval/sonnet-c/` (not committed). 134,256 mm3, 159.8 g against 261.1 g, one body, watertight, STEP in mm (`SI_UNIT ( .MILLI., .METRE. )`).
Shape numbers: flat_share 0.155, largest_flat 0.076, sharp_per_area 7.89 (boxy 12.3).
`pictures/c2_before_after.png`: boxy on top, organic below. Looking at it: a smooth tapering strap with a domed elbow boss and a forked end. It is still flat, not round.

### Fixed items, measured on the STL (`c2checks.py`, `checks_final.json`)
- Mating plane Y -4: all 11,094 ring points (R 15.5 to 31, off the holes) have material just above and none just below.
- Six Ø7 x 10 clear cylinders (Y 4 to 14): 0 of 28,800 sample points in material. Sampled to R 3.3 only, so the last 0.2 mm of wall is untested. They are pockets in a 12 mm dome.
- Slot |Y| < 16, Z < -183, X +-34: 0 of 18,445 points in material.
- Pin ring: nearest outline vertex to the pin axis, hole excluded, is 10.6 to 12.8 mm at Y +-16.3, +-18, +-20. That is at least 6 mm round a Ø8 hole.
- Cheek inner faces: material just outside, none just inside, at Y +-16, round the pin out to R 8.
- Ø6 passage, X 0, Y 2.5, Z -15 to -176 (bore wall to slot roof): 0 of 1,944 points in material, and the STL section is clear at every Z.
- NOT measured on the solid: bore Ø30, the six Ø3.4 holes on Ø50 and the Ø8 pin as faces. `measure.py` was written for it but its launch failed ("PID 131052 did not answer for 300 s", another session's solve), and I ran out of time. The checks above only show them indirectly (the ring section and the pin ring).
- Assumption of mine: no material below Y -4 within R 36 (the motor). A MOTOR_CLEAR cut removes 126 mm3.
fixed_items_ok: true on what was measured, with the gap above.

### Load cases: 60 N at the pin as a remote load carried to the two Ø8 hole faces, ring Y -4 fixed, PETG, el 3.0 mm, 104,484 nodes
I predicted about 60,000 nodes (off by 1.7) and a peak at the neck; it sat at the dome/neck seam.

| case | vM away (MPa) | SF yield | tension across layers, print Y | SF | shear between layers, print Y | SF | tip movement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| +X | 5.05 | 8.9 | 2.21 | 10.2 | 0.95 | 13.7 | 1.63 mm |
| -X | 5.05 | 8.9 | 2.23 | 10.1 | 0.95 | 13.7 | 1.63 mm |
| +Y | 8.29 (8.48 at 172,573 nodes) | 5.4 (5.3) | 4.60 (4.89) | 4.9 (4.6) | 3.06 (3.76) | 4.25 (3.46) | 4.6 mm |

- Reaction equals the load in all cases (60.0 N). Hand value for +Y: M = 60 x 172 = 10.3 N.m over a neck about 35 x 18 mm is about 10 MPa; FEA 8.5. Hand tip movement 6 mm, FEA 4.6.
- Print directions from the same +Y result (worst of the three cases): layers along Y: tension SF 4.6, shear 3.46. Along X: 11.5 and 3.07. Along Z: 3.0 and 3.05. Y is chosen, though all three clear 2.0 on the final model (earlier iterations did not: shear SF 1.0 to 1.4 for X and Z).
- Governing: shear between layers in +Y. Convergence from 104k to 173k nodes: vM +2 %, tension +6 %, shear +23 % (rising, at the seam). By the letter of 07-done.md shear is "not shown", though SF stays above 3 at the finest size.
- Second ways NOT done on the final model: the screw-hole support, the bearing load as a force on half-holes, a third mesh size.
- On the previous iteration (peak 17.3 MPa) fixing the six hole walls instead of the ring gave 22.2 MPa (SF 2.03), so the hole support is the harsher one. Unexplained: the final model's +Y peak is 8.3 MPa against 17.3 for the iteration before; between them I only added a 126 mm3 motor cut and moved two neck keys. I do not fully trust the margin at the seam.

### Print
Not sliced. It needs a 66 x 245 mm footprint, which fits 256.
- Orientation: lie it with Y vertical, the mounting face up, so the ring prints as a top surface and the six screw holes and the pin hole are vertical and round.
- That puts the upper cheek face on the bed.
- Supports go under the dome and the neck underside, and fill the slot between the cheeks (about 32 mm high) up to the lower cheek.

## Checkpoints (time, picture, what was missing against the request)
- 04:50 `checkpoint_01.png`: crude loft. Missing: twist at the wrist, stub neck at the disc, plain tube.
- 04:58 `checkpoint_02.png`: silhouettes and fillet, loft gone. Missing: rounded-rectangle section with flat broad faces, abrupt neck, disc not blended.
- 05:17 `checkpoint_03.png`: dome and pockets. Missing: still a flat strap, seam notch, roof corner fillet missing.
- 05:39 `checkpoint_05.png`: thicker neck. Missing: round sections, seam crease. (checkpoint_04 is the version with the seam fillet that built on 3 of 4 edges; dropped.)
- 06:01 `checkpoint_06.png`: final. Missing: roundness, a seam fillet, slicing, supports second way on the final model.
Ideas: `idea_a.png` (the first loft, pinched) and `idea_b.png` (flat leaf). I chose A because B is a plate and weak in +Y bending.

## Runs that failed before it worked, and why
1. `np.trapz` is gone from this numpy: the C1 script died after the model was built. I recomputed the hand volume outside SolidWorks.
2. Loft pinch: 6 variants, none cured it (see DESIGN.md). About 12 minutes. Cause not found. A loft with two sections, or in a new part with no body, fails in `loft()` with "sections must be closed" although they are closed.
3. Idea B loft failed twice (my duplicate section, then thin sections) and was rebuilt as an extruded leaf.
4. Silhouette fillet: R above 5 failed at a neck 15 mm wide. `edges_where` could not select the long corner edges, so I wrote my own selection.
5. First +Y FEA: 115 MPa at the narrow pad (SF 0.39), so I added the dome.
6. `c2fea.py` assertion: my ring pick returned 2 faces and my pin pick 4 (roof R4 fillets also have r 4); fixed with `inside=`.
7. The DOME revolve failed twice after I changed two neck keys that should not matter; reverting worked. Unexplained.
8. A seam fillet that built on 3 of 4 edges made the peak worse (30 MPa on the unrounded edge); removed.
9. My own wait-watcher fired at once on a stale log.

## Playbook and helper problems
- `sheet.py` prints "wrote ..." before the JSON on stdout, so redirecting it to a file gives invalid JSON. The pictures made a pinch and a twist plain, but a 6 mm crease is hard to see at this size. `sharp_per_area` went 12.3 to 7.9 for a form that is smoother but not organic: the numbers do not tell a smooth strap from a bone.
- `swkit.loft()`: closed-spline sections pinch to a point midway between two sections, silently. The recipe "Organic skin" in 03-modelling.md does not warn. Equal-angle sampling did not help.
- `swkit.bbox()` returns a loose box for curved faces (X +-42 for a 66 mm part); use the STL bounds.
- `swkit.edges_where` tests start, middle and end, so a closed-loop edge, or a long edge starting outside the test region, is never found. Closed edges are common after two cut extrusions.
- 05-fea.md: a `pick(kind='cyl', r=4)` also catches R4 roof fillets, so `inside=` is not optional.
- 07-done.md wants a table of print directions per case. `layer_stress` and `layer_shear` give the numbers, but no helper builds the table.
- 01-session.md says to work on meshes in chunks of 20,000 points. trimesh `contains` on a 12k-triangle mesh at 20,000 points allocated 442 MB per chunk and died at capped.py's 6,144 MB; 1,000 works but takes minutes.
- `launch()` waits silently behind another session's solve: my first jobs looked hung for 2 minutes. A "waiting for pid N (busy)" line would help. My last launch raised after 300 s, as the playbook says it can.
- `sw_instance.py --status` crashed once with `pywintypes.error 1400 GetClassName` while an instance was closing.
- The 100 minutes did not fit iteration on form: launch waits and solves of 35 to 100 s each cost more than the engineering.

## Not done
Slicing; the support and load second ways and a third mesh size on the final model; face measurements of bore, holes and pin in SolidWorks; any review by another model.
