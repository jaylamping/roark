# Review: upper arm concept A, print release (v26)

**Verdict:** don't release yet. One cheap blocker should be fixed first. Several major items make the FEA claims and the planned bench proofs weaker than the packet says. The halves can be printed as a bench article once B1 is fixed. The parts are not fit for robot use until M1–M4 are closed.

I couldn't open the 3MFs or STLs: shell commands needed approval and this session is non-interactive. Everything about the slice comes from `organic_print.py` and the `*_result.json` / `*_check.json` files, and assumes the 3MFs were built by that script.

## What I checked and what I assumed

**Checked against the JSON and scripts:**
- Every SF in packet tables 3, 4 and 6 matches `fea_results.json` within rounding, including the ×2 for 17 N·m.
- The friction hand calculation is right on its own assumptions: 0.35/(0.2·0.003) = 583 N; × 6 × 0.3 × 36.5 mm = 38.3 N·m.
- Thread engagement: 11.8 − 2.0 = 9.8 mm grip, so 16 − 9.8 = 6.2 mm into the flange.
- The orientation transforms are proper rotations, so nothing is mirrored. The vendor placement matrix also has det = +1.
- The hole clocking holds together: `CLOCK` 93.5 puts the vendor holes at 20 + 40k. Rays through the six used holes hit nothing, and the three tab holes hit at 164.98.

**Assumed, not checked:**
- PETG properties.
- RS02 specs: rated torque about 6 N·m, gearbox not known.
- Stop stiffness in the impact estimate.
- Key width, which decides whether keys have an infill core.
- The elephant-foot compensation value and the `bottom_surface_density` value.

## Blocker

