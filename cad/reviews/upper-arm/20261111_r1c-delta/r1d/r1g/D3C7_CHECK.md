# Hub D3c7 candidate against R1g, the final plates and the 0.70 ring: checks (2026-11-13), PROVISIONAL

**Provisional.** D3c7 is the shoulder thread's local build, not yet pushed. It was copied read-only from
`C:\joe\code\roark-wt\shoulder-study\cad\_wip\shoulder-pass1\stl_look_hubD3c7\hub.STL` to `cad/_wip/shoulder_hub_d3c7_local/`.
These checks hold for the pushed candidate only if its STL SHA-256 equals the one below.

**What D3c7 is.** D3c6 plus Dia 3.8 lug holes, with the cable window at 68 deg (a flat inner wall; footprint at Y 298:
r 15.7-21.0, ±8 across).

**Ours:**
- **Halves:** the R1h halves (`cad/_wip/r1d_r1h_print/exports`): the R1h back half with the tie bridge, and the R1g front half.
  Rerun on 2026-11-13 17:30 (see `R1H_BACK.md`). Every check gives the same result as on the R1g halves: the maxima and minima
  below are unchanged; only the hit and path-collision counts of the sampled closing path move by a few points.
- **Plates:** the final plates (Dia 3.8, Y 288.2-294.6, short lips) at 0.45 and 0.75.
- **Ring:** the 0.70 shim ring on the disc face.

**Method.** Everything ran under the 6 GB cap, with no solve of ours running. The script is
`cad/scripts/fea/r1c/d3c7_check.sh`.

| # | Check | Result | Files |
| --- | --- | --- | --- |
| 1 | STL SHA-256 and watertightness | **PASS**. SHA-256 a73103adb49bb9a4fe3b3901fea852e6668e928e7e1586953bc8b25a0c10259b, the same as the original. Watertight; 63,187 mm³, 80.2 g. | `d3c7_halves_used.txt`, `d3c7_check.json` |
| 2 | Against D3c4: below Y 296, and the arm-facing surfaces | **PASS**. See the notes below the table. | `d3c7_check.json` |
| 3 | Roots against our posts and the plates | **PASS**. See the notes below the table. | `d3c7_plate_fillet_gap.txt` |
| 4 | Closing path of both halves on D3c7 plus the 0.70 ring | **PASS**. Final overlap max 0.041 front / 0.039 back, along the line-to-line ridge flank only (Y 297.97-298.53). That is the same as D3b and D3c4. The 21 / 4 path hits (R1g run: 20 / 18) are all on that flank (Y 298.0-298.5, r 34.9-35.8): faceting of the two line-to-line surfaces (D3c4 had 10 / 15). None at the lugs, roots, pocket, webs or collar. | `close_path_d3c7.json` / `.txt` |
| 5 | The 68 deg window as built, the bundle route, and the shoulder's tie at the 98 deg boss | **PASS**. See the notes below the table. | see the notes |
| 6 | Bore fill at Y 296 and above | **PASS**. Nothing of ours lies inside r 22 at Y 296-298 (0.0 mm² in every section). Between Y 296 and Y 302 our nearest material is the bore at r 35.9 and above (the post tops end at Y 295.7). D3c7 is unchanged from D3c4 on every arm-facing surface. | `d3c7_check.json` |

**Check 2, against D3c4.**
- **Below Y 296:** the only change is material removed at Y 290.2-293.8, X offset 21.1-24.9 (r 21.3-25.4), on both lugs, through
  the lug thickness. That is the lug bolt hole going from Dia 3.4 to Dia 3.8, round (X offset 23, Y 292).
- **Arm-facing surfaces (groove, land, disc face Y 302, spigot, r over 23.5 in Y 296-302.3):** no change, 0 pieces.
- **Above Y 302.3:** 187 changed pieces, all inside the hub (the window rework).

**Check 3, the roots against our posts and plates.**
- **Our halves:** 0.300 at the least, on both lugs and faces. That is the post tops (Y 295.7) under the hub's Y 296 face,
  unchanged.
- **Final plates (0.45 and 0.75), top edge to the R1.2 fillet:** 0.267 on every lug and face. The final top is Y 294.6, 0.2 below
  the fillet's tangent line (D3c4 at the old top Y 294.7: 0.167).

**Check 5, the 68 deg window, the route and the 98 deg tie.**
- **Window footprint against our halves** (r 15.7-21.0, ±8, at theta 68): at the hub end (Y 298-285) the smallest clearance is
  3.23 mm (front half, Y 288). A straight drop below that runs into the waist's front wall, as known
  (`d3c7_window68_footprint.txt` / `.png`).
- **The 3.5 x 13 bundle from the as-built entry** (centre r 17.45 at Y 298, slant starting at Y 298): it moves 23 mm inward along
  the thin axis over 53 mm, with R 24.7 (at least 24), a slope of 0.68 and a twist of -15 deg.
  - The smallest clearance is 5.63 mm, at the hub end (Y 292), to the front +X post corner.
  - The other edges: the waist front wall 6.06, the arm wall 6.02, the waist back wall 11.46.
  - The assembly sweep is 0 (`d3c7_route68_r17.45.json` / `.png`).
- **The shoulder's tie round the 98 deg boss tube, Y 300-304:**
  - The tube is a hub piece at r 7.6-16.4 (theta 77-120) round a Dia 4.3 screw bore at r 12.0, theta 98.
  - The tube region plus 3 mm for the tie band and head is 15.3 mm or more from our nearest part at Y 300-301. Above Y 302
    nothing of ours is in the plane.
  - Nothing of ours is near it (`d3c7_tie_boss98.txt`).
