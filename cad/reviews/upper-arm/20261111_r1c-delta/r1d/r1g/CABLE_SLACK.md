# Hub harness at the 68 deg window: sliding stretch, slack loop and anchor (2026-11-13)

**Setup.**
- **Bundle:** the reserve is 3.5 x 13 laid flat; the real bundle is 3.0 x 8 to 3.0 x 12.
- **Bending:** at least R 24, across the thin direction only. No edgewise bends; a twist of at most 90 deg per 50 mm.
- **Window:** theta 68 deg. Theta is ours and the hub's: 0 = +X lug, positive toward +Z (the front half). The bundle's inner face
  is at r 17.2 and its centre at r 18.95 at Y 298. The slant starts at Y 298.
- **Geometry:** the R1g halves, plus the RS02 mounting ring and the vendor RS02 as placed (`rs02_fit.py`). Sections every 1 mm,
  with holes filled.
- **Script:** `cad/scripts/fea/r1c/cable_slack.py`; results in `cable_slack.json`.
- **Pictures:** `cable_route_68_r18.9.png` and `cable_slack.png`.

## Route from the new entry, Y 298 to 245

**PASS.**
- **Shape:** the centre moves 17 mm inward along the thin axis over 45 mm of drop. That is R 24.1 at each bend of the S, with a
  steepest slope of 0.59 mm/mm and no twist.
- **Clearance:** 5.06 mm at least, at the hub end (Y 292) to the front +X post's outer corner.
- **Assembly sweep:** 0 mm². The front half closes last without passing through the bundle.
- **Largest entry radius:** our halves don't limit it. Every centre radius from 15 to 21.5 passes with 3.6 mm or more at R 24 or
  more (`2_entry_scan`). The limit is the hub's own bore (r 23): the inner face at r 19.5 puts the outer face at r 23.0.

## Edges along the sliding stretch, 3.5 x 13 bundle

| Edge | Clearance | Where | Shape |
| --- | --- | --- | --- |
| Front +X hub post, outer corner | 5.06 | Y 292, X 189.0, Z 22.1 | 90 deg square printed corner (a sharp edge, but 5 mm away) |
| Waist front wall | 5.08 | Y 272, X 168.3, Z 22.9 | smooth (178 deg) |
| Seam posts at Y 272 (Dia 7.5) and fins | over 5.1 | Y 268-276 | not the nearest anywhere |

No edge is within 5 mm of the bundle on this route, so no radius is needed in the halves for it.

## Slack loop below the waist

**FAIL: 0 mm available against the 100 mm needed.**
- **Below about Y 251 there is no open cavity.** It is the elbow drum (axis along X at Y 209.86, inner r 41.5), and the RS02 and
  its ring fill it. The free radial gap around the motor is 0.25-2.25 mm (X 155-190); at X 145-150 there is none, because of the
  rib and the end wall.
- **No U-loop fits.** An R 24 rolling loop needs 51.5 x 13 in plan (2R + t). No such rectangle is clear over even 1 mm of height
  anywhere from Y 256 down to 165, at any loop-plane angle (0-165 deg) or offset.
- **None fits above the waist either.** The tube narrows to 47 mm in Z and 49 mm in X at Y 260-272, which is under 51.5.
- **The arm cannot store the 100 mm yaw travel.** It has to be taken up above the hub (shoulder side). Otherwise the halves would
  need a cable bay, which is a change to the halves (not made).

## Where the bundle goes below the waist, and the anchor

- **The harness path runs down the drum's -X end (cad/upper-arm/README.md):**
  1. the neck opening at the drum top (X 145-156);
  2. the rib gap (phi ±15 deg, X 144.5-153.9, 9.4 x 19.7 at r 37.7);
  3. down between the drum end wall and the RS02's back (7.8 wide);
  4. into the hollow stub (Dia 32), then on to the elbow cap coil.
- **No anchor exists.** The upper arm has no clip, tie point or strain relief anywhere. The rib gap and the neck opening guide the
  bundle but do not hold it. Sliding into the arm with nothing holding it, the bundle would be pushed down toward the rib gap and
  the stub.
- **The route from the 68 deg window to the rib gap.** The window centre (X 177.6, Z 23.6) is 33.4 mm sideways from the rib gap
  (X 149.2, Z 6.0), over a 50.4 mm drop (Y 298 to 247.6). Both ends run along Y, so the path is an S-curve, and that S needs about
  R 15 (FAIL against R 24). An R 24 S-curve would need 63 mm of drop. The bundle also has to twist about 68 deg (its thin side from
  radial at 68 deg to along X at the rib gap), which is within 90 deg per 50 mm.
- **Other window angles, for reference** (S-curve R to the rib gap):

  | Window | R |
  | --- | --- |
  | 98 deg | 19.5 |
  | 116 deg | 24.1 |
  | 124 deg | 27.1 |
  | 140 deg | 37.0 |

  Angles over about 127 deg run the 13-wide bundle at r 19 into the front -X post (147-165 deg) at the hub end; this is not
  checked in full yet.
