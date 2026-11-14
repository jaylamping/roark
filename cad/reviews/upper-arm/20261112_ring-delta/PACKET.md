# Upper arm R1g6 (ring + printed shim + yaw torque through extended lugs): delta review packet (2026-11-12/13)

Branch `left-arm-organic-r1`.

Pinned commit: 0fb42a291b050475ad3cc12c5ff6eb53676507ca (r1g6 after review 3; hub D3c7 released at 355aa9b; no-instrument bench). Nothing here is
released.

**Review 3 (head 131cd60) verdict: the coupon, the hub, the shim rings and the yaw lever only.**
- The halves wait for the hub release, the hub-root reconciliation, the coupon insert result and a corrected bench 2b that passes.
- Findings and responses: `../20261111_r1c-delta/r1d/r1g/REVIEW_R1G6_FINDINGS.md`.

**Scope: the change from R1c to R1d "ring".** R1 was reviewed in `../20261111_print-release/` and R1c in
`../20261111_r1c-delta/`. Review:
- the ring ridge and the crush ribs;
- the single axial datum;
- the slot edge break for the hub's new lug-root fillets;
- the FEA route and its post-processing fixes;
- the honest low spots listed below.
No SolidWorks is needed: the scripts, result JSONs, post-processing outputs and notes are all in git. Working notes, with
every intermediate step, are in `../20261111_r1c-delta/r1d/R1D_NOTES.md`.

Frame: the hub axis is Y; r is measured from that axis (X 170.49, Z 5.986); θ runs from +X toward +Z. The front half is
Z > 5.986.

## R1g6: yaw torque through the hub's extended lugs, final hole layout (2026-11-13)

**Why.** The full-ring groove and ridge carry no torque about the hub (yaw) axis. Nearly all of the RS02's yaw torque (17 N·m
peak, routine) therefore passes through the two lugs as a Z couple. On rev D:
- YAW_17 failed: our loaded post about 0.95-0.99 at 0.5 mm, hub lug roots 0.92-0.99, insert 1.27.
- There was about ±0.22° (±1.1 mm at the wrist) of free yaw play in the 0.1 lug slots.

**What r1g6 changes from r1g4.** Only the hole layout:
- The hub's lug holes are Dia 3.8 (the shoulder thread's D3c7; Dia 3.4 before).
- The plate holes are Dia 3.4, inside the hub's hole. In r1g5 the plate and hub holes were both Dia 3.8, and the lumped plate's
  step sat edge on edge with the hub's hole rim. r1g6 puts the plate step inside the hub hole, over the brass insert's rim.

**Design.**
- **Hub (shoulder thread).** The lugs grow out to one straight outer face at X offset 34.4, over Y 288-296, with the R1.2 Z roots
  and an R0.8 outward root.
  - The hub is **D3c7**: D3c6 plus the Dia 3.8 lug holes and the cable window at 68 deg.
    - Pushed by the shoulder thread in commit 96f74abc669b20ee1ed6831b4f1c47b818df69d2 (branch `claude/project-thread-90ef87`),
      as `cad/exports/shoulder/shoulder_hub_left_revD3c7_candidate.STL`.
    - The real LFS object hashes to SHA-256 a73103adb49bb9a4fe3b3901fea852e6668e928e7e1586953bc8b25a0c10259b (3,136,484 bytes),
      the same file the checks were run on.
  - All checks PASS, on the R1h halves (`../20261111_r1c-delta/r1d/r1g/D3C7_CHECK.md`). Final for the pushed file.
  - **Released for the stage 1 print:** adopted at commit 355aa9b3c1ffd0e5c1fa4ebe013ef0fa41353b85 as
    `cad/exports/shoulder/shoulder_hub_left.STL`, the same SHA-256.
    - Its print file `shoulder_hub_left_revD3c7.3mf` (2 h 47 min, 81.9 g) holds the same mesh.
    - The 3MF is on the PCs, not in the repo.
  - The D3c4 and D3b checks are in `D3C4_CHECK.md` and `D3B_CHECK.md` alongside it.
- **Our side (unchanged since R1g).**
  - A shallow seam pocket at X offset 34.6 for the whole lug height.
  - Post-to-wall webs.
  - The lug slot at 0.5 per side.
  - A root relief for the R1.2 out to X offset 35.2.
  - The ridge stays whole, with 1.7 or more of wall to the skin.
- **Harness tie bridge (R1h, back half only).** A bar 2.0 thick on the -X inner wall at the neck (Y 255-261), standing on the seam
  face, with a 1.7 × 3.0 slot for a 2.5 × 1.0 cable tie.
  - Its edges are rounded R0.5 against chafing: the bar's corners and lower edges. Its post-to-wall corners are not rounded.
  - It adds 0.09 g and needs no support.
  - **It is in no FEA.** Without it, the wall where it stands reads SF 2.77 or more in every r1g6 case (STOP_124 shear 2.77 / 2.77 /
    2.96; STOP_0 3.43; `r1h_tie_wall_probe.txt`, a coarse 4 mm mesh there).
  - The geometry stays as built. The unrounded post-to-wall corners are on the whole-arm test's inspection list
    (BENCH_TESTS 5).
  - Checks: `../20261111_r1c-delta/r1d/r1g/R1H_BACK.md`.
  - The front half and the ring are unchanged from R1g.
- **Lug plates (final).** Flat printed PETG plates, one on each lug Z face, for zero yaw play.
  - **Outline:** the main flat face, X offset 18.96-34.2 × Y 288.2-294.6. The top is 0.2 below the line where the hub's R1.2
    fillet leaves the lug face.
  - **Hole:** Dia 3.4, smaller than the insert's Dia 4.0 hole and the hub's Dia 3.8. The plate sits on the insert's rim and holds
    it captive (insert, plate, lug, plate, back post, bolt head). The strip above the hole is 0.9, 2 whole perimeters
    (`plate_ligament_check.txt`).
  - **Lip:** short, X offset 19.5-32.5, hooked under the lug's free end.
  - **Sizes and pick:** 0.25-0.75 in 0.05 steps. Each print plate carries four of each thickness, two full sets. The pick is made
    after the ring (BENCH_TESTS 2b).
  - **Print:** plate A 19 min / 1.75 g, plate B 19 min / 1.47 g (`r1h_d34_lug_plate_set_sheet.png`, with the thickness scan).
- **Lug bolts.** Capped at 0.3 N·m until the coupon's insert check (BENCH_TESTS 2b step 14). The insert's outer diameter and
  pull-out rating have no source in the repo; only "Ruthex M3 × 5.7" in a Dia 4.0 hole is recorded
  (`cad/prints/upper-arm/SETTINGS_CHECKLIST.md`). The seam screws stay at 0.5 N·m.
- **Print orientation.** The halves print seam face down, so their layers lie in Z planes: the arm layer allowable (22.5) is on σz,
  and the interlayer shear (13) is on τxz / τyz.

**Checks.**
- **Halves:** the mesh gate PASSes. Back (R1h) 5 h 28 / 124.3 g, front (R1g) 4 h 49 / 108.2 g.
- **Closing path:**
  - On D3c7 plus the 0.70 ring: final overlap max 0.041 / 0.039, along the line-to-line ridge flank only.
  - Against the final plates with their lips: no hits (`close_path_d3c7.*`, `close_path_plates_final.*`).
- **Plate top against the hub's R1.2 fillet:** 0.267 on every lug and face (`d3c7_plate_fillet_gap.txt`).
- **Tie bridge against the front half:** as the halves close, the front's lowest material over the bar stays 5.4 mm or more
  above it. The harness route from the 68 deg window is unchanged (`r1h_tie_check.txt`).

