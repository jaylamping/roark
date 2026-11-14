# r1g6 lug loads: which totals to trust, and how the plate force spreads (review 3, item 11; 2026-11-14)

Source: `r1g6_lug_loads.txt` (lug_loads.py) and `r1g6_lug_plate_distribution.txt` (lug_plate_dist.py), r1g6 results, hub side.

## Which totals are trustworthy

- **Per lug, use the section at Y 294.5.**
  - The section integrates the stress inside the lug, through its cross-section. The face rows integrate nodal stresses
    extrapolated to contact faces, and those over-read.
  - Per case, the loaded lug's |faces| against |section| (Fz):

    | Case | -X lug: faces / section | +X lug: faces / section | Uncertainty on a lug force |
    | --- | --- | --- | --- |
    | STOP_0 | 172 / 179 N (-4 %) | 96 / 81 N (+18 %) | ±18 % |
    | STOP_124 | 198 / 180 N (+10 %) | 86 / 72 N (+18 %) | ±18 % |
    | YAW -17 | 263 / 247 N (+7 %) | 267 / 242 N (+10 %) | ±10 % |
    | YAW +17 | 264 / 243 N (+9 %) | 256 / 247 N (+4 %) | ±9 % |
    | G90 | 38 / 31 N (+24 %) | 30 / 26 N (+15 %) | ±24 % (small forces) |
    | G90 + YAW -17 | 219 / 214 N (+2 %) | 299 / 271 N (+11 %) | ±11 % |
    | G90 + YAW +17 | 294 / 272 N (+8 %) | 221 / 220 N (+1 %) | ±8 % |

  - **For a design value, take the larger of the two.** That is the face total, at most 299 N per lug (G90 + YAW -17, +X lug),
    against the shoulder thread's 304 N design value and 370 N bound.
- **Do not use the "both lugs" net force.**
  - The two lugs push in opposite directions, so their net is the small difference of two large numbers. The face/section
    difference of each lug lands in the net whole.
  - Example: G90 + YAW +17 gives a net Fz of 73.5 N from the faces and 52.7 N from the sections. That is the -X lug's 22 N face
    over-read, not a 40 % uncertainty on the lug loads.
- **The yaw moment the lugs carry:** My 15.1-15.4 N·m from the sections, 16.6-17.0 N·m from the faces, of 17.0 applied. The lugs
  carry 89-100 % of the yaw moment, and for design it can be taken as all of it.
- **The whole-hub section at Y 310:**
  - Its moments balance the applied moments within 2-3 % in every case: Mx 23.3-23.4 against 22.9, My ±17.5-17.6 against ±17.0.
  - Its force components carry about ±37 N of integration error.
    - In the three cases with G90 it reads Fy -32 to -37 N where none is applied. It reads Fz -67 to -68 N against -62 applied.
    - The cause is the G90 bending stress across the hub's coarse 4 mm mesh at Y 310. Those σy values are large and should cancel
      over the section; a few percent left over on the integration grid is that much force.
    - Without G90, Fy is 4-7 N.
  - Use the whole-hub section for moments only, not for forces under ±40 N.

## How the plate force spreads over the lug Z face

- **Zones.** The lumped plate covers X offset 18.96-34.2 × Y 288.2-294.6, with the r 1.7 hole round the bolt. The 1 mm band
  inside its outer outline is about 40 mm², 45 % of the plate's 88 mm².
- **Compressive normal force on the loaded face, by zone (N, % of that face):**

  | Case, loaded face | Total | Within 1 mm of the outline | Within 1 mm of the hole | Rest of the plate | Outside the plate | Centre (X offset, Y); spread 1 sd |
  | --- | --- | --- | --- | --- | --- | --- |
  | STOP_0, -X front | 179 | 88 (49 %) | 10 (5 %) | 69 (39 %) | 13 (7 %) | 30.2, 291.5; 3.4 × 2.0 |
  | STOP_124, -X front | 200 | 106 (53 %) | 16 (8 %) | 65 (33 %) | 13 (6 %) | 28.9, 292.8; 4.3 × 1.6 |
  | YAW -17, -X front | 286 | 153 (54 %) | 6 (2 %) | 105 (37 %) | 22 (8 %) | 31.2, 292.5; 2.8 × 1.8 |
  | YAW +17, +X front | 280 | 149 (53 %) | 6 (2 %) | 103 (37 %) | 22 (8 %) | 31.2, 292.4; 2.8 × 1.8 |
  | G90 + YAW -17, -X front | 242 | 125 (52 %) | 4 (2 %) | 93 (39 %) | 20 (8 %) | 31.7, 291.9; 2.3 × 2.0 |
  | G90 + YAW +17, +X front | 240 | 122 (51 %) | 5 (2 %) | 93 (39 %) | 20 (8 %) | 31.5, 291.8; 2.5 × 2.0 |

- **What that means:**
  - About half the plate force lies within 1 mm of the plate outline, on 45 % of its area: edge-weighted, but only mildly.
  - The centre of pressure sits toward the lug's free end (X offset 29-32 of 19-34), so the outer end of the plate carries most of
    it.
  - The 6-8 % "outside the plate" is the linear interpolation of nodal values across the lumped boss's step edge, so the lumped
    model's step can be read as up to 8 % extra concentrated at the outline.
  - Applying the force evenly over the plate would put the centre at the plate centroid (X offset about 26.6, Y 291.4). That is
    4-5 mm nearer the hub axis than the model, which lowers the lug-root moment.
- **Model limits.** The plate is a 0.5 boss of our part, frictionless against the lug and unclamped, so a real clamped PETG plate
  spreads the force at least as evenly as this. The values are nodal tractions on a 0.8 mm face mesh.