**B1. The 100% infill modifier stops at X 160.5. The keys and the thickened wall past their tips run to X 165.4.**
- **Evidence:**
  - `organic_print.py:75`: the box is `(128,150,-50)–(160.5,262,62)`, and its docstring says it covers "the RS02 rib and its four keys".
  - The ring spans X 153.9–165.7, and the keys stop 0.3 mm short of 165.7.
  - The governing peaks are both at X 165.4:
    - `half_HALFK0_fine` at (165.4, 224.0, −32.8)
    - `half_HALFK02_fine`, bulk 1.30, at the same point
  - v26 added "wall thickening past the key tips", which is exactly the zone left at 50% zig-zag.
  - The FEA assumes solid PETG there.
  - The key coupon prints at 100% everywhere (`key_coupon_result.json`: `sparse_infill_density` 100% vs the seed's 50%). So the coupon is stronger than the part at the very spot it is meant to prove.
- **Smallest fix:** extend the box to X 167, re-slice, and check that the cross-section shows solid infill through the keys and the wall behind them.

## Major

**M1. The stop rating isn't honest at 17 N·m (Q6).**
- **Wrong radius.** 444 N comes from 17 N·m at r 38.25 (`organic_fea.py:8`, `p3_fea.py:62`). But:
  - The load face is picked at r 33.0 (`organic_fea.py:39`).
  - The pad spans r 30.1–35.9 (`stop_post.py` `band()`).
  - The lug ends at r ≤ 37.9.
  - A uniform normal force acts at the pad centroid, about r 33. So the FEA's 889 N is 29.3 N·m, and 17 N·m needs about 515 N, a factor of 1.16. Even at the lug's outer edge (r 37.9) it would be 449 N.
- **Corrected SFs at 17 N·m:**

| Case | Lug root bulk / layer | Elsewhere bulk / layer | No exclusion |
| --- | --- | --- | --- |
| STOP_0_fine | 1.98 / 1.59 | 2.38 / **1.17** | **0.67** |
| STOP_124_fine | 1.97 / 1.90 | 1.53 / **1.22** | 0.75 |
| STOP_124 (coarse) | — | — / **1.15** layer | — |

  The "elsewhere" layer values are below 1.5 even at the packet's own 444 N (1.33–1.42). The README doesn't say so.
- **Stale geometry.** All stop cases are v23: R1 corner, no key-wall thickening.
- **Wrong load path.** These cases are fixed at the hub seat, which is the back-driven path. When the motor drives the forearm into the stop, the load is an internal loop: lug → drum → rib → keys → ring, with the lug and the keys loaded together. That case isn't modelled.
- **Energy (estimate).** Assumptions:
  - forearm and hand without payload: I ≈ 0.025 kg·m²; with 5 kg at 283 mm, about 0.42
  - total stop compliance: 0.2 mm at r 33 under 17 N·m, so k ≈ 2800 N·m/rad
  
  The energy needed to reach 17 N·m is 17²/(2k) ≈ 0.05 J. That is about 2 rad/s unloaded or 0.5 rad/s with payload, before adding motor torque or reflected rotor inertia.
  
  The rating equals the motor's own peak, so a motor-driven hit at peak torque has zero margin before any kinetic energy is added. G90 needs 17.2 N·m just to hold 5 kg, which is the same number.
- **No stop proof in the packet.** The README's stop coupon has no 3MF in `data/prints`.
- **Smallest fix:**
  - Recompute the forces at the pad centroid and re-run STOP_0/124 on v26.
  - State the rating as the corrected value.
  - Give software a speed limit near each stop as well as the torque limit, derived from E = T²/2k.
  - Add the stop coupon to the print set.

**M2. Criterion (b) fails at a second place the packet doesn't declare.**
- Keys 0+2 sharing 34 N·m: halves bulk **1.30** at the key-0 tip and drum wall, (165.4, 224.0, −32.8). The deviation section quotes only the neck-corner value for this pair (1.52 / 2.43).
- Keys 3+1: layer 1.16.
- So both pairs miss 1.5 in the halves.
- The 2.43 layer figure isn't in `fea_results.json`, so I can't verify it. The same goes for E34's 1.10 layer.
- The pair cases also assume equal sharing. See M5 for why that probably won't hold.
- **Fix:** declare it. B1 covers part of it.

**M3. The ring's layer figure is excluded, despite "Ring results exclude nothing".**
- `p3_fea.py:283`: the `layer_*` peaks use `away`, which drops nodes within 2·el (2 mm) of the fixed flange face. That is the 10 layers that would peel.
- Without that exclusion, `region_slot.layer_x` is 78.0 MPa at 34 N·m (fine), or 39 MPa at 17 N·m: **layer SF 0.58** for one key. Pairs K02/K31 give the same 0.58 at 34 N·m.
- That peak is tension on a bonded rigid face, which a clamped, unglued joint can't carry. So it's a fixture artefact, but the real across-layer stress isn't known either way.
- The fixture stands in for six M3 clamping a part that creeps:
  - 583 N on a button-head annulus of about 16.4 mm² is about 36 MPa on PETG.
  - The ring is screwed straight onto the motor flange, which gets hot.
  - Preload will relax well below the 38 N·m friction figure.
- The slot SF also isn't converging: coarse to fine went 1.76 → 1.50, at the fixture edge.
- **Fix:**
  - Correct the packet text.
  - Re-run one ring case with the fixture limited to the screw-head and clamp annuli, keeping the remaining flange face compression-only (no-penetration contact) so it can lift off instead of carrying tension.
  - Add M3 washers or a printed-in steel washer seat, and re-torque after 24 h.

**M4. The axial stack and the thread depth are typed-in constants, not measured (Q4).**
- `rs02_fit.py:17,41`:
  - The flange is placed at `FRONT − 28.0`, a drawing value.
  - `STOP_FACE` 193.9 is a constant.
  - So "gap 0.0" and "front to stop 0.2" are arithmetic on constants, never measured against the vendor mesh or the halves' STL.
  - `vendor_depth` 8.0 is also typed in. The rays down all six used holes find no bottom, so the mesh holes are open through.
- **Worst case:** 0.2 mm nominal, with ring thickness, rib face and stop face at ±0.1 each, plus first-layer squash on the ring, gives −0.2 to +0.6 mm.
  - At −0.2 the RS02 front binds on the stop, or the front half won't close.
  - At +0.6 the elbow has axial play.
- The README says the tab heads stand 2.4 mm proud; the ray says 0.72. The 3 mm pockets cover both, but one of the numbers is wrong.
- **Fix:**
  - Measure the flange face X and the stop face X from the meshes.
  - Get the real hole depth from the vendor drawing, and check where a 6.2 mm tip ends up if the holes are through.
  - Re-run the slide check at ≤ 0.5 mm steps. The current 10/5/2 mm steps can skip thin features.

**M5. Crush ribs and key sharing (Q3).**
- **Interference range per face:** rib 0.25 ± 0.1 (a sub-line-width feature) against clearance 0.1 ± 0.2 gives −0.15 to +0.45 mm.
- **Each half clamps a ring web between its two keys** (0/1 in the back half, 2/3 in the front), so the total per half is −0.3 to +0.9 mm.
  - At the high end the ring won't go in by hand, and PETG smears rather than shaves.
  - At the low end nothing is preloaded.
- **After the first peak load:** two shaved ribs of about 3 mm² each, carrying 453 N, are well past yield. They crush to face contact and leave about 0.1 mm per face plus the stack. From then on one key per direction carries the load, so 34 N·m runs through the single-key case: halves SF 0.81, ring slot 0.75.
- **Fix:**
  - Accept single-key at 34 N·m as the design case.
  - Or make the bearing faces a printed, reamable fit with a shim, not crush ribs.
  - At minimum, measure rib height on the printed halves before first assembly.

**M6. The ring as printed (Q3, Q5).**
- **Brim:** the ring's slice bounding box (91.8 × 90.6) is the part (82.5 × 81.2) plus the 5 mm brim. An outer brim follows the contour into the four key slots and the C-gap window, so first-layer flash lands on the bearing flanks at the layers where the key tips sit (X 165.1–165.4).
- **Elephant foot** narrows the same layers.
- **Fix:** no brim on the ring. It is 11.8 mm tall and won't tip. Add a 0.3 × 45° chamfer on the bed-face edges of the slot flanks.

**M7. Joey's hand-chamfered ring.**
- The R2 round reaches 2R(1 − 1/√2) = 1.17 mm along the 45° line. A 1.2 mm chamfer "touching at 0.00" therefore means the ring seats with roughly zero radial and axial clearance at that corner.
- With a hand chamfer of size a, the gap is (a − 1.17)/√2: 0.59 mm at a = 2.0, 0.23 mm at a = 1.5.
- Hand filing on PETG can't hold the roughly 1.6 mm minimum once ±0.1 tolerances are added.
- If the corner touches, the ring stands off the rib, the RS02 moves toward the 0.2 mm stop gap, and M4 gets worse.
- **Fix:** reprint the ring (58 min, 19 g) instead of filing it.

**M8. Supports on fit faces aren't screened (Q5).**
- In the back half, support touches 7,388 mm² of part faces, and the gate only screens "visible" faces. With the seam face down, the drum bore under the ring and RS02, and the key ends, are overhang roofs.
- **Fix:** list the fit faces (bore, rib face, key flanks and ends, stub) and require zero support contact on them, or a listed allowance.

**M9. Heat and creep at the motor (assumption).**
- G90 is 17.2 N·m, the RS02's peak, against what I take to be about a 6 N·m continuous rating.
- The ring is clamped straight to the aluminium flange. PETG's heat deflection temperature is about 70 °C, and preload, crush ribs and key bearing all creep with heat.
- **Fix:** log the flange temperature during the bench torque test. Re-check screw torque afterwards.

## Minor

- **Bench coupon misses the governing corner.** The key coupon box is dy −10…21, dz −47…−27. The neck corner is at dy 31.6, dz −27.1, outside it. The coupon can't test that corner.
- **Mixed model versions.** Halves keys 1–3 are v25, G90 fine is v25, everything else global or stop is v23. Coarse and fine pairs sometimes come from different versions (HALFK0), so mesh convergence isn't shown for the halves' key cases.
- **Stale whitelist text.** The front-half whitelist still says "R1 round … φ −23". Confirm the front STL has R2.
- **Inconsistent ring-zone exclusion.** `stop_post.py` excludes X 155.8–165.8; the packet says 152.8–165.8.
- **Rounded SFs doubled.** The ring slot "1.50" is 2 × 0.75; the exact value is 1.503, which passes only barely.
- **Bonded halves in the global FEA.** There is no seam fastener in the drum (posts at Y 272 and the hub). Pure torque is fine, because keys 0 and 2 put opposite Y forces into the two halves. But one-key cases push about 447 N net into one half, and seam slip is never assessed.
- **Settings to confirm:**
  - `bottom_surface_density` and `top_surface_density` are overridden. Confirm both are 100%, because the ring's bed face is its clamp face.
  - The elephant-foot value isn't overridden, so it's whatever the preset gives.
  - PETG on SuperTack with a brim risks the part fusing to the plate. Let the plate cool fully before removing parts.
- **Stub coupon.** It was printed with 3 walls at 15% and was never measured. The halves' stub is 6 walls / 100% with seam elephant foot. Measure it on the first half.
- **Slice-time mismatch.** The back half is 5 h 03 in the packet and 5 h 02 in the checklist.

## Answers to the questions

1. **Neck corner:** acceptable only as a bench article.
   - It is about 2.2–2.6 at 17 N·m.
   - At 34 N·m it is 1.10–1.16 layer. Keys 3+1 (−T) is the worse direction.
   - The bench test should torque the whole arm to 34 N·m in −T, through the keys, and watch φ 41° for whitening.
   - It is not acceptable for robot use, and the deviation needs to include M2 and M1's "elsewhere" values.
2. **The web:** it reinforces the rib's rotation from behind, 7–10 mm from a peak that sits on the ring-side surface. Expect only partial relief, and confirm by re-running E34, K31 and STOP_124 on the new version.
   - A more direct internal fix is a bead or doubler along the drum wall's free edge at the neck opening, at φ 36–46 and 331–341, where the σz peak is.
   - The opening could also be narrowed. It spans φ −24…41, and the harness only needs φ ±15.
   - Either way, keep it inside the 100% modifier.
3. **Binding or cracking on assembly:** see M4–M7 and the seam elephant foot. The elbow axis lies in the seam plane, so the bore narrows exactly where the ring and RS02 are widest. Service removal will loosen the ribs further each time.
4. **RS02 placement:** the hole clocking is consistent. Socket angles (`SOCK_MESH`), flange X, stop X and thread depth are all typed in, not derived from the vendor mesh (M4). The pocket depth covers either head height.
5. **Print files:** see B1, M6, M8, and the minor settings item.
6. **Stop rating:** no (M1).
7. **Cables:** nothing in the data shows a pinch, but:
   - The rib gap (φ ±15°) and the RS02 cable (centre about 1 mm below the seam, Ø7) both straddle the seam plane. Dress both into the back half before the front closes, or break the seam-face edges at the gap.
   - The trunk turns 90° from the 7.8 mm gap into the stub bore at X 145.5, and that edge has no stated radius.
   - The cap pocket has 0.8 mm spare width for a coil that slides through 124°. Break its edges.
   - The rigid straight-cable envelope doesn't capture droop past the ring window edges.