**FEA model (r1g6).**
- **Mesh:** global 4.0, 0.8 on the lug bearing faces, 1.0 on posts / lugs / fins; 390-398 k nodes per case, every case checked by
  the mesh guard.
- **Plates:** lumped as a 0.5 boss of our part inside the plate outline, with the Dia 3.4 hole and top Y 294.6, and frictionless
  no-penetration to the lug. The shim is lumped into the end face.
- **Hub:** the D3b-shaped FEA hub with Dia 3.8 lug holes (`HUB_D3S38`), on its coarser mesh.
- **Bolts:** in the model, with a no-penetration contact set between the hub's lug faces (hole wall included) and every bolt
  face. No preload.
- **Mesh and convergence, said plainly:** at the 0.8 face size, a 0.5 mm sphere holds 4-9 nodes, so the 0.5 mm values are
  near-nodal and are read only at contact and model edges.
- **Convergence run** (`r1g6_convergence_g90y.txt`): G90 + YAW +17 again with local refinement 0.5 at the plate outline corners,
  the bolt boxes and the end-face corner box. 489,186 nodes, against 390,748 for the base run.
  - **Hub lug root: shear converged, vm not.**
    - Shear 1.00 / 1.36 / 2.12 becomes 1.03 / 1.30 / 2.06, and layer 1.24 rises to 1.43.
    - But vm 1.84 drops to 1.48 (the refinement boxes reach the root's outer corner), so the root's vm is still moving at the
      first radius.
    - Corrected after review 3: an earlier version called the root converged.
  - **Lumped-plate outline corner: not converged, and it gets worse with refinement**, as a re-entrant step corner does: shear
    0.94 / 1.49 / 2.64 becomes 0.56 / 1.06 / 2.43, vm 0.72 becomes 0.61.
    - Tensor probe at the corner edge itself: shear SF 1.44 becomes **0.96**.
    - 0.5 mm into the post: 2.09 becomes **1.39**.
    - At 1.0 mm in: 1.87 becomes 2.07.
    - So the corner value depends on the mesh, and only the 2 mm average (2.43-2.64) is stable. It stays a known item, for the
      bench imprint inspection.
  - **Arm end-face corner (θ 296):** vm 4.45 becomes 5.39. The refined mesh supports the r1g6 reading, not r1g4's 1.14 (see
    known item 3).
  - **Everything else in our part moves by under 0.3 at 0.5 mm**, or improves: the PETG ring by the insert vm 4.16 becomes 8.75,
    the hub lug face at the plate-hole edge 3.50 becomes 6.45.
  - **Whole-part rows:** the arm's worst is the plate corner in both runs. The hub's worst is the lug root.
  - **Body split:** the refined run first had one hub node (279355, at the lug's outward root) classed as arm. Review 3 found it.
    - The fix: hub_r1c.py moves a run of 3 nodes or fewer to the body on both sides of it in node order when 80 % of its 0.6 mm
      neighbours are of that body.
    - After the fix, every r1g6 result passes the per-body node-count check (`r1g6_body_check.txt`).
    - Re-post-processing changed nothing but one 2 mm value (4.05 to 4.00), so "worse when refined" stands.
  - The refined run's whole-part post-processing needed a 9 GB Python cap (the machine was idle) instead of 6 GB.
- **Averaging:** sphere averages at 0.5 / 1 / 2 mm, with every node a candidate centre. vm is reported apart from the signed
  components (layer = signed across-layer tension, shear = interlayer magnitude).
- **Reports per case** (in `../20261111_r1c-delta/r1d/r1g/`):
  - `r1g6_<case>.spot_report.txt`: named spots, including the PETG ring just outside the insert, with the brass apart;
  - `.region_report.txt`: per post, fin, hub lug, insert and bolt;
  - `.fx_path.txt`: shank gaps, the deformed hole rim, the lug outer face against our pocket wall, and plate slip;
  - `.post_allc.txt`: whole-part rows.
- **Lug loads:** `r1g6_lug_loads.txt`, every case.
  - Which totals to trust, an uncertainty per case, and how the plate force spreads over the lug face: see
    `r1g6_lug_loads_uncertainty.md`.
  - Use the section totals, ±8-18 % against the face totals; for design, the larger face total, at most 299 N per lug.
  - About half the plate force lies within 1 mm of the plate outline.

**Results (r1g6)**, SF at 0.5 / 1 / 2 mm; targets: 1.5 for yaw and G90, 1.2 for the stops:

| Case | Posts / webs / fins (lowest) | Arm end-face corner band | PETG ring by the insert (r 2-3) | Hub lugs and groove (lowest; the shoulder FE governs) | Model edge: lumped-plate outline corner | Whole part, nothing excluded (where the 1 and 2 mm worst sit) | Inserts / bolts (SF) | Below target |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STOP_0 | hub-end wall shear 2.69 / 3.81 / 4.85; -X fin shear 3.41 / 3.71 / 4.12 | vm 4.09 / 4.34 / 4.60 | shear 6.06 / 7.80 / 12.26 | -X lug outer front edge vm 0.74 / 1.26 / 2.80 (X offset 34.4, Y 293.4, at the lumped boss's step edge: the shoulder FE reads about 8 there and governs); -X lug shear 1.16 / 1.76 / 2.89; lug roots vm 0.98 / 1.46 / 3.16, shear 1.16 / 1.76 / 3.06; groove bottom shear 1.30 / 1.60 / 2.17, layer 1.31 / 1.66 / 2.28; whole hub shear 1.16 / 1.60 / 2.17 | shear 0.47 / 1.27 / 3.17, vm 0.65 / 1.51 / 3.44, layer 1.00 / 3.58 / 4.80; outline skin layer 1.00 / 2.45 / 4.26 | whole arm shear 0.47 / 1.02 / 1.17 (the first radius at the plate corner; 1 and 2 mm at the loaded stop-lug pad, Y 228), vm 0.65 / 1.51 / 1.88 (the same places), layer 1.00 / 1.29 / 1.49 (the plate corner; 1 and 2 mm in the neck, Y 250, X 165.7, Z 14.3) | 11.45 / 33.03 | hub edge and roots, plate corner at the first radius; whole arm at the stop pad at 1 and 2 mm (the R1 precedent: a load-introduction patch, excluded in R1) |
| STOP_124 | hub-end wall shear 2.35 / 3.43 / 3.82; +X fin layer 2.75 / 3.91 / 6.45 | vm 3.49 / 4.84 / 5.48 | shear 3.40 / 4.74 / 7.61 | groove bottom layer 1.44 / 1.79 / 2.51; lug face at the plate-hole edge shear 2.10 / 4.24 / 9.75; lug roots shear 2.42 / 3.25 / 5.37 | vm 1.52 / 2.81 / 4.89 | whole arm shear 0.82 / 0.98 / 1.17 (all three radii at the loaded stop-lug pad, Y 192; R1 listed the same patch) | 6.85 / 11.43 | whole arm at the stop pad, all three radii (the R1 precedent: a load-introduction patch) |
| YAW -17 | +X back post shear 2.93 / 3.95 / 5.19; -X front post shear 3.21 / 3.87 / 5.40 | vm 3.99 / 5.93 / 6.77 | shear 3.21 / 3.99 / 6.46 | lug roots shear 1.17 / 1.53 / 2.40, layer 1.49 / 2.48 / 4.22; -X lug shear 1.26 / 1.67 / 2.58, layer 1.49 / 2.64 / 4.74; 2 mm land layer 1.49 / 2.48 / 5.09 | vm 0.88 / 1.65 / 3.08, shear 1.05 / 1.74 / 3.52 | whole arm and whole hub are the plate corner and the lug roots | 7.21 / 11.60 | hub roots, land and plate corner at the first radius |
| YAW +17 | -X back post shear 3.12 / 4.21 / 5.10; +X front post shear 3.12 / 3.94 / 5.47 | vm 4.07 / 6.04 / 6.95 | shear 3.33 / 4.07 / 6.59 | lug roots shear 1.14 / 1.54 / 2.38, layer 1.41 / 2.41 / 4.33; +X lug shear 1.28 / 1.64 / 2.59, layer 1.49 / 2.64 / 4.31; -X lug layer 1.41 / 2.41 / 4.28; 2 mm land layer 1.41 / 2.41 / 4.96; whole hub layer 1.41 / 2.41 / 4.26 | vm 0.83 / 1.59 / 2.93, shear 1.06 / 1.70 / 3.09 | whole arm is the plate corner | 7.44 / 12.76 | hub roots, land and plate corner at the first radius |
| G90 | hub-end wall shear 3.28 / 5.23 / 6.58; +X fin layer 3.39 / 5.09 / 10.21 | vm 8.36 / 8.76 / 9.22 | shear 18.54 / 24.95 / 41.45 | groove bottom layer 2.25 / 2.81 / 3.96; lug roots shear 6.29 / 8.17 / 10.95 | layer 3.52 / 5.58 / 11.98 | whole arm layer 2.47 / 3.49 / 4.96 | 35.17 / 62.46 | none |
| G90 + YAW -17 | +X back post shear 2.38 / 3.21 / 4.68; +X fin layer 2.41 / 3.83 / 8.33 | vm 3.36 / 4.79 / 5.29 | vm 2.52 / 4.19 / 9.22 | lug roots shear 1.00 / 1.31 / 2.09, layer 1.42 / 2.19 / 3.97; -X lug shear 1.41 / 1.83 / 2.70, layer 1.49 / 2.50 / 4.51; +X lug layer 1.42 / 2.19 / 3.98; 2 mm land layer 1.42 / 2.19 / 4.54; whole hub layer 1.42 / 2.19 / 3.28; groove bottom shear 1.75 / 2.10 / 2.68 | vm 0.73 / 1.38 / 2.55, shear 0.98 / 1.49 / 2.91 | whole arm is the plate corner | 9.57 / 14.94 | hub root at the first radius and 1 mm; land at the first radius; plate corner at the first radius and 1 mm |
| G90 + YAW +17 | -X fin layer 2.57 / 3.99 / 7.13; -X back post shear 2.71 / 3.69 / 4.26 | layer 3.71 / 3.87 / 4.03 | vm 4.16 / 7.25 / 12.04 | lug roots shear 1.00 / 1.36 / 2.12, layer 1.24 / 2.14 / 4.01; -X lug layer 1.24 / 2.14 / 3.98; 2 mm land layer 1.24 / 2.14 / 4.42; whole hub layer 1.24 / 2.14 / 3.52; groove bottom shear 1.86 / 2.24 / 3.03 | vm 0.72 / 1.36 / 2.50, shear 0.94 / 1.49 / 2.64 | whole arm shear 0.94 / 1.49 / 2.49 (the plate corner) | 10.99 / 13.06 | hub root at the first radius and 1 mm; land at the first radius; plate corner at the first radius and 1 mm |

`packet_numbers_check.py` checks every number in this table against that case's own reports. It also checks that every region
below target is listed.

**Our part passes everywhere off the model edge.** Posts, webs, fins, the end-face band, the PETG ring by the insert and the brass
read 1.89 or more at 0.5 mm in every case (the lowest: our post at the boss hole edge, G90 + YAW -17 vm; then 2.35, the hub-end
wall in STOP_124). The inserts read 6.85 or more and the bolts 11.4 or more.
- **Whole-arm rows** (`r1g6_<case>.post_allc.txt`, nothing excluded), now in the table's whole-part column. Where the 1 and 2 mm
  worst centres sit is in `r1g6_stop0.worst_centres.txt` and `r1g6_stop124.worst_centres.txt`.
  - The lowest are the plate outline corner and, in the stops, the loaded elbow stop-lug pad.
    - STOP_0 at Y 228: shear 1.02 / 1.17 at 1 and 2 mm.
    - STOP_124 at Y 192: 0.82 / 0.98 / 1.17.
  - The pads are the load-introduction patches, where the 515 N goes on as a pressure. R1 excluded them, and they are listed
    here as below target, not as passes.
  - STOP_0's whole-arm layer at 1 and 2 mm (1.29 / 1.49) is in the neck at Y 250 (X 165.7, Z 14.3). STOP_124's next lowest is
    layer 1.32 at the neck, Y 242. Both are above the 1.2 stop target.

**Where the lug lands** (`r1g6_<case>.fx_path.txt`, surface nodes). The M3 shank sits in the Dia 3.8 lug hole with 0.40 radial
clearance (the mesh reads 0.36-0.40).
- **The bolt is free in every case.** The bolt-hole walls carry about 0 N. Smallest shank gap left:
  - STOP_0 0.102 (-X); STOP_124 0.176 (+X).
  - YAW -17 0.243; YAW +17 0.252.
  - G90 0.242.
  - G90 + YAW -17 0.179; G90 + YAW +17 0.185.
- **The lug outer face against our pocket wall** (0.20 gap):
  - It lands only in STOP_0: about 9 N inward on the -X lug (centre Y 293.2, Z - CZ +3.7).
  - The lug's net 26 N outward goes, in the model, through the lumped boss's step edge, which is a model artefact. In the real
    joint it goes through plate friction or to the bolt (`r1g6_lug_loads.txt`, `r1g6_stop0.lug_sideways_split.txt`).
  - In every other case the gap stays open, closing by at most 0.10.
- **The deformed hub hole rim** (nominal r 1.9), against the plate edge (r 1.7) and the insert rim (r 2.0), is given per lug face
  in each fx_path file.
  - It dips inside the plate edge in four cases, on the loaded lug: STOP_0 -X to r 1.600; STOP_124 +X to 1.625; G90 + YAW -17 -X
    to 1.681; G90 + YAW +17 +X to 1.654. Otherwise it stays over the plate (r 1.708 or more).
  - It goes past the insert rim (up to r 2.203) in places on the loaded faces, in every case.
  - So in the frictionless, unclamped model the hub's lug hole rim rides up to 0.10 over the plate's hole edge (Dia 3.4 kept) in
    those four cases. The PETG ring by the insert still reads 2.52 or more and the hub lug face at the plate-hole edge 2.10 or
    more at 0.5 mm in every case. The bench imprint inspection (BENCH_TESTS 2b step 12) covers the plate's hole edge.
- **The real joint is clamped** (0.3 N·m, about 0.33-0.5 kN). Its friction (about 200-300 N) holds far more than these side loads.
  It is not counted on.

**Remaining below target. These are known items, not passes.**
1. **The hub lug root at the extended lug's outer face** (X offset 34.4, Y 294.9).
   - Readings: YAW ±17 shear 1.14-1.17; G90 + YAW ±17 1.00; STOP_0 vm 0.98 and shear 1.16 on the -X outer root.
   - This is the hub, and the shoulder thread's FE governs it. Our FEA hub is the D3b shape on a coarser mesh.
   - **The shoulder thread's re-solve (D3c7, 1.0 M nodes, their `A_HUB_LUGS.md` at b399e84), at our centres of pressure:**
     - At our section totals (governing lug 270.9 / 272.2 N): shear 1.58 / 1.59. That passes 1.5.
     - At the larger of the section and face totals (299 / 294 N), at the outer R1.2 root (X offset 32.6-33.0, Y 295.6):
       - G90 + YAW -17: shear 1.42, layer 1.57;
       - G90 + YAW +17: shear 1.44, layer 1.58.
     - **The design load is the section totals.** Both figures are stated here.
     - It clears the 1.2 bound either way. No hub change.
     - Accepted for the test print because the bench ends with the 1.5 × yaw proof (25.5 N·m) on the printed hub, which loads that
       root in the real material. After the proof, the hub lug roots are inspected and photographed.
   - **STOP_0, -X lug outer front edge** (X offset 34.4, Y 293.4, Z 11.0): vm 0.74 / 1.26 / 2.80.
     - The shoulder thread's fine hub reads about 8 there (von Mises 7.98 peak, 8.71 at 0.5 mm, friction variant; 8.13 / 8.89 with
       the bolt-wall variant; their `A_HUB_LUGS.md` at b5679c6). **Their number governs.**
     - Ours is the lumped plate boss's step edge (`r1g6_stop0_hub_edge_probe.txt`, findings item 6). The arm's boss carries
       16-23 MPa on its last 0.5 mm before its edge at X offset 34.2.
     - The hub face nodes at X offset 34.3-34.45, beyond the boss, still read 12.9 MPa mean: values extrapolated from that edge,
       with no arm face opposite.
     - The tensor average there is p1 +51.5, p3 -16.9 MPa, edge bending at the corner of the lug's front and outer faces.
     - It is gone within 1 mm. 0.5 / 1.0 mm into the lug, vm reads SF 1.47 / 3.11; 0.5 / 1.0 mm inward, inside the boss outline,
       1.38 / 2.37.
   - The lug loads for their FE are in `r1g6_lug_loads.txt`. Per lug, from the section:
     - YAW -17: +247 / -242 N.
     - YAW +17: -243 / +247 N.
     - G90 + YAW +17: -272 / +220 N.
     - STOP_0: -X 179 N.
   - The lugs carry 89-90 % of the yaw moment and almost none of the G90 moment, which goes through the ring, ridge, groove and
     spigot.
2. **The lumped-plate outline corner on our post** (X offset 34.2, Y 294.6).
   - Readings: STOP_0 shear 0.47 / 1.27 / 3.17; yaw and G90 + yaw vm 0.72-0.88 and shear 0.94-1.06 at 0.5 mm.
   - It is the corner of the 0.5 boss that stands in for the separate plate. A real plate on a flat post face has no step there.
   - Tensor averages over the same arm nodes (`r1g6_plate_corner_probe.txt`):
     - STOP_0: shear 0.48 at the edge itself (3 nodes), 1.31 at 0.5 mm into the post, 2.84 at 1.0 mm. Layer 2.72 / 1.20 / 1.60.
     - Yaw and G90 + yaw: shear 1.44-1.61 at the edge and 1.76-2.47 at 0.5 mm in.
   - The convergence run shows the value at the corner itself is mesh-dependent (shear 0.94 at 0.5 mm becomes 0.56 when refined;
     1.0 mm in, 1.87 becomes 2.07).
   - Bench: the imprint inspection (BENCH_TESTS 2b step 12) covers the plate's outer corner and the hub lug's outer front edge
     as well as the hole edges.
3. **The arm end-face corner (r1g4's third item): the r1g4 low was a contact-pressure spike at single inner-edge nodes, and it did
   not move elsewhere** (`r1g4_r1g6_g90y_endface_compare.txt`, G90 + YAW +17, post-processing only).
   - **Same place, same mesh there:** the r1g4 spot (θ 296, X 186.7, Y 302.0, Z -26.6) has a node at the same position in both
     meshes (0.011 mm from the point). 0.5 mm average there: r1g4 vm 1.14, shear 0.76; r1g6 vm 4.50, shear 6.08.
   - **Same load path:** the end-face contact force by 30 deg sector agrees within about 10 % (270-300 deg: 240 / 253 N on the arm
     face; 300-330: 189 / 226 N). The arm-to-hub displacement at the spot agrees within 0.03 mm, and the face tilts match within
     3 % (arm face plane fit: -94 / -96 and -104 / -108 mdeg). The freed bolt did not shift or tilt the arm on the disc.
   - **What differs is the nodal pressure peak at the face's inner edge (r 36.40):** r1g4 put 57.7 MPa at one node in 270-300
     deg (mean 4.7), 40.0 in 300-330 and 29.7 in 120-150; r1g6 puts 17.1, 17.4 and 6.4 there (means 4.9, 4.4, 1.3). The hub
     side shows the same (26.2 against 9.1 MPa).
   - **The peak did not move:** searching every node of the end-face corner band and the ridge flank as a 0.5 mm centre, r1g6's
     worst in the band is the same node at vm SF 4.45 (then θ 307 at 4.51; shear 4.53 at θ 314), and on the ridge flank vm 3.60
     at θ 171. Nothing lower appears elsewhere, so the table has no new entry for it.
   - **Cause, as far as it is established:** a local contact solution at the sharp inner edge, where the frictionless contact
     concentrated pressure on single nodes in r1g4 and not in r1g6. The load path is the same in both. Why the contact iteration
     settled differently is not established beyond that: r1g6 changes only the lug holes, which changes the contact iteration path.
     The convergence run refines this corner and reads vm 4.45 / 6.04 / 6.58 becoming 5.39 / 6.54 / 7.11, so the mesh supports the r1g6
     reading.

**Bench (BENCH_TESTS 2b), on the final hub only.** Rewritten after review 3: D3c7, Dia 3.4 plates, r1g6 loads, readings on the
coupon, not the lever.
- Joey's step-by-step sheet is `cad/upper-arm/STAGE1_PRINT_AND_BENCH.md`.
- **Default method: no special instruments.**
  - Torque comes from a weight hung on the 2.5 mm hex key: grams = 102 000 × N·m ÷ the measured hang distance in mm. About ±10 %.
  - Movement is read with a 300 mm steel pointer glued to the coupon's skin below the lever. Its tip is read with photos against
    a fixed ruler, to about 0.1 mm at R 300, which is 0.013 at r 40.
  - The pointer's glue joint is checked by a push-and-return test, done before the loads and again before the proof.
- **Alternative:** a torque screwdriver and a 0.01 dial indicator at r 40.
- The pass numbers are given below at r 40 (dial), with the pointer's at R 300 in brackets (× 7.5).

1. A bare fit; callipers on every ring and plate.
2. Hole gauges: every plate hole takes a Dia 3.4 drill shank and not a 3.8; each hub lug hole takes a 3.8.
3. Three inserts measured and pressed flush to 0.05; the scrap-block insert torque check (0.3 / 0.5 / 0.7 N·m). The coupon's own
   inserts get only 0.3 N·m until after the loads.
4. The ring pick, then the plate pick, with a blue check of the plate top against the hub fillet; lug bolts at 0.3 N·m.
5. The rock check.
6. **Play reversal, bolts loosened:** ±1 kg at the hook (±0.39 N·m). Pass: total travel at most 0.04 (0.30).
   - A pick one plate step loose (0.05 at X offset about 30.5) turns the coupon 1.6 mrad, which is 0.066 at r 40.
   - The ±0.39 N·m itself adds 0.010 elastically.
   - So a one-step-loose joint reads about 0.076 (0.57) and fails; a tight one reads 0.01-0.02 (0.1-0.15).
7. Yaw 8.7 kg at 200 mm (17 N·m), each way, read on the coupon. The FEA gives 0.22 at r 40 (1.7), ±0.04 for the modulus. Pass:
   at most 0.29 (2.2) loaded, back within 0.02 (0.15).
8. The stop-equivalent load: the lever plus 4.5 kg sideways at the -X lug (r1g6 STOP_0: 179 N on the plate, about 26 N sideways).
   - Sideways, bolts tight: at most 0.05 with a dial. With the pointer method this check is lost; it becomes "no visible
     movement, under about 0.1".
   - The lug's X slip is recorded with the bolts loosened: at most 0.25, and back within 0.03 (dial) or no visible offset (mark).
9. A 1.5 × yaw proof, 13 kg at 200 mm (25.5 N·m), as the last load. Pass: no click, crack or whitening, back within 0.03 (0.23).
   Then the hub lug roots are inspected and photographed.
10. The imprint inspection after all the loads: the plate hole edge and the hub hole rim, the plate's outer corner, and the hub
    lug's outer front edge.
11. A 24 h re-check (rock and play reversal); then the coupon inserts' 0.5 / 0.7 N·m check.

**Prints (not released):** in `cad/prints/upper-arm/`.
- Halves: `upper_arm_organic_back_r1h.3mf/.gcode` (with the tie bridge) and `upper_arm_organic_front_r1g.3mf/.gcode`.
- Hub-end coupon: `..._r1g_coupon`.
- Shim ring set: `upper_arm_organic_shim_rings_{A,B,C}_r1g` (0.30-1.10 by 0.05).
- Lug plates: `upper_arm_organic_lug_plates_{A,B}_r1h_d34` (Dia 3.4 hole), two full sets on each plate.
  - They were renamed from `..._r1g` (review 3, item 8), so a Dia 3.8 file from an older commit cannot be mistaken for them.
  - `cad/prints/upper-arm/SUPERSEDED.md` lists what not to print.
  - The 0.9 strip above the hole prints as 2 whole perimeters, plus the outer perimeter
    (`r1h_d34_lug_plate_strip_slice.png`: 3 lines cross the strip on every plate).
- Coupon yaw lever: `upper_arm_organic_coupon_yaw_lever` (106 min / 72 g; `cad/scripts/arm/yaw_lever_print.py`).

Sheets: `r1g_front_half_sheet.png`, `r1g_shim_ring_set_sheet.png`, `r1h_d34_lug_plate_set_sheet.png`, `r1g_seam_section.png` here, and
the R1h back half in `../20261111_r1c-delta/r1d/r1g/r1h_back_sheet.png`.

**Open:**
- **Read-back trim test** (all-node GetStress against per-body GetStressForEntities3): not done.
  - A saved r1g6 study re-opened in a hidden instance gives no Results object out of process. Results stays None, and the
    results folder can only be read through StaticStudyOptions, which faults from Python.
  - Proposed: do the two reads right after the next real solve, while the result is in memory.
- The hub: D3c7 released (355aa9b) with its print file; stage 1 can print.
- The bench (hub-end coupon first).

**Superseded (record only).**
- **r1g4** (hub lug holes Dia 3.4, plate holes Dia 3.8).
  - Its table, lug loads and probes are in `r1g4_*`, and this packet's r1g4 version is pinned at
    06b3e5fb6607cf130e74c40f7700176e29c61ef2.
  - The lug landed on its bolt in the stops and in G90 + yaw (STOP_0 -0.006, the shank bearing 32-43 N).
- **r1g5** (both holes Dia 3.8). The plate and hub holes sat edge on edge.
- **r1g2** (plate hole Dia 4.4). Its STOP_0 plate-hole edge was the known item: post shear 0.33 / 0.76, hub face 0.72 / 0.98.
  Reports: `r1g2_*`.
- **r1g3** (Dia 6.0). It cut through the plate's top edge.
- **R1g with Dia 3.6.** The plate edge met the hub's hole rim.
- **R1f** (the D3 candidate with a step and column).

## R1e: the design for review (2026-11-12)

The ring geometry below (R1d ring) stays, but its crush-rib fit is retired. Joey chose a play-free joint, and **R1e** gets it
from a printed shim:
- **Flank line-to-line** as printed (gap 0), no ribs. Lead-ins at the ridge ends: the load flank relieved 0.1 along its normal
  over the last 2 mm of arc each side of the seam, both halves (so closing doesn't bind or scuff).
- **End face lowered 0.70.** A printed PETG shim ring, r 36.2-38.4 (2.2 mm wide, on the rev D disc's flat face, r 36.05-38.73),
  sits between our end face and the hub disc. The thickness is picked by trial at assembly from a set of 0.30-1.10 in 0.05 steps
  (17 sizes, 22 rings, 3 plates, 55 min, 9.1 g). Notches in the ring's inner edge mark it: t = 0.25 + 0.05 × N.
  - Tolerance stack (axial): arm flank to end face ±0.115, hub groove flank to disc ±0.15, flatness ±0.05 (arm) and ±0.1 (disc
    at its seam). Worst case ±0.415, RSS ±0.22. The set covers the worst case.
  - Pick: "start with the thickest ring and work down until the front half closes by hand with the seam shut; use that one".
    Residual play is at most one step (0.05 axial, ≤ 0.28 mm at the wrist).
  - Why not a wedge: closing is along Z, so seating the 30° flank across ±0.2 would need each half's hub end to move 0.4.
    Bending it that far needs about 9 kN against about 0.8 kN per screw. Notes: R1D_NOTES.md, "R1e".
- Unchanged from the ring design: slot edge break 1.2 × 1.6 for the rev D lug-root fillets, the 0.5 bore chamfer (moved down
  with the end face), the as-built bolt joint (brass inserts), fins, hub rev D (bc16e97).
- Outside: the shim shows as a thin band at the arm-hub junction, 0.6 inside our skin. The shoulder cuff ends about Y 313.6, so
  it doesn't cover it. The step visible in the band near θ 70-110 and 250-290 is the hub's own outer wall stepping out (r 38.76
  to 39.3). Pictures: `r1e_hub_end_front.png`, `r1e_hub_end_back.png`, `r1e_shadow_line_closeup.png`,
  `r1e_side_with_shoulder.png`, `r1e_junction_under_cuff.png` (the last two use the shoulder thread's WIP fork meshes).

R1e checks (`../20261111_r1c-delta/r1d/r1e/`):

| Check | Result |
| --- | --- |
| Slice + mesh gate, halves | Back PASS 5 h 25 / 123.8 g; front PASS 4 h 44 / 107.3 g |
| Accepted thin walls (back half) | Three counterbore exits, the same features as R1's accepted entries. A point-to-surface diff against the R1d ring half shows ≤ 0.05 mm there; the R1e tessellation merged two regions and stretched two 1-2 mm up the counterbore wall, out of the old boxes. Three entries added with that reason (`r1e/print_whitelist.json`). |
| Closing path against bc16e97 with a 0.70 ring | 0 path collisions (hub + ring, RS02, RS02 ring). Final overlap ≤ 0.041 mm (front) / 0.039 (back), only along the load flank: line-to-line through faceted meshes. None within about 9° of the seam (lead-ins). |
| Hub-end fit coupon (cut at Y 284) | Back PASS 69 min / 16.9 g; front PASS 64 min / 16.1 g; cut-plane slivers accepted in a coupon-only list. Procedure: BENCH_TESTS.md section 2b, pass rule included. |
| 0 gap G90 (flank line-to-line, shim lumped into the end face) | All ≥ 1.5. Lowest: end-face corner θ 296, shear 1.68 / 3.48 / 11.14 at 0.5 / 1 / 2 mm (0.81 at the 0.1 gap). Hub groove bottom / spigot core layer 2.20; posts layer 2.38. |
| 0 gap STOP_0, STOP_124 | Done on the clean 4.0 mesh (r1e_g00_stop_d, r1e_g00_stop124_d; the 0.4 / 0.5 lug-root refinement at global 5.0 broke the spigot-underside mesh and was dropped). STOP_124 is 1.33 or more. STOP_0 is 1.2 or more except the lumped end-face corner (shear 1.04 / 1.93). Superseded by R1g. |
| Shim ring bearing (from the lumped runs; the ring was **not** modelled as a separate body, see below) | End-face contact pressure of the 0 gap model mapped onto the ring annulus r 36.2-38.4 (516 mm2), arm side. Mean / net axial force / worst 30 deg sector mean / worst 0.5 mm / 1 mm average / peak (MPa, compression): G90 1.2 / 0.64 kN / 4.6 / 15.2 / 7.4 / 29; STOP_0 1.0 / 0.50 kN / 3.0 / 30.1 / 13.6 / 43; STOP_124 2.2 / 1.1 kN / 9.4 / 19.7 / 15.1 / 21; YAW +17 1.2 / 0.64 kN / 4.4 / 35.2 / 14.3 / 69. Against 45 MPa (the model's PETG yield; printed PETG compression is about 55-60 and through the layers is not a weak direction): sector means SF 4.8 or more, 1 mm averages SF 3.0 or more. The 0.5 mm values and the peaks all sit at r 36.40, the contact edge where the 0.5 bore chamfer meets the end face: a model edge, local to the ring's inner rim. Hand check: 1.1 kN over 516 mm2 is 2.1 MPa mean (the shoulder thread's figure is about 3 MPa per kN on their 324.6 mm2 seat; same order). `ring_bearing_lumped.txt` |
| **YAW_17** (RS02 17 N·m peak about the hub axis, both signs; 0 gap lumped model; global 4.0, 0.8 on posts / lugs / fins, lug-root fillets at 0.8) | **Below 1.5.** The ring carries no torque about the hub axis, so all of it goes through the lugs: 312-334 N per lug in Z (pads < 1 N). Loaded post (the one the lug pushes on, at its top edge by the slot break, Y 294.5): vm 0.99 / 1.41 / 1.86 (+17, +X front, n 6/31/170) and 0.95 / 1.47 / 2.05 (-17, +X back); the opposite-corner posts 1.17 / 1.09; post shear 1.07-1.54. Hub lug roots layer 0.92-0.96 / 1.32-1.38 / 2.1-2.2, shear 0.95-0.99 (0.8 mesh: the refined value would be lower). Hub lug bolt-hole bearing 1.19-1.26. Inserts vm 188 MPa (SF 1.27 vs brass yield). Bolts SF 4.9-5.4 (transverse shear only about 30 MPa: the load runs along the bolt axis). Fins ≥ 3.2. End-face corner θ 296 (+17) shear 0.69 / 1.23 / 2.88: the lumped model's contact edge, where R1e has the shim. G90 + yaw by superposition: the same figures within 0.05 except the end-face corner (0.49 / 0.88 / 2.11). `r1e_g00_yaw*3*.txt`; remedies in R1D_NOTES.md "YAW_17" |

Rejected variants, and why:
1. **R1c / R1d partial ridge with tapered ends:** failed at the ridge ends in STOP_0 (arm vm 0.64 / shear 0.71 at θ 143, confirmed
   with the corrected post-processing). Replaced by the full ring.
2. **0.1 flank gap + crush ribs (R1d nominal):** the ribs carry the flank load as point contacts and bed in under routine G90
   (crown rib about 95-130 N against about 41-51 N to flatten). That leaves play equal to the print gap: 0.115 / 0.231 axial,
   0.66 / 1.31 mm at the wrist for gaps 0.1 / 0.2. Joey asked for a play-free joint.
3. **Load-carrying ribs (R2 sizing on paper):** ribs strong enough for G90 at 1.5 need about 53 mm² of face, about 2 kN to crush
   on closing; the screws give about 0.8 kN each. Load-carrying and take-up conflict.
4. **Wedge seat by seam relief:** seating the 30° flank across ±0.2 needs each half's hub end to move 0.4 along Z. Bending it that
   far takes about 9 kN, and relieving the whole seam would open the elbow end.
5. **Split clamp band** inside the skin: in PETG the band can't both flex 0.4 under about 1 kN and carry the loads.
6. **TPU spring bias** in the end-face gap: no rattle, but only TPU-stiff when pushed: about 4 mrad of G90 rocking, 1.6 mm at the
   wrist.
7. **R0.8 round on the end-face inner edge** (instead of the 0.5 chamfer): would cost bearing, and is not needed. The G90 corner
   value it targeted was a contact-edge value of the gap design; at 0 gap it is 1.68.

Open caveats:
- **Upper hub approximated above Y 300.5.** The FEA hub is our ring hub plus the rev D lug-root fillet (the same edge selection as
  the shoulder thread). Through the joint (Y 295.5-300) its sections match bc16e97 within 0.1 %. Above that, rev D's outer wall
  and top boss differ, so the hub's upper-region figures are indicative only; the shoulder thread's FEA governs there. Our FEA
  hub also has a sharp spigot foot where rev D has about R0.23 (it doesn't touch the arm).
- **Mesh:** 4.0 mm global (5.0 in the refined stop runs), 0.8 on the seat, posts, lugs and fins. The lug-root fillets are refined
  to 0.4, not 0.3: 0.3 exceeded the solver's memory limit (458 k nodes). The groove band can't be refined, because its faces are
  full rings (2.3-3.0 M nodes).
- **Model:** frictionless contact, no bolt preload, linear PETG, isotropic stiffness with layer allowables. The shim ring is held
  on the disc by the touching-face bond, with no-penetration against our end face.
- **The ring was not modelled as a separate body.** A shim-body model (the ring as its own PETG body, bonded to the disc, frictionless no-penetration to our end face) was tried three times. The ring separated correctly in the normal direction, but the contact stuck tangentially: in STOP_0 about 10-11 N.m of the stop's twist went through the ring as shear (mean tau 0.54 MPa, slip 0.0005 mm) and the lugs carried nothing, with friction logged off on every contact set. The cause was not found within the time given, so those runs are dropped. The lumped, frictionless runs load the lugs, posts and hub fully, so they are the conservative cases for those parts; the ring's own bearing is taken from them (table above).
- **Shim creep:** the ring sees about 1-2 MPa mean and 3-9 MPa over the worst 30 deg sector in G90 and the stops, a few percent of PETG compressive strength in the sector means; at that level PETG creep is a few um on a 0.7 ring over long holds. The local 15-35 MPa at the inner edge (r 36.4) is a contact edge that beds in. The bench split-and-inspect step measures the ring after the cycles (thinner by 0.03 or more, a flattened band or a cut inner edge: stop).
- **Shim thickness:** printed accuracy about ±0.03-0.05 (first-layer squish on SuperTack). The pick by trial absorbs it; a set
  offset as a whole is reprinted shifted, never the arm.
- **Before the halves print:** the hub-end coupon must pass (closes by hand with a ring, seam shut, no rock after ten cycles,
  nothing scored).
- The seed slicer project sets no elephant-foot compensation; the seam lead-ins (0.1 × 2 mm) are what keep the ridge ends from
  binding. To be seen on the coupon.
- The accepted thin-wall entries for R1e (three counterbore exits) rest on the ≤ 0.05 mm surface diff described in the table above.

The R1d ring sections below are the history of how the ring and these numbers were reached. Cases 3-5 there are the rib design
that R1e replaces.

## What changed (R1c to R1d ring)

1. **One axial datum.** The end face at Y 302 bears on the hub disc. The floor and the hub-post tops are cut back to Y 295.7,
   0.3 under the spigot. The floor corner ring is gone.
2. **Ring ridge.** It is a full semicircle per half, so it is a continuous 360° ring through the seam, with no ends. (R1d's
   first version, a tapered ridge, failed at its ridge ends under the stop: arm vm 0.64 / shear 0.71 at θ 143. The corrected
   post-processing confirms it, `../20261111_r1c-delta/r1d/r1d7_tg01p_stop.post_resplit.txt`.) Section:
   - 30° load flank set 0.1 off the groove's flank, measured normal to the flank;
   - tip at r 34.8; top chamfer (34.8, 300.4) to (35.0, 300.8);
   - 45° flank; top flat at Y 301.5;
   - 0.5 × 45° bore end chamfer, unchanged from R1c.
3. **Crush ribs.** 12 ribs on the load flank, 6 per half, at θ 15 / 45 / 75 / 105 / 135 / 165 (+180), about 1 × 1 mm. They
   print 0.25 proud and crush on assembly to take up the 0.1 flank gap, so there is no axial play.
4. **Collar** r 35.9-37.4, Y 295.7-302, with a foot chamfer. Head counterbores Ø6.0 for DIN 912 M3 socket heads.
5. **Slot edge break, new today.** The shoulder thread's hub rev D candidate (bc16e97) adds R1.2 fillets where the lugs' Z faces
   meet the spigot underside. Our slot walls (the posts' lug faces at |Z| 5.1, up to Y 295.7) get a 1.2 (down the face) × 1.6
   (across the post top) chamfer along each fillet's X span ± 0.5: X 139.75-149.0 and 192.0-201.25, all four post faces.
6. **Hub (shoulder thread, rev D candidate bc16e97).** Full-ring groove, r 23-28.2 fill, and the R1.2 lug-root fillets.

The R1c print files (0d8f841) are not released and do not change.

## FEA route, and what was fixed on the way

- **Model.** Hub-seat contact model: arm, hub, steel M3 bolts and brass inserts as separate bodies.
  - No-penetration contact at the seat and at the lugs. Contact set type 0 = no penetration; the types are read back and
    printed in every run log.
  - Bolt joint as built: in the front post, a Ø4.0 × 5.7 brass insert bonded in its hole (explicit bonded sets), with the bolt
    bonded inside it. In the back post, the bolt's head on its seat and its shank in the Ø3.4 clearance hole, both in contact.
    No preload.
  - Four soft pads (Ø1.8 × 0.3; E 0.5 MPa stop, 0.05 G90) stabilise the arm in the gap cases. Their forces are reported (a few
    newtons against 515 N).
  - Hub fixed at its top face (Y 319.86).
- **Solver.** The automatic choice (FFEPlus, iterative) stalled at contact iteration 7 on the ring.
  - SolverType can't be written from our out-of-process scripts; every value faults inside SolidWorks.
  - A plain-text SolidWorks Basic macro, run inside our own instance, sets direct sparse. SolidWorks maps that to Intel direct
    sparse. The benchmark log of every run confirms the solver.
  - At 1.8 mm global the factorisation ran out of memory ("error 24" = analysis failed).
  - Used: 4.0 mm global, 0.8 mm on the seat faces and on the lug / post / fin faces. That is 390-410 k nodes, solving in 7-11
    min at under 12 GB.
- **Post-processing bugs found and fixed** (`hub_r1c.py`).
  - The solver lists each body's surface nodes before its interior nodes. The old index-range body split counted (a) the -X
    bolt as arm, so an "arm post" layer peak of 76.6 MPa was a steel node, and (b) about 15,500 hub surface nodes as arm. That
    shifted arm figures in every result since 2026-11-11.
  - The split is now geometric, with a single cut per body boundary in node order.
  - A **guard** stops the run if any arm or hub node lies inside another body (hub mesh by > 0.15; bolt, insert or pad by
    > 0.05).
  - All results in this packet use the fixed version. The tapered failure and the ring decision were re-checked with it.
- **Memory.** Every python analysis / geometry / slicing job runs under a 6 GB Windows job-object cap (`capped.py`). Solves run
  under a watch: stop cleanly at 12 GB used or under 4 GB free.

## Fit checks

| Check | Result |
| --- | --- |
| bc16e97 against 556cc44 (fixed-axis sections) | Only the lug roots differ: X 140.5-148.5 and 192.5-200.5, Y 295-296, 0.619 mm² per section = two R1.2 fillets. STL SHA-256 18db5676...f261e verified. |
| Slot break against the bc16e97 fillets, full span including the run-outs | Minimum 0.285 (+X front), 0.292 (-X front), 0.451 (back). Run-out ends 0.55-0.58. Target 0.2. `../20261111_r1c-delta/r1d/slot_break_vs_bc16e97.json` |
| Lug-bearing area the break removes | 6.2 mm² of 48.4 (front) / 51.8 (back) mm² per post face (13 %) |
| Ligament from the break to the insert mouth on the face | 0.5 mm (front, Ø4.0 insert hole); 0.8 mm (back, Ø3.4) |
| End face against the rev D spigot-foot fillet | The 0.5 chamfer clears it by 0.248. The end face (r 36.4-37.6) seats flat on the Y 302 datum. A sharp edge would land on the fillet. `endface_clearance_bc16e97.json` |
| Front lug-face gap | 0.086 rather than 0.1, on 556cc44 and bc16e97 alike (the lug face sits 0.014 proud). Not new. |
| Closing path and final overlap, ring print halves against rev D 556cc44 | Overlap only at the 12 crush ribs, at most 0.15 (the intended crush). *To be re-run against bc16e97 with the slot break in the print rebuild.* |
| Slice + mesh gate (ring halves, before the slot break) | Back PASS 5 h 26 / 123.7 g; front PASS 4 h 45 / 107.9 g. *To be re-run in the print rebuild.* |

## Results: combined geometry (bc16e97 fillets, slot break, as-built joint)

Worst sphere-average SF at 0.5 / 1 / 2 mm, PETG yield 45 MPa, across-layer allowable 22.5 MPa (arm σz, hub σy), interlayer
shear 13 MPa. n = nodes in the 0.5 mm sphere. Targets: 1.2 at the stop (515 N), 1.5 in G90. Every region of every case is in
the post-processing files (`../20261111_r1c-delta/r1d/r1d11_*.post.txt`).

| Case | Lowest (0.5 / 1 / 2 mm, n) | Posts vm / layer / shear (0.5 mm) | Hub lug roots vm / layer / shear | Hub groove bottom layer / shear | End-face corner vm / shear (0.5 / 1 / 2) |
| --- | --- | --- | --- | --- | --- |
| 1. 0.1 gap STOP_0 | end-face corner θ 18, vm 1.18 / 2.15 / 6.13 (7) | 1.76 / 2.32 / 2.21 | 2.14 / 1.27 / 1.21 | 1.21 / 1.29 | 1.18 / 2.15 / 6.13; 1.24 / 2.14 / 5.92 |
| 2. 0.1 gap G90 (target 1.5) | **end-face corner θ 296, shear 0.81 / 1.88 / 6.55 (9)** | 3.97 / 2.69 / 3.38 | 14.1 / 16.8 / 9.9 | 2.21 / 2.36 | 1.23 / 2.58 / 8.25; **0.81 / 1.88 / 6.55** |
| 3. nominal STOP_0 (ribs 0.1 proud, touching): rib bedding | **θ 135 crush rib: arm shear 0.36 / 0.66 / 1.41, vm 0.47 / 0.80 / 1.59 (20-21); hub flank shear 0.70 / 0.90 / 1.57, layer 0.85** | 1.87 / 1.85 / 2.26 | 2.01 / 1.33 / 1.26 | 0.97 / 1.20 | rib-dominated (bore wall by the rib 0.53 / 0.39) |
| 4. nominal G90 (target 1.5): rib bedding | **crown crush rib θ 105: arm shear 0.43 / 0.73 / 1.70, vm 0.60 / 0.93 / 1.94 (18-20); hub flank shear 0.83, layer 1.15** | 3.04 / 2.32 / 3.12 | 8.4 / 18.4 / 7.8 | 1.28 / 1.99 | rib-dominated (bore wall by the rib 0.77 / 0.49) |
| 5. nominal STOP_124: rib bedding | **ribs θ 75 / 45: arm shear 0.36 / 0.60 / 1.41, vm 0.45 / 0.72 / 1.56 (18-22); hub flank shear 0.65, layer 0.86** | 1.74 / 1.64 / 1.91 | 2.42 / 1.48 / 1.46 | 0.93 / 1.35 | rib-dominated (bore wall by the rib shear 0.44) |
| 6. 0.2 gap STOP_0 | **hub lug root (fillet, -X lug +Z), shear 1.04 / 1.64 / 2.58, layer 1.11 / 1.65 / 2.73 (11)**; hub groove bottom layer 1.17; spigot core layer 1.19 | 1.79 / 2.72 / 2.46 | 1.83 / 1.11 / 1.04 | 1.17 / 1.25 | 1.25 / 2.28 / 6.19; 1.30 / 2.45 / 5.95 |
| 7. 0.1 gap STOP_0 repeat, 0.3 mm on the lug-root fillets | not run: superseded by R1e / R1g | | | | |
| 8. 0 gap (flank in contact, no ribs) G90 | not run: superseded by R1e / R1g | | | | |
| 9. 0 gap STOP_0 | not run: superseded by R1e / R1g | | | | |
| 10. 0.2 gap G90 | not run: superseded by R1e / R1g | | | | |
| 11. 0.1 gap STOP_124 (highest lug load, flank bearing) | not run: superseded by R1e / R1g | | | | |

Also per case: lug forces (-X lug about 190 N in Z at the stop: the ring carries no torque about the hub axis, so the lugs take
the stop moment's twist), inserts about 60-70 MPa (SF ≥ 3.5 against brass), bolts about 56-60 MPa, pads ≤ 3.4 N.

End-face bearing on the hub disc (σy on the face, r 36.45-37.55):
- STOP_0: mean 0.41 MPa, peak 32.7 MPa (SF 1.38), worst 0.5 mm average 9.3 MPa (SF 4.8).
- G90: mean 0.99 MPa, peak 18.6 MPa, 0.5 mm average 5.8 MPa.
- The chamfer-edge nodes reach 53-62 MPa locally.

## The honest low spots

1. **G90 end-face contact edge, shear 0.81 at 0.5 mm** (target 1.5). This is where the 0.5 chamfer meets the end face: a
   compressive contact edge, 1.88 by 1 mm and 6.55 by 2 mm. Decision: keep the chamfer, because the face is only 1.2 mm wide
   and a real PETG edge beds in. The bench split-and-inspect step looks at that edge and the hub disc for crushing or
   whitening.
2. **Rib bedding, expected, not a strength failure (cases 3 and 4).** With the ribs 0.1 proud and touching (the as-assembled
   state), the crush ribs carry the flank load as point contacts: the θ 135 rib in the stop (arm shear 0.36 at 0.5 mm), the
   crown ribs θ 75 / 105 in G90 (0.43). A rib's flank face (about 0.9 mm²) holds about 41-51 N before flattening; the crown ribs
   see about 95-130 N normal in G90. So they bed in within the first routine cycles until the flank bears, which is the
   strength case covered by the 0 / 0.1 / 0.2 gap runs. Play once bedded: axial 0.115 / 0.231 mm and rocking 0.09° / 0.18° for
   gaps 0.1 / 0.2 (0.66 / 1.31 mm sideways at the wrist), showing only on load reversal.
   **Flag: hub flank marking under a rib (hub shear 0.70 stop, 0.83 G90, local), for the shoulder thread and the reviewer.** R2
   options: wider / longer ribs that crush flush on assembly, or a line-to-line flank. A fit coupon tests closing, crush and
   play on a printed rev D hub.
   Earlier wording of this item: **Nominal stop: the θ 135 crush rib carries the flank load.** It is overloaded at the rib (arm shear 0.36 at 0.5 mm, 0.66
   at 1 mm, on about 20 nodes), and the hub flank under it is marginal (0.70). Under the first full stop the rib should crush
   about another 0.1 until the flank engages, which is effectively case 1. That uses up part of the ribs' no-play fit and may
   mark the hub's groove flank. The bench notes already look for rib marks. **Open: accept, or change the ribs.**
3. **Hub across-layer values of 1.2-1.3** at the groove bottom, spigot core and lug roots in the stop cases. They are at or
   just over the 1.2 target. The lug-root fillet barely lifted its root (1.23 to 1.27), and its mesh is being settled in
   case 7.
4. **End-face corner at θ 18 in the stop: vm 1.18 at 0.5 mm.** Same contact-edge character as item 1: 2.15 at 1 mm.

## Not verified / caveats

- **Upper hub approximated above Y 300.5.** The FEA hub is our ring hub with the rev D lug-root fillet applied (the same edge
  selection as the shoulder thread's build). Through the joint (Y 295.5-300) its sections match bc16e97 within 0.1 %. Above
  that, rev D has a slightly larger outer radius and a much smaller top boss, so our top fixture face is larger. The hub's
  upper-region figures (outer ring above the groove) are indicative only; the shoulder thread's own FEA governs there. Our FEA
  hub also has a sharp spigot foot where rev D has about R0.23; that does not touch the arm.
- Frictionless contact, no bolt preload, linear PETG with isotropic stiffness and the layer allowables above. Print
  tolerances and droop on the bore's ceiling are not modelled.
- The pads are numerical stabilisers. Their forces are reported in every case.
- No printed rev D hub has been fit-tested against these halves.

## Questions for the reviewers

1. Is the nominal-stop rib overload (item 2) acceptable for a bench article, given the ribs are meant to crush? Or should the
   ribs change: lower (0.15 printed), wider, or more of them near θ 135 / 45?
2. Is the G90 end-face contact edge (item 1) acceptable as recorded, with the bench inspection?
3. Do the slot edge break and its 0.5 mm ligament above the insert mouth print and hold acceptably?
4. Does anything in the R1 / R1c reviewed findings stop holding because of these changes?
