# Independent review of the R1g packet (head 39154dd): findings and responses (2026-11-13)

**Verdict.** The coupon, hub and shims may print; the halves not yet; the lug-bolt region is not closed.

Each item was checked against the files before any change. "Confirmed" means the reviewer is right. "Partly" means the reviewer
is right but the cause differs.

## B1: the STOP_0 plate-hole edge

### Numbers

**Confirmed.** The packet's hub value 0.72 / 1.21 / 1.88 came from an ad-hoc rim script whose output was printed and never saved.
Its region also differed (1.4-3.0 from the bolt, |Z - CZ| within 1.5 of 5). The packet's arm layer "1.35 or more" and "about
1.9 at 1 mm" were not file-backed either.

Corrected from the saved spot report (`r1g2_stop0.spot_report.txt`, now with full-body sphere averages and every node a
candidate centre):

| Spot | Measure | SF at 0.5 / 1 / 2 mm |
| --- | --- | --- |
| Hub lug face at the plate-hole edge | vm | 0.62 / 1.01 / 1.47 |
| | shear | 0.72 / 0.98 / 1.30 |
| Our post (front, insert side) | shear | 0.33 / 0.76 / 1.66 |
| | vm | 0.35 / 0.79 / 1.71 |
| | across-layer tension | 0.62 / 1.35 / 2.62 |

The across-layer tension sits on 14 nodes at Z 11.6, the insert / PETG interface.

### Load path

**Partly.** Force balance on the -X lug in r1g2_stop0, from the displacements (`fx_path.py`, `r1g2_stop0.fx_path.txt`):

- **Bolt shank to the lug's Dia 3.4 hole:** no contact. The gap closes 0.15 of 0.2 on the -X side. The hole-wall normal stress
  is about 0. The shank's transverse shear is 0 at the lug mid-plane and about ±1 N at the faces. The bolt carries no Fx.
