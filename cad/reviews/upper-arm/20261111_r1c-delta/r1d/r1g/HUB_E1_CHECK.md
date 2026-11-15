# Hub rev E1 against our arm: checks (2026-11-15)

## ADOPTED E1 (roark 8656e20, gate packet c404ab8; checked 2026-11-15). THIS IS THE HUB.

**Print from:** `J:\code\roark\cad\_wip\prints\shoulder\shoulder_hub_left_revE1.3mf` on Joey-PC, or
`C:\joe\code\roark\cad\_wip\prints\shoulder\shoulder_hub_left_revE1.3mf` on holly-pc. SHA-256
c384a067f1f3d5a9532ac16758862e919518f8ac2e4b7a91abf1b6615895fc5a on both. (`C:\joe\prints\shoulder-hub\revE1_final\` holds the
same file. The `staged_revE1_seats5p2_NOT_RELEASED` folder named earlier no longer exists; it became `revE1_final`.)

**Superseded, do not print:** the first E1 (92cf101; 3MF aa4c7dd3…4a81, STL ec8c8a59…74fb4). It is still in
`C:\joe\prints\shoulder-hub\staged_revE1_NOT_RELEASED\` (now with a DO_NOT_PRINT note) and in the
`superseded_revE1_seats6p2_do_not_print` folders. Its screws would go 6.2 mm into motor holes that bottom out at 6.5-7 mm.

| # | Check | Result |
| --- | --- | --- |
| 1 | Released export | `cad/exports/shoulder/shoulder_hub_left.STL` at 8656e20. The real LFS object, smudged and hashed: SHA-256 **638facef4a15a6ed8f9315f58ed556b567e72503f3a60d0bdfcbd1103de0080b**, as claimed. 4,851,484 bytes, one watertight body, 97,028 triangles, 92,304.8 mm³ = 117.2 g. Assembly frame, Y 285.00-319.86. |
| 2 | Same solid as the arm-frame file | Moved 3.00 mm up (+Y) it equals `shoulder_hub_left_revE1.STL` (c38fafc5a0cd8b96c94611bf43df2747bc2db4234d44981c205a30e57edc79e5, Y 288.00-322.86) to **0.00003 mm** both ways, by vertex and surface. All checks below are on that file. |
| 3 | Print file = that solid | The 3MF's part is the same mesh: 97,028 triangles, 48,498 vertices, extents 34.86 × 78.6 × 78.6, volume 92,304.8. The other two objects are the 100 % modifier and the support blocker. |
| 4 | Arm-facing surfaces against D3c7 (a73103ad) | **Identical.** Below Y 296, max 0.0000. D3c7 to E1 on the groove, flanks, land, disc face and spigot: 0.0000. Past r 23.5 only the tunnel mouth (Y 302.04-302.25, r 23.5-23.65, θ 56-81). |
| 5 | Against the first E1 (ec8c8a59), every difference | Only two: **the six head seats**, 1.0 mm further from the motor (the tube ends, Y 298.86-299.86, r 6.6-17.4, up to 1.0), and **the plate underside** made level with the R 4 tube blends (Y 308.17-312.80, r ≤ 23, up to 1.98). Nothing else. |
| 6 | Whole-part survey, every 0.5 mm | No enclosed void under 1.0 mm wide. The only material strip under 1 mm is the groove-flank ring at r 35.8, Y 301.75, which D3c7 has too. |
| 7 | The tunnel | Unchanged against the first E1 (the diff in 5 shows nothing there): 4.5 × 11, the 40 deg knee, the exit at r 23, Y 302.1-309.1. |
| 8 | The M4 heads, now 1.0 mm lower | Head plus washer envelope Ø9, Y 294.06-298.86: our nearest part (halves, the 0.75 plates, the lug-bolt envelopes) is **3.35 mm** away, at Y 294.06, θ 338. Nothing overlaps; the ring, the halves' top (Y 302) and the lug-bolt tool access are outside the bore. |
| 9 | Fit check rerun (`cad/scripts/fea/r1c/e1s_check.sh`, outputs `e1s_*`, `close_path_e1s.*`) | Same as D3c7: roots 0.300, plate top to the R1.2 fillet 0.267, closing path final overlap 0.041 / 0.039 on the flank, nothing of ours inside r 22, window footprint 3.23. |
| 10 | Our route from r 21.5 | Uses our halves only, so its pass (3.64, R 24.7, sweep 0) stands. |
| 11 | Print file | PETG, 0.20, 6 walls, 100 %, no brim, tree hybrid, SuperTack, Bambu P2S 0.4. **RS02 face down** (Ø47 contact, r ≤ 23.65), **lugs up**. The blocker covers z 20.06-36.36: the groove (z 20.86-23.86) and both lugs. Support only in z 0.2-4.6 (the plate side), none in the tunnel, the bore or on any arm-facing face. 3 h 14 min 39 s, 115.84 g. No blockers to printing. |

**Correction to the earlier wording "identical below Y 302":** that holds outside the bore. Inside it, the head seats changed at
Y 298.86-299.86 (check 5). Nothing of ours is in the bore there.

**Verdict: GO. Print from the path above.** Open: Joey's 215 mm rule against the +3.00 mm (below); the URDF +3.00 (software project).

## First E1 final candidate (92cf101). SUPERSEDED, do not print.


**File:** `shoulder_hub_left_revE1_candidate_armframe.STL` at 92cf101 (`claude/project-thread-90ef87`). The real LFS object hashes to
SHA-256 **ec8c8a592d71f1dca96f6f40d940408df3c612e0657353c72f51756744874fb4**, as claimed. 3,170,584 bytes, watertight, one body,
90,676 mm³ = 115.2 g.

**Against D3c7 (a73103ad):**
- Every arm-facing surface is unchanged: below Y 296, max 0.0000; the groove, flanks, land, disc face and spigot, 0.0000 from
  D3c7 to final.
- The only change past r 23.5 is still the tunnel mouth (Y 302.0-302.3, r 23.0-23.8, θ 57-79).

**Against the first E1 candidate (c7231b1), every difference.** 200,000 samples each way. Exactly the two claimed changes, nothing
else:
1. **The tunnel exit's top edge cut square:** Y 308.4-310.6, r 23.0-24.8, θ 54-82, up to 1.76. The feather edge is gone.
2. **The six screw-hole edges on the RS02 seat face squared:** Y 322.37-322.86, r 9.4-14.6, all round, up to 0.35.

**Whole-part survey, every 0.5 mm:**
- No enclosed void under 1.0 mm wide.
- The only material strip under 1 mm is the groove-flank ring at r 35.8, Y 301.75, which D3c7 has too. **The feather edge at the
  tunnel exit is gone.**

**Fit check rerun** (`cad/scripts/fea/r1c/e1f_check.sh`, outputs `e1f_*`, `close_path_e1f.*`): the same as D3c7 and c7231b1.
- Roots against our posts 0.300; plate top to the R1.2 fillet 0.267.
- Closing path on final E1 plus the 0.70 ring: final overlap 0.041 / 0.039, on the flank only.
- Nothing of ours inside r 22.
- Window footprint at the hub end 3.23; the 98 deg boss region and our nearest part unchanged.
- **The M4 heads:** the head seats inside the hub didn't change (the changes are on the top face), so the 4.91 clearance stands.
- **The route** from r 21.5 uses our halves only, so its pass (3.64, R 24.7, sweep 0) stands.

**Verdict: GO for the arm interface.** The open item is unchanged: the arm sits 3.00 mm lower, and Joey's 215 mm rule decides it
(below).

## First E1 candidate (c7231b1), the earlier check

**What was checked.** The shoulder study's E1 candidate, roark commit c7231b1 on branch `claude/project-thread-90ef87`, file
`cad/exports/shoulder/shoulder_hub_left_revE1_candidate_armframe.STL`. It is in our present arm coordinates, Y 288.00-322.86.
The baseline is D3c7 (a73103ad…259b).

None of the claims were trusted. Everything here comes from the file, with the scripts named. Exploration copies are in
`cad/_wip/shoulder_hub_e1_c7231b1/` (gitignored).

| # | Check | Result |
| --- | --- | --- |
| 1 | Hash and file | **PASS.** Fetched without checkout, and the real LFS object was smudged and hashed: SHA-256 c004bc2d1c2778f436f5f07df96224bbefb1ec2b58903fb2a1335f90d64e452a, the same as claimed. Binary STL, 3,242,484 bytes, watertight, **one body**, 90,680 mm³ = 115.2 g in PETG. |
| 2 | Arm-facing surfaces against D3c7 | **Identical.** See the surface diff below the table. |
| 3 | Whole-part survey | **No slits, no loose bodies.** One thing to look at: a feather edge at the top of the tunnel exit. See below the table. |
| 4 | The tunnel as built | **As confirmed.** See below the table. |
| 5 | The M4 heads | **Clear.** Six bores at r 12 on θ 38 + 60k: four Dia 4.3 and two Dia 3.8, the reamed pair at 38 and 218. A head-plus-washer envelope (Dia 9, Y 295.06-299.86) stays **4.91 mm** or more from our halves; nothing of ours is inside r 17 at Y 295.5. |
| 6 | D3c7-style fit check rerun on E1 (`cad/scripts/fea/r1c/e1_check.sh`; outputs `e1_*`, `close_path_e1.*`) | **Same as D3c7.** See below the table. |
| 7 | Our cable route from r 21.5 (θ 68) | **PASS** (`cad/_wip/route_r21.5/`): 3.64 smallest clearance, R 24.7, slope 0.68, assembly sweep 0. See below the table. |

**Check 2, the surface diff.** Both directions, 150,000 surface samples each, distance to the other mesh.
- **Unchanged:**
  - Below Y 296 (the lugs, the Dia 3.8 lug holes, the R1.2 roots): max 0.0000.
  - At Y 296-302.3, r > 23.5 (groove and both flanks, the land, the disc face where our end face seats, the spigot): max 0.0000
    from D3c7 to E1.
- **The first difference reaching beyond r 23.5 is the tunnel's mouth in the bore wall.** It runs Y 301.98-302.59, r 23.0-24.0,
  θ 54-82, up to 0.32 off: the 11-wide exit with its R 1.5 edges. It starts 0.12 below the claimed Y 302.1, from the edge round.
  Our nearest surface there is the seat bore at r 35.9.
- **Inside the bore (r ≤ 23.5) the changes start at Y 298.06:** the tube bottoms (Dia 10.8 now) and the head seats at Y 299.86.
- **Nothing of ours is below Y 302.6 anywhere these changes are.**

**Check 3, the whole-part survey.** Sections every 0.5 mm, Y 288.25-322.75.
- **No enclosed void narrower than 1.0 mm.** No slit like D3c7's.
- Material narrower than 1 mm (over 1 mm²) appears in only two places:
  - A ring at r 35.8, Y 301.75: the section grazing the groove's sloped flank. D3c7 has it too, so it isn't new.
  - **New:** a feather edge of bore wall at the top of the tunnel exit, Y 309.25-310.25, r 23.0-24.0, θ 54-82, under 1 mm thick
    and about 1.7-5.6 mm² per section. It may print ragged. It is above the bundle's path (the bundle leaves over the exit's lower
    edge and hangs down), so it is a print-quality note for the shoulder study, not a fit issue.

**Check 4, the tunnel as built.** The section through θ 68:
- A vertical leg 4.5 radial (r 27.0-31.5) from the dish floor at Y 318.5 (mouth rounded, Y 317-318.5) down to about Y 314.5.
- The knee at Y 313-314.5, inner corner rounded about R 2.
- A slant at 40 deg from the axis (dr/dY 0.84), 4.5 wide square to itself.
- The exit through the bore wall at r 23, Y 302.1-309.0.
- About 11 tangential, measured as 11.8-12.1 across the rounds.
- The centre plate's underside, at about Y 312.5 there, is 3.4 above the top of the exit.

**Check 6, the fit check.**
- Roots against our posts 0.300, all four.
- Plate top to the R1.2 fillet 0.267 (0.45 and 0.75 plates).
- The closing path on E1 plus the 0.70 ring: final overlap 0.041 / 0.039, on the ridge flank only.
- Nothing of ours inside r 22 (bore fill 0.0).
- Window footprint at the hub end, Y 298-285: 3.23.
- The 98 deg boss region now reaches r 6.6 (it was 7.6) with the thicker tube; our nearest part is unchanged at 1.73 / 3.03 at Y 300 / 301.

**Check 7, the cable route.** That route uses our halves, not the hub. In E1's bore at θ 68 the space is free from r 14 to 23
between Y 298 and 302, so the flat 2.6 bundle hangs at r 20.2-22.8 with room.

## The arm sitting 3.00 mm lower on the yaw axis

- **The offsets check out** (D3c7 Y 319.86 to E1 Y 322.86 at the RS02 face):
  - RS02 output face to our disc face: 17.86 to 20.86.
  - To the spigot underside (Y 296): 23.86 to 26.86.
  - To the lug-bolt axis (Y 292): 27.86 to 30.86.
- **Joey's length rule: decision needed.** `upper_arm_requirements.md` says "Length 215 mm shoulder to elbow, a skeleton variable.
  Don't lengthen it (Joey 2026-11-06: the built right arm already feels long)."
  - E1 puts the elbow 3.00 mm further from the shoulder: RS02 face to elbow axis goes from 110.0 to 113.0 in our frame. That makes
    the arm 218 instead of 215, unless the shoulder takes the 3 mm back above the RS02.
  - This is Joey's to accept, or for the shoulder study to recover.
  - The URDF and the kinematics belong to the software project. They need the +3.00 on the upper-arm link if E1 is adopted.
  - Our `config/skeleton.yaml` holds joint limits only, no lengths.
- **Fork skirt:** we have no skirt geometry. If the shoulder study lengthens the skirt by exactly 3.00, the gap to our arm's top
  is unchanged; they should confirm it in their assembly.
- **Our constants that hold the old top face**, to change only if E1 is adopted, together with any rerun:
  - `HUB_Y = 319.86` in `cad/scripts/arm/organic_master.py`;
  - `HUB_TOP = 319.86` in `cad/scripts/fea/hub_seat.py` (the hub-seat FE's fixed face);
  - the packet's "hub fixed at its top face (Y 319.86)" and the D3c7 notes (Y 316-319.86 for the slits), which are records.
- **Does the arm FE need rerunning on E1? Not for our parts.**
  - Every surface the arm touches is identical, and the loads are applied in our frame.
  - Our FE hub is the solid D3b-shaped FEA hub (it never had the slits), fixed at its top face.
  - E1's 3 mm taller, solid centre moves the fixed face up and stiffens the hub, which changes our lug-to-groove load share only
    slightly.
  - The hub's own figures (the lug roots, the plate) are the shoulder study's FE, and they govern.
  - A rerun would only be worth it if the shoulder study's E1 hub FE showed a different lug load split. It would be a geometry
    change in hub_seat (HUB_TOP 322.86, the E1 hub body), not a new mesh study.

## Verdict on the first candidate (superseded)

**GO for the arm interface.** It is identical to D3c7 on every arm-facing surface. There are no slits or loose bodies, the tunnel
is as confirmed, the heads clear by 4.91, and the fit checks and the route pass.

**Open, before adoption:**
1. **Joey's 215 mm rule against the +3.00 mm.**
2. **The feather edge** at the top of the tunnel exit (print quality, the shoulder study's call).
3. **The skirt gap**, to be confirmed by the shoulder study.
4. **The URDF** gets +3.00 if E1 is adopted (software project).
