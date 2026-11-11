# Upper arm R1c: delta review packet (2026-11-11)

Pinned commit: 0d8f841d2245ffeee17ec1b45634937756a7691a (branch `left-arm-organic-r1`)

**Scope: the change from R1 to R1c only.** R1 (commit 70cf634) was reviewed in `../20261111_print-release/`. Review:
- the fins, ridge, collar and chamfers;
- whether the ridge prints in the seam-face-down orientation;
- the assembly order around the hub and the RS02;
- whether any of R1's reviewed findings is no longer valid.
Everything you need is in git. No SolidWorks is needed: the STL/STEP exports, sliced 3MFs, scripts, FEA notes and
pictures are all here. File hashes are in `SHA256SUMS.txt`.

## What changed (R1 to R1c)

The geometry changes only between Y 276 and 302 (the hub end). Frame: the hub axis is Y; r is measured from that axis
(X 170.49, Z 5.986); θ runs from +X toward +Z. The front half is Z > 5.986, the back half Z < 5.986.

1. **Hub-post fins:** 9 mm fins joining each of the four hub posts (X 147.5 / 193.5, Y 291.4) to the seam posts (Y 272),
   over Y 276 to 291.4, from the lug-face level out to 0.4 into the skin.
2. **Ridge in the hub seat:** it closes around a groove in the hub spigot, the shoulder thread's hub rev C+. Section
   (r, Y), revolved over θ 35-145 (front half) and 215-325 (back half), with flat radial end faces:
   - load flank (the low-Y side): 30° from the radial plane, line-to-line with the groove's flank,
     Y = 298.0 + (35.8 − r)·tan 30, from the bore (r 35.9, Y 297.94) to r 34.67;
   - 0.2 mm chamfer to the tip face at r 34.5, Y 298.95-299.85;
   - top chamfer (34.5, 299.85) to (34.9, 300.70); 0.26 minimum clearance to the hub's R1.0 groove-corner round;
   - 45° flank Y = 300.1 + (r − 34.3) up to (35.9, 301.70), 0.3 axial clearance from the hub's flank;
   - top flat at Y 301.5 for r 35.7-35.9, where the bore end chamfer starts.
   The hub groove: bottom r 34.3, Y 298.87-300.4; full depth over θ 30-150 / 210-330; taper run-outs to 20/160; no
   undercut of the disc. Hub side, out of scope here: the r 23-28.2 inside fill, an R1.0 on the 45°-side bottom corner,
   R0.4 on the load-side corner and on the spigot bottom edge.
3. **Seat collar:** a full ring, r 35.9-37.4, Y 296-302, so the seat wall is solid all round. In R1 the arm's hollow
   inside reached up to Y 299 at θ about 20-60 and 110-160, with its inner surface at r 36.2. Outer skin there:
   r ≥ 38.21.
4. **Bore end chamfer:** 0.5 × 45°, from (35.9, 301.5) to (36.4, 302.0), for the hub's R0.3 spigot-to-disc corner.
5. **Floor corner ring:** 0.25 × 45° in the bore-to-floor corner at Y 296, only over θ 72-108 (front half), where the arm
   has a floor.

R1c needs the grooved hub. **It does not close around today's hub**: the ridge sits 1.3 mm into the plain spigot, about
220 mm³ of overlap per half. The hub now goes into the back half before the front half closes along Z
(`cad/upper-arm/BENCH_TESTS.md`, "R1c halves").

Scripts diff: `r1_to_r1c_scripts_diff.txt`, `git diff 70cf634 0d8f841` of organic_master, organic_parts, organic_print and
hub_seat. R1c builds with `ARM_R1C=1 ARM_RIDGE=1 ARM_SEAT_RIBS=0`; without those flags the code builds R1.
Geometry against R1: `geometry_diff_R1_to_R1c.txt`. Surface distances over 0.05 mm occur only at Y 276-302. The
boolean-difference boxes reach lower only because tessellation slivers chain together.
Front +2,978 mm³, back +4,730 mm³ (about 9.8 g, mostly the fins).

