# R1h back half: harness tie bridge (2026-11-13)

R1h is the R1g back half plus a cable-tie bridge on the -X inner wall at the neck. The front half and the RS02 ring stay R1g (their
files are unchanged). Not released.

## The bridge

- **Position:** on the back half's -X inner wall, Y 255-261, Z CZ-4 to CZ, standing on the seam face. The back half prints on its
  seam face, so the bridge stands on the bed and needs no support.
- **Shape:**
  - A bar 2.0 thick (X 147.9-149.9), standing off the wall.
  - Posts 1.5 long at each end, embedded in the wall.
  - A slot between bar and wall for a 2.5 x 1.0 cable tie passing along Z, round the bar and the bundle.
- **Slot as built** (sections of the exported STL): X 146.2-147.9 (1.66-1.73 wide), Y 256.5-259.5 (3.00 long), the same from the seam to
  Z CZ-3.6. The tie needs 1.0 x 2.5.
- **Rounds** (SolidWorks fillets on the solid; build log `R1H_TIE_VR: R0.5 on 4 edges`, `R1H_TIE_LOWR: R0.5 on 13 edges`):
  - **Vertical edges:** R0.5 on the bar's two outer corners and the slot's two corners at the bar.
  - **Lower edges:** R0.5 on every lower edge of the bar and posts, except where they meet the wall. Where the posts meet the wall
    is the wall surface itself: no edge, so no round.
  - **Seam face:** stays flat.
  - **Why the change:** the first R1h build rounded the outline in the sketch (shapely buffer). That gave dozens of short straight
    segments, and the lower-edge fillet over them failed. The sketch is now the sharp outline, with the rounds as fillets.
- **Material added:** 69.7 mm³ (about 0.09 g). One body, watertight.

## Checks

| Check | Result | File |
| --- | --- | --- |
| Build | One body; both fillets built | `cad/_wip/r1h_build_rebuild.log` |
| Slice and print gate (back) | **PASS**. 19,707 s (5 h 28 min), 124.29 g, 44.5 mm tall. Support 6,539.7 mm², all inner (R1g: 6,539.2). No visible support spots. The mesh-gate list is the same 14 lines as R1g. | `r1h_back_sheet.png` |
| Bridge against the front half (halves close along Z onto the seam at CZ) | **Clear**. Over the bar (X 147.4-149.9, Y 255.5-260.5), the front half's lowest material is Z - CZ +5.39 to +5.82, so the closing sweep stays 5.4 mm or more above the bar. The posts meet the front half only where the wall continues across the seam, line to line. Overlap is 0.000 mm² in every section. | `r1h_tie_check.txt` |
| Free section at the bridge (bundle passage), R1g vs R1h | Y 256 / 258 / 260: 1684 / 1692 / 1729 mm² down to 1670 / 1684 / 1713 mm². The largest inscribed circle is unchanged (Dia 41.3-42.1). | `r1h_tie_check.txt` |
| Harness route (3.5 x 13 bundle from the D3c7 68 deg window, 53 mm down the arm) | **Unchanged** from R1g: every value in the route JSON is identical. The smallest clearance is still 5.63 mm, at the hub end. | `d3c7_route68_r17.45.json` |
| D3c7 checks repeated on the R1h halves | **Same as R1g**. Closing-path final overlap 0.041 front / 0.039 back, on the ridge flank only. Roots against our posts 0.300. Plate-to-fillet gap 0.267. The window footprint and bore fill are unchanged. Hit and path-collision counts move by a few points between runs (the closing-path sampling); the maxima do not. | `D3C7_CHECK.md` |

## Print files

- `cad/prints/upper-arm/upper_arm_organic_back_r1h.3mf`, SHA-256 7608e70368147d69e3b2bb6e95e3e1f5b0b032ec585f89552418fe0f469228e9
- `cad/prints/upper-arm/upper_arm_organic_back_r1h.gcode`, SHA-256 174c1ed6eb7a81cb16f2c61fbbbe6fc4fddb7d2bb6c17bda3fb248aea445dee9
- From the exported back half, SHA-256 7a4fb8380c0500a0fdd04f2a8ca0129794d1ae7b78d0de595d7cbe4843f8c4c8. Close-up of the bridge:
  `r1h_tie_bridge_closeup.png`.
- The front half and the ring print from the R1g files.
