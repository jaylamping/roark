# Hub D3c4 candidate against r1g4: checks (2026-11-13)

**Source.** Shoulder thread, commit a1057a9 on `claude/project-thread-90ef87`, read-only:
`cad/exports/shoulder/shoulder_hub_left_revD3c4_candidate.STL` / `.STEP`, copied to `cad/_wip/shoulder_hub_d3c4_a1057a9/`. It
replaces D3b (6b2fd93, `D3B_CHECK.md`).

**Ours.** The R1g print halves (`cad/_wip/r1d_r1g_print/exports`), unchanged in r1g4. The r1g4 lug plates have a Dia 3.8 hole,
the top at Y 294.7 and the short lip (to X offset 32.5), at 0.45 and at 0.75 (`plates_close_stl.py`). The ring is the 0.70 shim
ring on the disc face.

**Method.** Everything ran under the 6 GB cap.
- Y-plane sections every 0.1 (`d3c4_check.py`).
- X-plane sections every 0.1 over the plates (`plate_fillet_gap.py`).
- Surface sampling against the hub surface, signed by the closest face (`root_clearance.py`).
- The closing path (`close_path_r1c.py`).

**Theta.** atan2(Z - CZ, X - HX): 0 = +X lug, positive toward +Z (the front half). This is the hub's convention too: D3b's old
window measured -24 to +40 deg, centre +8.

| # | Check | Result | Files |
| --- | --- | --- | --- |
| 1 | STL SHA-256 and watertightness | **PASS**. SHA-256 5b919048fcd16d2bcbe1205692b1f6b713065afa756cdfb93bbb8e12977a44cc, as stated. Watertight; 63,144 mm³, 80.2 g at 1.27 g/cm³. | `d3c4_check.json` |
| 2 | D3b against D3c4 | **PASS**. See the notes below the table. | `d3c4_check.json` (`2_diff_pieces`) |
| 3 | The new roots against our posts, plates and post tops | **PASS**. See the notes below the table. | `d3c4_plate_fillet_gap.txt`, `d3c4_root_clearance.txt` |
| 4 | Closing path of both halves on the real D3c4 plus the 0.70 ring | **PASS**. Final overlap max 0.041 front / 0.038 back, along the line-to-line ridge flank only (Y 297.97-298.53, r 34.84-35.78). That matches D3b (0.041 / 0.039). Path hits: 10 front / 15 back, all on that flank (Y 298.08-298.52, r 34.85-35.61), 0.06-0.16 before seated. That is faceting of the two line-to-line surfaces, as on D3b (8 / 7). None at the lugs, roots, pocket, webs or collar. The plates and lips against the halves are unchanged from r1g4 (`close_path_plates_r1g4`): no hits, seated 0.036 / 0.064. | `close_path_d3c4.json` / `.txt` |
| 5 | The cable window at 248 deg | **PASS**. See the notes below the table. | `d3c4_check.json` (`5`), `cable_footprint_check.*` |
| 6 | The r 20 bore fill at Y 296 and above | **PASS**. Nothing of ours lies inside r 22 at Y 296-298 (0.0 mm² in every section). The hub material inside r 23.5 is 11.2 mm or more from our halves (nearest at Y 299.1, our bore). | `d3c4_check.json` (`6`), `d3c4_borefill_gap.txt` |

**Check 2, D3b against D3c4.**
- **Below Y 296:** the only change is material added on the lug Z faces at Y 295.0-295.9. It sits mainly at X offset 19.2-22.5,
  r 20-23. That is the R1.2 Z roots running further inboard, to X offset 19.17 at Y 295.9. The few longer strips are under 0.02 mm
  thick, which is faceting.
- **Arm-facing surfaces (groove, land, disc face Y 302, spigot):** no change. That is 0 difference pieces at r over 23.5 in
  Y 296-302.3.
- **Lug outer faces, R0.8 roots and lug holes:** unchanged.
- **The 254 changed pieces above Y 302.3:** these are the window and the bore fill inside the hub. They don't face the arm.

**Check 3, the new roots against our parts.**
- **Our halves:** the minimum is 0.300 mm, front and back, for D3b and D3c4 alike. It is the post tops (Y 295.7) under the hub's
  Y 296 face. The longer roots don't come nearer.
- **Plates (0.45 and 0.75), plate top edge to the fillet:** 0.167 mm on every lug and face, for D3b and D3c4 alike. The plate top
  (Y 294.7) is 0.10 below the line where the R1.2 fillet leaves the lug face (Y 294.8).
- **The 0.22 mm question:** this is not a D3c4 change. It comes from our plate top moving to Y 294.7.
  - A plate printed 0.1 tall in Y reaches the tangent line, where the fillet has not yet lifted.
  - A plate printed 0.2 tall would ride about 0.01 up the fillet. A plate printed 0.3 tall would ride about 0.04 up it, lifting the
    plate's top edge off the face by that much.
  - **Recommendation: a small edge break on the plate's lug-side top edge.** Inset the last two printed layers (the lug-contact
    face prints on top, with the lip) by 0.3 along the Y 294.7 edge. That gives 0.4 of margin at the face, for 0.2 off the top of
    the plate. It is not applied: the re-slice waits for the r1g4 results.
  - The alternative is to put the top back to Y 294.6, which gives 0.2 of margin and a 0.7 strip above the Dia 3.8 hole.

**Check 5, the cable window at 248 deg.**
- **The as-built slot:** its centre line runs from r 15.5, Y 298 to r 31, Y 320.4, 9 radial and ±8 across. Our nearest section is
  11.6 mm away, with no overlap. Nothing of ours is above Y 302 except the collar, at r 35.9 and outward.
- **Straight drop below Y 298:** the footprint at 248, r 15.5-19, clears our back half down to Y 240. The smallest clearance is
  0.46 mm at ±8 and 3.70 mm at ±4.5, at Y 272 by the back -X fin end.
- **The old window at about 8 deg is closed.** D3b had trimmed the two spokes either side of 8 deg. In D3c4 they are full again, so
  8 deg is now an ordinary 40 deg gap between spokes, like the other four. The r 20 bore fill covers 324-40 deg at Y 296-300.
- **Nothing of ours relies on the old window.** The upper arm has no clip, guide or channel between the hub and Y 245. Its only
  harness features are at the elbow end.

**FEA.** Our FEA hub is not changed. The shoulder thread's FE governs the hub. Our r1g2 and r1g4 runs use the D3b-shaped FEA hub;
D3c4 differs from it only inside r 23 and above Y 296, plus the inboard root extension.