## Pictures

- `ridge6_section.png`: section of the arm mesh against the hub rev C+ mesh at θ 90 and θ 30, plus a close-up.
  Today's hub is dashed.
- `ridge_collar_closeups.png`: the hub end of each half, looking into the seat; the bore, ridge, chamfers and collar
  face are orange.
- `back_r1c_sheet.png`, `front_r1c_sheet.png`: as printed, bed side included. Faces printed on support: orange =
  visible on the arm, blue = hidden.

## Checks done

| Check | Result |
| --- | --- |
| Hub-seat contact FEA (bolted, no preload, grooved hub as its own body, lugs in frictionless contact, steel M3s), G90 and STOP_0 (515 N) | Arm passes at the 0.5 mm average: G90 ≥ 2.42, stop ≥ 1.29. Every peak is listed unexcluded. See `RIDGE5_6_FEA.md` (ridge6b and ridge6c). Each case was solved twice and matched exactly. |
| Hub side of the same FEA | All pass except the hub groove's 45°-side corner at the stop: 1.13-1.16 at 0.5 mm. That is the shoulder thread's hub, and their r 23 fill was being solved as this was written. |
| Bolts and lugs, with the ridge in place | Bolts 81 MPa (G90) and 105 MPa (stop). Lug axial force 4-16 N. With the plain hub the same model gives 770 MPa and 453 N. |
| Nothing else moved | G90_fine SF 3.08 against R1's 3.08; HALFK31_fine 1.60 against 1.66 (layer 1.41 against 1.45). Same peak nodes. |
| Closing path | Halves closing along Z onto the rev C+ hub, the vendor RS02 and the ring: 0 path collisions, nothing inside at the final position (`../20261111_print-release/r1c/close_path_ridge6.json`). |
| RS02 fit | Identical to R1 in all 72 values (`../20261111_print-release/r1c/rs02_fit_ridge6.json`). |
| Clearance to the hub fill (r 23-28.2, θ 25-155 / 205-335, Y 296-302.3) | 0.10 mm minimum, over the hub posts at Y 296; nothing inside the arm. |
| Slice (Bambu Studio 2.09.01.70) | Back 5 h 27 / 124.5 g; front 4 h 45 / 108.2 g. No warnings, settings identical to the seed. The 100% modifier now starts at Y 274 (R1: 283). |
| Mesh gate | PASS on both halves. The first slice failed on a 0.25 mm free lip and a 0.2 mm ridge-top wedge; both were removed in the geometry (ridge6c / 6e), not whitelisted. |
| 3MF integrity | SHA-256 written equal to the slicer output; both zips test clean. |

## Not verified

- The ridge's print quality on tree support: its flanks are fit faces, and support removal there has not been tried.
- The load-flank crush ribs (0.15-0.2) in the settled section are **not** in the model. The load flank is line-to-line, as
  in the FEA.
- How the joint behaves with the print tolerances: ±0.1 per part, and droop on the bore's ceiling where the ridge hangs.
- Any fit test of a printed hub rev C+ against these halves. No preload in the bolts.
- The stop-pad region at Y 224-250 is the hot spot recorded for R1, and was not reworked.

## Questions for the reviewers

1. Does the ridge print acceptably seam-face down, hanging from the bore's ceiling on tree support, or should it be
   reshaped (for example a 45° underside) so it is self-supporting?
2. Is the assembly order right? The hub goes into the back half first, then the front half closes along Z over the hub
   and the RS02 + ring.
3. Is the collar's foot at Y 296 (beside the hub posts, stop layer 1.29 at 0.5 mm) acceptable, or should it be blended
   into the arm's inside surface?
4. Does anything in R1's reviewed findings (`../20261111_print-release/README.md`) stop holding because of these changes?
5. Anything else in the delta that makes the halves unfit to print as a bench article?
