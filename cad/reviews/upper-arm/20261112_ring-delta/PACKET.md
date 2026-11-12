# Upper arm R1d "ring": delta review packet (2026-11-12)

Branch `left-arm-organic-r1`. The pinned commit is set when the print rebuild is done. Until then this packet is a working
draft, and rows marked *running* are not in yet. Nothing here is released.

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
| 3. nominal STOP_0 (ribs 0.1 proud, touching) | **θ 135 crush rib: arm shear 0.36 / 0.66 / 1.41, vm 0.47 / 0.80 / 1.59 (20-21); hub flank shear 0.70 / 0.90 / 1.57, layer 0.85** | 1.87 / 1.85 / 2.26 | 2.01 / 1.33 / 1.26 | 0.97 / 1.20 | rib-dominated (bore wall by the rib 0.53 / 0.39) |
| 4. nominal G90 (target 1.5) | **crown crush rib θ 105: arm shear 0.43 / 0.73 / 1.70, vm 0.60 / 0.93 / 1.94 (18-20); hub flank shear 0.83, layer 1.15** | 3.04 / 2.32 / 3.12 | 8.4 / 18.4 / 7.8 | 1.28 / 1.99 | rib-dominated (bore wall by the rib 0.77 / 0.49) |
| 5. nominal STOP_124 | *running* | | | | |
| 6. 0.2 gap STOP_0 | *queued* | | | | |
| 7. 0.1 gap STOP_0 repeat, 0.3 mm on the lug-root fillets | *queued* | | | | |

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
2. **Nominal stop: the θ 135 crush rib carries the flank load.** It is overloaded at the rib (arm shear 0.36 at 0.5 mm, 0.66
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
