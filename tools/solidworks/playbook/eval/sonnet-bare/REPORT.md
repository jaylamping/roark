# Benchmark run `sonnet-bare` (tasks T1 to T7)

Run on holly-pc, SolidWorks 2026 (Simulation add-in version string 891107), scripted from Python (pywin32), one hidden instance
per script started with `sw_instance.launch()`. Only what is on `main` was used (RULES.md, `sw_instance.py`, `conventions/cad*.md`)
plus the SolidWorks and Simulation type libraries (`sldworks.tlb`, `cosworks.tlb`, read with `pythoncom.LoadTypeLib`).
Frame: X, Y, Z in mm. Material: PETG E 1.9 GPa, nu 0.38, 1190 kg/m3, yield 45 MPa in plane and 22.5 MPa across layers; steel
E 210 GPa, nu 0.28. A custom `.sldmat` with those numbers is written by `common.py`; the study reads them back (`mat_report`).

Wall-clock from `date` stamps (23:10 first command, 00:41 last; launches that waited behind another session's solve are inside these figures):
T1 about 15 min plus a rebuild of about 5 min later, T2 13, T3 28 (Simulation API discovery included), T4 5, T5 5, T6 25, T7 and report 4. Total about 1 h 31 min.

Files: `common.py` (launch, sketch/feature helpers, STL check, results.json writer), `fea.py` (study helpers), `t1_bracket.py`
(also builds `sharp` and `c` variants), `t2_change.py`, `t3_study.py`, `t4_sharp.py`, `t5_bottomfixed.py`, `t6_model.py`,
`t6_study.py`, `t6_sweep.py`, `verify_geom.py`, row data `*_rows.json`, `results.json`. Model files are in `cad/_wip/sw-eval/sonnet-bare/`.

## Things that went wrong in my scripts and mattered for every task

* **Sketch inference moved geometry.** With the default sketch settings, the circles of the upright (bore pattern) came out
  with centres and radii changed: two of the four dia 3.4 holes were at (Y,Z) = (36, 39) and (14.04, 39) with r 1.74 instead of
  (35.96, 38.96), r 1.70. Found only when reading the cylinder faces during T3 set-up. Fix: `SketchManager.AddToDB = True`
  in every script; T1 and T2 were rebuilt, and hole centres and radii of both parts were then read back from the faces
  (`verify_geom.py`, all within 0.01 mm of the specification). The same setting also made a slot sketch (two lines, two
  arcs) cut that had not cut before. The first T1 STL, taken straight from the freshly built document, was not watertight
  (T-junctions on the X=0 face); exporting from the saved, reopened part gave watertight STLs.
* Zero-argument COM methods come back sometimes as values and sometimes as bound methods in pywin32 dynamic dispatch
  (`CreateMassProperty2`, `RunAnalysis`, `GetFaces`...). `common.g()` handles it. `study.RunAnalysis` is a property that
  runs the solve when read.
* Simulation unit arguments: `GetMinMaxDisplacement(..., unit)` takes `swsLinearUnit_e` (0 = mm, 3 = inches), stresses take
  `swsStrengthUnit_e` (3 = N/mm2). My first displacement numbers were in inches; all numbers below are from the corrected
  runs.

## T1. Bracket from specification

What I did: base 80 x 50 x 6 with R5 on the two corners at X 80 (Front plane sketch, lines and arcs), upright X 0..6, Z 0..46 with
R5 top corners (Right plane sketch), R4 fillet feature on the edge at X 6, Z 6, base holes dia 5.5 (4), bore dia 22, four dia 3.4 holes on a dia 31
circle at 45/135/225/315 degrees (Right plane sketch, cut through both ways). Saved, reopened, exported STEP and STL.

Hand volume: 36000 (base 24000 + upright above base 12000) - 4 x (1 - pi/4) x 25 x 6 x 2 (four R5 rounds, 128.76) + (1 - pi/4) x 16 x 50 (fillet, +171.68)
- 4 x pi x 2.75^2 x 6 (570.20) - pi x 11^2 x 6 (2280.80) - 4 x pi x 1.7^2 x 6 (217.90) = 32974.02 mm3.

Checks: SolidWorks volume 32976.08 mm3 (+2.06 mm3, 0.006 %); one body; bounding box from the STL [0,0,0,80,50,46];
STL 32974.90 mm3, watertight (trimesh, vertices merged), 1 piece; STEP written (117 KB, not re-read); every hole and the bore verified from the cylinder faces.
Mass 39.242 g = volume x 1190 kg/m3.

Could not verify / odd: SolidWorks' own volume after the four base holes is already 0.24 mm3 off my hand figure while the
earlier steps agree to 0.001 mm3, and I did not find why (a hole radius of 2.75 mm reads back exactly). Assigning my custom
material to the part with `SetMaterialPropertyName2` did not change SolidWorks' density (stayed 1000), so the SolidWorks
mass is not used. The STEP content was not inspected. Time about 20 min including the rebuild.

## T2. Change an existing part

Opened the saved `bracket.SLDPRT` (not rebuilt), sketched four dia 10 circles on the base top face, blind cut 3 mm; slot (two lines,
two semicircles, 20 x 6 overall, centre (45, 25)) cut through; saved as `bracket_b.SLDPRT`.

Hand: 32974.02 - 4 x pi x (5^2 - 2.75^2) x 3 (657.38) - (14 x 6 + pi x 3^2) x 6 (673.65) = 31643.00 mm3.

Checks: SolidWorks volume 31645.06 mm3 (+2.06 mm3, the same offset as T1; counterbore and slot removals match hand to 0.001 mm3);
counterbore floor read from the planar face list: Z = 3.000 mm; one body; hole and slot centres and radii verified from the faces.
Not verified: nothing beyond the above. Time about 13 min (a good part of it the slot that would not cut).

## T3. Static study with a verdict

Set-up: copy of `bracket.SLDPRT`; custom PETG; Fixed restraint on the four dia 5.5 base-hole walls; 150 N in +X as a total on the dia 22 bore
face (direction from the Right plane normal; the force object only took its value after `ForceBeginEdit/EndEdit`; without them
the reaction came out 1 N); standard mesh quality High (curvature-based mesher is this install's default); Intel direct sparse automatic solver.
I tried to split the bottom face into washer-sized rings for a more realistic bolt restraint (`InsertSplitLineProject`, three selection variants); it
never created a feature, so I used the hole walls. This is the weakest modelling choice of the run.

Hand: bending at the root of the upright, M = 150 N x (28 - 6) mm = 3300 N mm, S = 50 x 6^2 / 6 = 300 mm3, sigma = 11.0 MPa (X=0 face tension, X=6
face compression); at a dia 3.4 hole rim (Z = 17, M = 1650, nominal 5.5 MPa) times Kt about 3 for a small hole in a wide plate = 16.5 MPa.
Deflection of the top edge: upright cantilever 0.69 mm + rotation of the 25 mm base overhang (4200 N mm x 25 / EI, 0.061 rad x 46 mm) 2.8 mm = about 3.5 mm.

Checks run:
* Reaction: sum of nodal reactions -150.00 N in X (all meshes within 0.01 N).
* Material read back from the study: E 1.9e9, nu 0.38, density 1190, yield 4.5e7.
* Mesh sweep, global size 4, 3, 2.5, 2, 1.75, 1.5 mm (15,120 to 119,012 nodes) and then a local control on the four dia 3.4 hole faces down to
  0.25 mm on a 3 mm global mesh (24,222 to 117,537 nodes), where the peaks sit. Peak VM away from the bolt walls: 16.9, 16.7, 16.7, 16.2, 16.7, 17.0 (global), then 17.7, 17.5, 18.2,
  18.5, 18.6 MPa (local). Layer tension sigma_Z: 16.7, 16.0, 17.3, 16.2, 16.3, 16.0, then 16.6, 16.6, 16.4, 16.3, 16.1 MPa. Last-step change 0.4 % (VM) and 1.3 % (sigma_Z): converged.
  Table in `results.json` / `t3_bracket_rows.json`, `t3local_bracket_rows.json`.
* Nominal stress on the X=0 face at Z=8 away from holes: FE 8.4 MPa against hand 10.0 (16 % lower; shear lag from the bore-centred load and the
  base flexibility are my guess, not checked). Root fillet VM peak 14.2 to 15.4 MPa depending on the mesh (the maximum jumps between nodes along the tangent line): hand 11.0 x Kt about 1.4 = 15.4.
* Max displacement 2.743 mm against the 3.5 mm hand figure (same order; the hand figure ignores the stiffening of the bore ring and the fixed hole walls).
* Peak VM including the bolt-hole walls: 26.5, 28.1, 27.4, 28.0, 29.1, 29.3 MPa on the global meshes, but 23.2 MPa at the same 3 mm global size once a local control is added:
  mesh dependent and tied to the fixed wall, so it was excluded from the verdict (see below).

Result: peak VM 18.57 MPa at (5.9, 34.3, 17.5) mm (X=6 face at a dia 3.4 hole rim), SF_yield = 45 / 18.57 = 2.42; layer tension sigma_Z 16.13 MPa at the rim of a dia 3.4 hole
on the X=0 face, SF_layer = 22.5 / 16.13 = 1.40. **Verdict: fail** (layer requirement). With the bolt-wall value (29.3 MPa) SF_yield would be 1.5, which also fails.

Not verified: the real bolt restraint; the exclusion of the bolt-hole edge is a judgement (T5 gives a second restraint that supports it);
layer-to-layer shear; creep. Time about 28 min.

## T4. The same study on a variant

`bracket_sharp.SLDPRT` (same script, no fillet; STL volume 32803.0 mm3). Same load case. Sweep: global 3, 2, 1.5 mm, then a mesh control on the corner edge of 1.0, 0.5, 0.25, 0.12, 0.06 mm on a 3 mm
global mesh (22,170 to 128,105 nodes).
Corner von Mises (nodes within 0.2 mm of the corner line, Y 5..45): 9.4, 13.3, 13.7 (global), then 16.7, 26.8, 39.9, 59.1, 78.8 MPa. It keeps growing by about x1.3 per halving of the
element (about r^-0.4, close to the r^-0.455 of a 270-degree re-entrant corner): a singularity, **not converged**. The layer-tension peak at the dia 3.4 holes stays at 16.6 to 17.0 MPa (as T3); at the finest corner mesh a singular sigma_Z of 20 MPa appears in the base top face next to the corner.
Reported stress: no FE value; judged from 11.0 MPa nominal x Kt about 2.4 (recalled Peterson shoulder-fillet value for r/d = 0.4/6, not looked up) = 26.4 MPa, SF_yield about 1.7. Reaction 150.0 N on all meshes.
**Verdict: fail** (corner estimate SF 1.7, and the unchanged hole-rim layer tension SF 1.3). Not verified: the real printed corner radius; Kt value. Time about 5 min.

## T5. Make it pass

Why T3 fails: across-layer tension sigma_Z at the dia 3.4 holes (stack along Z). I ran the same study with the stack along each axis (the stress is the same; only the component that is "across the layers" changes): stack Z gives sigma_Z 16.0 MPa (SF 1.4); stack X gives sigma_X 13.6 MPa (SF 1.65); stack Y gives sigma_Y 7.4 to 7.6 MPa (SF 3.0).
Change: print on its side (Y=0 face on the bed, layers stacked along Y) and inside fillet R4 -> R6 (`bracket_c.SLDPRT`; STL volume 33189.6 mm3 and SolidWorks volume 33190.69 mm3 against 32976.08, mass 39.497 g, +0.65 %). Hole positions, bore and footprint unchanged (hole faces checked, bounding box 80 x 50 x 46).
Study of `bracket_c` as T3, global 4, 3, 2, 1.5 mm and local 1.0 to 0.25 mm (up to 118,968 nodes): peak VM away from the bolt walls 16.7 to 18.6 MPa (finest 18.60), sigma_Y tension 7.1 to 7.64 MPa (largest over the last three local meshes 7.64; finest 7.38), reaction 150.0 N.
SF_yield = 45 / 18.60 = 2.42, SF_layer = 22.5 / 7.64 = 2.95. The fillet raise is a minor change (the root is not the critical place); the orientation is what makes it pass.
Second restraint (whole bottom face fixed, 88,967 nodes at the finest): no bolt-wall peak at all; VM 17.3 MPa (SF 2.6), sigma_Y 6.63 MPa (SF 3.4), sigma_Z 17.1 (in plane now).
**Verdict: pass.** Not verified: layer-to-layer shear and anisotropic yield beyond the two numbers given; the dia 22 bore printed on its side needs a teardrop or support; bolt preload; the pass still depends on excluding the bolt-hole wall edge in the main restraint (the second restraint is the only support for that).
Time about 5 min.

## T6. Contact between two bodies

Model: multibody part, PETG block with dia 10.2 hole along Y, steel dia 10 x 50 pin as a second body, 0.1 mm radial clearance. Block bottom face Fixed; two forces of 250 N in +Z on the pin end faces (500 N);
a frictionless No Penetration contact set between the pin cylinder and the hole wall; Intel direct sparse; soft springs on.
Hand: nominal bearing stress 500 / (10 x 30) = 1.67 MPa projected. Peak by line-contact (Hertz) theory for the 0.1 mm clearance: R_eff = 5 x 5.1 / 0.1 = 255 mm, E* = 2.2 GPa, w = 16.7 N/mm: a = 1.57 mm, p0 = 6.76 MPa.
Peak contact pressure is read through a stress plot (`CreatePlot(2, 13, ...)`, contact-pressure component) because the nodal stress getters refuse component 13.

Results (more in `t6_*_rows.json` and `results.json`): surface-to-surface contact, peak pressure 9.1 / 7.6 / 6.3 / 6.6 MPa at 5,674 / 26,020 / 62,261 / 106,193 nodes (finest 6.55 MPa at (-1.2, 10.6, 14.95) mm); reaction 500.0 N; normal contact force on the hole wall 500.08 N; pin rise at mid-length 0.127 mm;
peak VM on the hole wall 4.9 MPa; peak VM in the block 5.6 MPa at (-2.3, 15.0, 15.5), the hole entry edge on a Y face (it rises slowly, about 2 % per refinement); pin VM about 44 MPa.
Node-to-surface contact on the same meshes gave 8.2 / 10.1 / 13.2 / 13.3 MPa and a normal force of 495 N: it disagrees with surface-to-surface by a factor 2 and the hand figure sides with surface-to-surface, so I report 6.55 MPa and state the disagreement.
Stabiliser: the 12,752-node solve without any stabiliser gave the same pressure (11.56 vs 11.55 MPa) and rise (0.135 mm) as with soft springs; the pin's axial position is arbitrary (max displacement 70 mm without springs).
`valid = true` with those caveats. Not verified: friction (set to zero), print tolerance of the hole, pressure at the entry edge, whether the mesh near the Y faces is fine enough for the block VM. Time about 25 min (limit 40).

## T7. Diagnose

**a. `--status` shows PID 20948 `busy` (age 2.2 h, 61 threads, 9 GB) and PID 2536 `HALF-CLOSED` (no windows, one thread, 3.6 GB).**
What is happening: 20948 is another session's instance in a long solve (an instance does not answer while it solves, that is not a hang). 2536 is a half-closed leftover (ExitApp or a killed client); it stalls every launch at the splash screen.
Next: do not launch; find the owner with `python tools/pc/claims.py who 2536`, tell them and Joey, and give Joey the exact line `taskkill /PID 2536 /T /F` (/T takes the solver with it); wait for 20948 to finish.
Must not: launch anyway or wrap the launch in `timeout`; kill either PID myself (threads cannot stop another session's process, and 20948 is solving); ExitApp, `GetActiveObject` or `Dispatch("SldWorks.Application")`.

**b. 796,000 nodes, direct sparse, error 24 after 143 s, log ends at GLOBAL-STIFFNESS-MATRIX-DECOMPOSITION-Start, free memory 26 GB -> 12 GB in 11 s.**
What is happening: error 24 is `swsRunAnalysisErrorAnalysisFailed`; the direct sparse factorisation ran out of memory (the matrix of 796k nodes with contact, about 2.4 M equations plus fill-in, needs more than the free RAM); not a model error.
Next: stop, check `--status` for a half-closed instance and free RAM, shrink the model: under 150,000 nodes with local mesh controls on the contact zone and coarse elsewhere, use symmetry, drop unneeded parts or refine only where the result is read; run one large solve at a time; re-check memory before the next run.
Must not: rerun the same mesh hoping for another outcome; run it next to another solve; read the partial output; treat it as a hang and kill things; lower the accuracy settings silently.

**c. STL fit check says the whole part is offset by (41.5, 0, 12.0) mm; native part right; export made on a machine set up last week.**
What is happening: the fresh holly-pc SolidWorks has "do not translate STL output to positive space" off (toggle 71, cad.md section 9), so the STL is shifted by the part's negative extents.
Next: set toggle 71 on in the export script (and 69 binary, units mm, quality, STEP AP) on my own instance, re-export, re-run the fit check, log the settings; check the old STL's minimum corner to confirm it equals the shift.
Must not: subtract the offset in the fit check (it would hide a wrong export), edit the native part, change Joey's SolidWorks options by hand or in the registry.

**d. VM peak 61 MPa on the edge of a fixed face; 38, 47, 61 MPa at element sizes 2.0, 1.5, 1.0 mm; requirement SF 2 against 45 MPa (22.5 MPa).**
What is happening: the value keeps rising as the mesh is refined (+24 %, +30 %): a singularity at the edge of the fixed face (stress concentration of an idealised restraint), not a converged stress; none of the three numbers is the stress of the part.
Next: judge the part away from the restraint edge and where the real load path concentrates stress, converge that quantity, compare it with a hand calculation, and make the restraint more realistic if the edge is a real load path (spread it over a washer area, model the support's compliance); report the edge value as an artefact with the three readings.
Must not: report 61 or an extrapolated number as the stress, say "SF 0.7, fail" or "SF 1.2, fail" from it, or pick the coarse 38 MPa as if it had converged; likewise not declare the part safe by ignoring the edge without showing it is an artefact.

**e. Script silent 25 min, `--status` shows my instance `busy`; another thread asks if SolidWorks is hung and suggests restarting.**
What is happening: `busy` means the instance does not answer because it is inside a solve (or reading a large result back): not hung. A truly dead instance shows `HALF-CLOSED` (no windows, one thread).
Next: answer "not hung, solving"; wait; check `--status`, solver processes (`star.exe` CPU time) and free memory; keep the claim fresh with `claims.py beat`; give the other thread the expected end; if it shows HALF-CLOSED or the budget is exceeded, report it and end my own instance with `end_session`.
Must not: restart or kill it or the Python client (a solve 28 min in was once killed this way, leaving `cwanalysisproc`/`star` running and losing the result), start a second solve alongside, wrap the script in `timeout`.