- **Lug outer face (X offset 34.4) to our pocket wall (34.6):** the gap closes 0.125 of 0.2; no contact (σx 0.08 MPa).
- **Plate faces:** the lug slides 0.11-0.15 mm in X relative to our faces, so the faces are not sticking (the dropped shim-body
  runs stuck; these don't).
  - Contact sets: seat and lug are type 0, no penetration; insert and bolt are type 1, bonded. The friction property is not
    set; it was logged IncludeFriction False on every set in the shim runs, which use the same API defaults.
  - Nodal τxz at our face nodes near the hole edge is -3.2 / +2.0 MPa. That is a nodal (extrapolated) value, not a contact
    traction. The whole-face mean is -0.66 / +0.39 MPa.
- **So no contact carries an X force.** The "Fx 86 N" in the post's root-band slab (mean τxy × an assumed section) is not a real
  force. It is a slab-averaging artefact: the nodes in the band are concentrated at the refined faces. The hot spot's apparent
  tracking of "Fx" is coincidental.
- **What the spot is.** The STOP_0 lug presses its plate face unevenly. The pressure peaks at the plate-hole edge (r 2.2), next
  to the brass insert (r 2.0), and loads the insert / PETG interface. It is a bearing-edge case on a lumped boss step (see
  r1g2_stop0 principal stresses: p3 -113 / -28 MPa, p1 +31 / +28 MPa at 0.5 / 1 mm).
- **No model artefact found in contact.** The one modelling effect is the lumped plate's 0.5 step at the hole edge. A separate
  plate on a flat face has no step. A local variant that removes the step would model the plate as a separate body, the very
  thing that stuck in the shim runs, so it is not proposed. B8 is therefore not run.

## M3: averaging centres

**Confirmed.** The method was in `hub_r1c.py` L131-141. All r1g2 cases and R1g YAW -17 were re-run with every node as a centre
(`R1C_ALL_CENTRES=1`; `post_allc.txt` per case).
- The 0.5 mm values never change.
- 1 mm and 2 mm values drop in several regions: the list is in `allc_drops.txt`.
- Two whole-arm rows drop sharply:
  - **r1g2_stop124 whole-arm shear: 0.99 / 1.09 / 1.19 becomes 0.83 / 0.96 / 1.16, at X 139.5, Y 192.0, Z -25.5.** That is the
    elbow stop-lug pad, where the 515 N stop load is applied on a 0.4 mm pad face. It is the load-application patch. The
    released R1 packet listed it the same way: "stop lug pad, within 2 mm: load-application edge", 0.82 / 0.78 at the pad edge,
    excluded from the SF. It is now named in the packet.
  - **r1g2_stop0 whole-arm layer at 2 mm: 7.50 becomes 1.56, at X 153.9, Y 250.2.** That is inside R1's excluded RS02 ring zone,
    the bond artefact of the merged ring; it is a known item from R1.
- vm is reported separately from the signed components (layer is signed tension; shear is a magnitude).

## M1: the hub lug roots under yaw

**Confirmed, different cause.** `hub_r1c`'s lug mask covered the extended lug. The miss was in `yaw_report.py`: its hub lug boxes
stopped at X offset 31.5, short of the D3b outer face at 34.4.

`spot_report.py` also averaged only over the spot's own nodes; it now averages over every body node in the sphere, as hub_r1c
does.

Corrected, at the extended lug's outer root (X offset 34.4, Y 294.9), shear at 0.5 / 1 / 2 mm:

| Run | Shear | Location |
| --- | --- | --- |
| R1g YAW +17 | 1.20 / 1.58 / 2.41 | -X |
| R1g YAW -17 | 1.15 / 1.54 / 2.44 | +X |
| r1g2 YAW +17 | 1.23 / 1.56 / 2.38 | -X |

The packet rows (1.45, 1.41 / 2.26) are corrected. The shoulder thread's FE governs the hub.

## Minor items

- **Torque share.** `plate_bearing.py` counted every 0.5 mm cell holding a node as full, and summed nodal (extrapolated)
  pressures, which over-counts: 20.8-23 N·m against 17. One consistent lug force: 17 N·m over the two lugs at the bearing
  centroid (X offset about 32) gives about 265 N, which agrees with the root-band section reads (258-272 N). Mean plate pressure
  is 265 N / 82 mm² net = 3.2 MPa. The 315-352 N "per face" numbers are dropped from the packet.
- **Stale text.**
  - BENCH 2b: "rev D hub" becomes "the D3b hub", "R1e half" becomes "R1g half", and "R1f, not for printing yet" is removed.
  - Packet: the "D3b check owed" lines and the seam-section title are corrected.
- **Plate lip in the closing path.** **Confirmed missing, and it clashed.**
  - With the lip (Y 287.2-288.0, out to X offset 33.7) and the plate's lower strip (to 34.2), both met our wall below the pocket
    floor (Y 287.2-287.5), by up to 0.30.
  - Fixed in `lug_shim_print.py`: the lip and lower strip now stop at X offset 32.5. The closing path with the lips is clean:
    no hits, seated 0.036 / 0.064 (`close_path_plates_lip.json` / `.txt`).
  - The plate set is **not re-sliced yet** (instructed).
- **Plate ligament above the Dia 4.4 hole.** The hole top is at Y 294.2 and the plate top at 294.6, so the ligament is 0.4: about
  one extrusion at 0.42 line width. The slicer may thin or drop it. Proposal: raise the plate top to Y 294.7, which gives a 0.5
  ligament, still 0.1 below the R1.2 root tangent (Y 294.8). Then check the slice preview for a closed perimeter. The check is in
  `cad/scripts/arm/plate_ligament_check.py` (output `plate_ligament_check.txt`). Not changed yet.
- **Print orientation.** The halves print seam face down (`organic_print.front_down` / `back_down`), so their layers lie in Z
  planes. The scripts' arm layer allowable (22.5) on σz, and the interlayer shear on τxz / τyz, are on the right axes. Stated
  in the packet.

## C: the insert and preload

- **Installation.** The front-post insert hole runs from the lug face into the post (`organic_parts.upper_half`: HUB_INSERTS
  from zl to zl + 6.5). The insert goes in from the lug face. The bolt comes from the back post's counterbore, through the lug
  and the plates, into the insert. **Bolt tension pulls the insert out the way it went in. The reviewer is right.**
- **Backing.**
  - With a Dia 3.6 plate hole, the plate covered the insert rim (r 1.8 against the hole's r 2.0) and backed it against the
    lug.
  - With Dia 4.4 (r 2.2) it does not, if the insert's outer diameter is 4.0.
- **Insert outer diameter.** Not recorded in the repo. `SETTINGS_CHECKLIST.md` names "Ruthex M3 × 5.7" in a Dia 4.0 hole; there
  is no listing or datasheet in the repo. To be measured on the part. If the knurl OD is above 4.4, the Dia 4.4 plate still
  overlaps it.
- **Bolt torque and preload.** 0.5 N·m (BENCH_TESTS) gives about 0.55-0.83 kN at K 0.2-0.3. The FEA has no preload.
- **Pull-out margin.** Not computable from the repo: there is no pull-out rating for this insert in PETG. R1D_NOTES quotes
  "about 1-1.5 kN" without a source. Against 0.55-0.83 kN of preload that is a margin of about 1.2-2.7, before any lug load
  that adds tension (the yaw and stop push one lug face toward the insert post).
- **Least changes, analysis only; nothing is changed yet:**
  1. **Plate hole Dia 3.8** (r 1.9). The plate backs the insert rim (r 1.9-2.0+) and its edge stays 0.2 outside the hub's
     Dia 3.4 rim (r 1.7). Costs: the STOP_0 hub-face edge moves back toward the Dia 3.6 numbers (it was 0.50 / 0.98 at r 1.8).
     A re-run is needed. Ligament above the hole 0.7.
  2. **Insert from the far (outer) side of the post.** Bolt tension then seats the insert into its shoulder. Costs: an access
     hole through the post to the skin (visible outside), a new insert pocket and a re-run of the post FEA; in effect a
     geometry change to the halves.
  3. **Torque cap.** Keep the insert as is and cap the lug-bolt torque at 0.3 N·m (about 0.33-0.5 kN). Costs: less clamp on the
     plates. The yaw is still carried by the plates in bearing, which needs no clamp. No geometry change. Bench pull-out test
     needed.
  - Recommendation: (1) Dia 3.8, re-run STOP_0, plus (3) as the bench torque until a pull-out test is done.

## D: the bench (text proposals)

See BENCH_TESTS 2b (updated):
- (a) a bare-fit step first, with no ring and no plates;
- (b) calipers on every ring and plate before the pick, two full plate sets, and half steps round the pick if cheap;
- (c) the simplest coupon load fixture: a printed lever on the hub, 8.7 kg at 200 mm for 17 N·m of yaw; a side load on the lug;
  play read with a feeler or a dial;
- (d) one pass rule covering the ring, the plates, the twist check and the imprint;
- (e) a 24 h re-torque and play re-check.

## B: the solves

- YAW -17 and G90 + YAW +17 on r1g2: queued (both locks, mesh guard).
- B8 (local STOP_0 variant): not run. A2 found no contact artefact, and the remaining step effect can't be removed without a
  separate plate body, which sticks.
