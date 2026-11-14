# Review 3 of the r1g6 packet (head 131cd60): findings and responses (2026-11-14)

**Verdict (review):** only the coupon, the hub, the shim rings and the lever. The halves wait for:
- the hub release;
- the hub-root reconciliation;
- the coupon insert result;
- a corrected bench 2b that passes.

No wrong table number was found. Each point below was checked against the files; the response says what changed and where.
Nothing is released.

## Bench 2b (BLOCKER, text): `cad/upper-arm/BENCH_TESTS.md`, section 2b rewritten

1. **Stale hub, hole and loads.** Confirmed: L96 named D3c4 / D3c5, L112 and L145 said Dia 3.8, and step 9 quoted r1g4 loads.
   **Fixed:**
   - The hub is now D3c7, and the plate hole Dia 3.4 throughout.
   - The stop-equivalent step quotes r1g6 STOP_0: 179 N on the -X lug's front plate at X offset 30.2, Y 291.5, and 81 N on the +X
     lug's back plate (lug sections).
   - It also gives the sideways load: about 26 N net toward -X, carried in the model by the lumped plate's edge and in the real
     joint by plate friction or the bolt. The outer face lands with about 9 N.
2. **Step order.** Confirmed: the coupon inserts went to 0.7 N·m before the play and load tests. **Fixed:**
   - 0.3 / 0.5 / 0.7 N·m is now done early on the scrap-block insert only (step 3).
   - The coupon's own inserts stay at 0.3 N·m until step 14, after every load, the imprint inspection and the 24 h re-check.
3. **Pass rule could not fail a one-step-loose joint.** Confirmed. **Fixed:**
   - **Readings on the coupon, not the lever.** All readings are now on the coupon itself against the hub: a dial on the
     coupon's side face at r 40 from the hub axis, on a stand on the hub clamp's base. The lever only applies load; its pocket
     clearance can no longer enter a reading.
   - **New step 8: play reversal**, ±1 kg at the hook (±0.39 N·m) with the lug bolts loosened, three times. Pass: total travel
     at most 0.04 at r 40. Derivation:
     - a one-step-loose pick leaves 0.05 at a lug face;
     - acting at X offset about 30.5 (the FEA centre of pressure is 29-32), that lets the coupon turn 0.05 / 30.5 = 1.6 mrad,
       which is 0.066 at r 40;
     - the ±0.39 N·m itself adds 2 × 0.39 / 17 × 0.32° = 0.015° in total, which is 0.010 at r 40;
     - the dial reads to 0.01.
     - So a tight pick reads about 0.01-0.02, and a one-step-loose pick about 0.076, which fails.
   - **Why not the suggested ~0.13 limit.** It would not catch one step at the radii a dial can reach on the coupon (0.076 at
     r 40, about 0.11 at r 60). I set the limit at half a step instead; the derivation is above. Tell me if 0.13 was meant at a
     different radius.
   - **Step 9 (yaw, 17 N·m)** is now read on the coupon: the FEA expects 0.22 at r 40, ±0.04 for the modulus. Pass: at most
     0.29 loaded, back within 0.02. It is the elastic check; the play is found in step 8.
   - **Step 10 (stop-equivalent)** has its own readings and pass: yaw dial and X dial. With the bolts tight, X at most 0.05.
     - It is then repeated with the lug bolts loosened, recording the lug's X slip: at most 0.25 loaded, back within 0.03.
     - The FEA's free lug closes its 0.20 outer-face gap.
4. **Hole gauges and proof.** **Added:**
   - Step 2, before assembly: every plate hole takes a Dia 3.4 drill shank and not a 3.8, and each hub lug hole takes a 3.8.
     A plate that takes 3.8 is the superseded file.
   - Step 11, the last load: a 1.5 × yaw proof, 13 kg at 200 mm (25.5 N·m) each way. Pass: no click, crack or whitening, and
     back within 0.03.
   - The imprint inspection (step 12) follows it, now also at the hub lug's outer front edge (X offset 34.4, Y 293).
   - The packet's bench summary follows the new 2b.

## Packet and checker (MAJOR)

5. **Checker.** Confirmed: `packet_numbers_check.txt` was the r1g4 output. **Fixed** (`cad/scripts/fea/r1c/packet_numbers_check.py`):
   - Rerun with prefix r1g6; the output is committed: 0 failures.
   - The EXCUSED entries "hub lug ±X incl. roots" are removed, and their rows are now in the table.
   - Completeness now reads post_allc (whole-part rows) as well as the spot and region reports, and all three radii: a row with
     ANY of its 0.5 / 1 / 2 mm values below target must be listed.
   - **Triplets are tied to their labels.** The report line holding a row's triplet must be of the component named before it
     (vm / layer / shear), and its region must share a word with the row's phrase for it. The column header counts only when the
     phrase names no region.
   - A negative test (a groove triplet written as "fins", and a vm triplet as "shear") is caught.
   - The first strict run found 28 missing rows. All are now in the table.
6. **Omitted rows.** Confirmed. **Fixed in the table:**
   - **STOP_0, hub -X lug outer front edge**, vm 0.74 / 1.26 / 2.80 at [136.1, 293.4, 11.0]. Checked from the r1g6 STOP_0
     result, post-processing only (`r1g6_stop0_hub_edge_probe.txt`), against the shoulder thread's explanation. **Confirmed: it is
     the lumped plate boss's step edge.**
     - The arm's boss carries 16-23 MPa on its last 0.5 mm before its edge at X offset 34.2 (X offset 33.2-34.0: mean 10.5-16.0,
       peak 21-23 MPa).
     - The hub face nodes at X offset 34.3-34.45, outside the boss, with no arm face opposite, still read 12.9 MPa mean, 20.3
       peak. Those are values extrapolated from the boss edge.
     - The tensor average at the spot is p1 +51.5, p2 +15.3, p3 -16.9 MPa: bending tension at the edge where the lug's front and
       outer faces meet. The outer face also lands nearby in STOP_0 (about 9 N, centre Y 293.2, Z 9.7).
     - It is gone within 1 mm of the edge:
       - 0.5 / 1.0 mm into the lug (-Z): vm SF 1.47 / 3.11;
       - 0.5 / 1.0 mm inward, inside the boss outline: 1.38 / 2.37;
       - against 0.76 (tensor) at the spot.
     - **The shoulder thread's fine hub reads about 8 there** (von Mises 7.98 peak, 8.71 at 0.5 mm, friction variant; 8.13 / 8.89
       bolt-wall variant; their `A_HUB_LUGS.md` at b5679c6). The table and the known-items list quote it as **the governing
       number**.
     - The "hub's worst is the root" wording is corrected.
   - **STOP_0 whole arm**: shear 0.47 / 1.02 / 1.17, vm 0.65 / 1.51 / 1.88, layer 1.00 / 1.29 / 1.49. The centres are located
     (`r1g6_stop0.worst_centres.txt`, every arm node a centre at each radius):
     - 0.5 mm: the lumped-plate outline corner [136.3, 294.6, 11.0].
     - Shear and vm at 1 and 2 mm: the loaded elbow stop-lug pad at Y 227-228, θ 224-226, r 44-48. That is the load-introduction
       patch where the 515 N goes on as a pressure.
     - Layer at 1 and 2 mm: the neck at Y 250 (X 165.7, Z 14.3, r 9.7). 1.29 and 1.49 are above the 1.2 stop target.
     - **The 2 mm shear 1.17 is under 1.2**, and it is at the stop pad. It is listed below target with the R1 precedent (R1
       excluded the pad patches), not as a pass.
   - **STOP_124 whole arm** 0.82 / 0.98 / 1.17: all three radii at the loaded stop-lug pad, Y 192
     (`r1g6_stop124.worst_centres.txt`). It is now in the table's below-target column, with the R1 precedent.
   - **Convergence wording corrected.**
     - The hub root's shear converged (1.00 → 1.03), but its vm did not (1.84 → 1.48), and the packet now says so.
     - The plate corner's refined values are quoted: shear SF 0.96 at the corner edge (base 1.44), 1.39 at 0.5 mm into the post
       (base 2.09), 2.07 at 1.0 mm (base 1.87).
7. **D3C7_CHECK plates and the slice check.** Confirmed: `d3c7_check.sh` built the 0.75 plate STL with HOLE_R 1.9 (Dia 3.8).
   **Fixed:**
   - The script now builds both plate STLs at Dia 3.4. Checks 2, 3 and 6 were rerun on them.
   - The plate-to-fillet gap stays 0.267 on every lug and face, and the roots against our posts stay 0.300; the hole size does
     not reach either. `D3C7_CHECK.md` is corrected.
   - `plate_slice_check.py`'s description now says the 0.9 strip above the Dia 3.4 hole. The committed slice picture was already
     the Dia 3.4 re-slice from 68c5356: 3 lines cross the strip on every plate. It is renamed with the plates (item 8).
8. **Plate file names.** **Fixed:**
   - `upper_arm_organic_lug_plates_{A,B}_r1g` is renamed `..._r1h_d34` (git mv; the content is the Dia 3.4 re-slice).
   - The sheets are renamed to `r1h_d34_lug_plate_set_sheet.png` and `r1h_d34_lug_plate_strip_slice.png`.
   - `cad/prints/upper-arm/SUPERSEDED.md` lists what not to print. The old Dia 3.8 plate files exist only in older commits
     (0b75a69 and before); the R1g back half is superseded by R1h.
   - The bench hole gauge (step 2) catches a 3.8 plate.
   - The packet and BENCH_TESTS use the new names.
9. **Tie bridge.** The wall at the bridge reads SF 2.77 or more without it (`r1h_tie_wall_probe.txt`), more than 2.0.
   - Readings: STOP_124 shear 2.77 / 2.77 / 2.96 at [146.18, 255.3, 5.37]; STOP_0 shear 3.43, layer 3.47.
   - The mesh there is coarse: 52 arm nodes, one per 0.5 mm sphere.
   - **The geometry stays as built** (coordinator 00:18Z). The unrounded post-to-wall corners are recorded in the packet and
     added to the whole-arm test's inspection list (BENCH_TESTS 5).
   - The STOP_124 layer 1.32 at Y 242 is 13 mm below the bridge.
10. **Mesh guard and body split.** **Fixed:**
    - **Per-body check.** `body_check.py` checks the per-body node counts after the split: one arm run, one hub run, one brass
      run, two steel, three pad runs (four pads), each at least 0.85 of the r1g6 base counts, and no run of 50 nodes or fewer.
    - It now runs in `r1e_solve3.sh` after every solve. The mesh guard still stops a solve early on the total.
    - Every r1g6 result passes (`r1g6_body_check.txt`). The refined run before the fix fails it, as it should.
    - **The split.** Node 279355 (at the D3 lug's outward root, Y 296.3) read signed distance -0.534 from the hub STL. Its 15
      neighbours within 0.6 mm read +0.25..+0.96 inside, so it was classed as arm.
    - `hub_r1c.py` now moves a run of 3 nodes or fewer to the body on both sides of it in node order when 80 % of its 0.6 mm
      neighbours are of that body, and reports it.
    - The refined run was re-post-processed: hub 249755-484515 in one run.
    - **Only one 2 mm value changed** (arm seat bore layer 4.05 → 4.00). The "worse when refined" corner result is unchanged.
11. **Lug loads.** See `r1g6_lug_loads_uncertainty.md`.
    - Per-lug section totals are the ones to trust. The face totals over-read by 1-24 %: ±8-18 % for the loaded lug in yaw and
      the stops, ±24 % on G90's 26-31 N.
    - The "both lugs" net is a small difference of two opposing forces and should not be used.
    - Whole-hub section: its moments balance within 2-3 %. Its forces carry about ±37 N of integration error under G90 (the
      34 N of Fy).
    - Plate force: 49-54 % lies within 1 mm of the plate outline, a band that is 45 % of the plate's area; 2-8 % lies within
      1 mm of the hole.
12. **Optional STOP_0 with separate plate bodies:** not retried, as you asked.

## Also from this round

- **Large-solve lock** (coordinator 00:10Z). `r1e_solve3.sh` takes `C:\joe\.fea_solve.lock` in main's big_solve layout, held for
  the whole job by `solve_lock_hold.py`, and never removes a lock it did not write: one that looks stale is waited on and logged.
- **Read-back trim test: not done.**
  - A saved r1g6 study re-opened in a hidden instance gives no Results object out of process. The results folder setting is
    only reachable through StaticStudyOptions, which faults from Python.
  - It ran under the large-solve lock, which the shoulder thread held until 00:19Z.
  - Proposed: do the two reads in-process right after the next real solve.
