# Upper arm R1g (ring + printed shim + yaw torque through extended lugs): delta review packet (2026-11-12/13)

Branch `left-arm-organic-r1`.

Pinned commit: 367106fbe75957edcd3c86ecbc6862146f772118 (R1g final results, geometry and print files). Nothing here is
released.

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

## R1g: yaw torque through the hub's extended lugs (2026-11-13, WIP)

**Why.** The full-ring groove and ridge carry no torque about the hub (yaw) axis. All of the RS02's yaw torque (17 N·m peak,
routine) therefore passes through the two lugs as a Z couple.
- On rev D the lugs took 312-334 N each.
- YAW_17 failed: our loaded post about 0.95-0.99 at 0.5 mm, hub lug roots 0.92-0.99, insert 1.27.
- Rev D also had about ±0.22° (±1.1 mm at the wrist) of free yaw play in the 0.1 lug slots.

**Fix, agreed with the shoulder thread.**
- **Hub (shoulder thread, rev D3b; candidate 6b2fd93, checked in D3B_CHECK):** each lug grows out to one straight outer face at X offset 34.4,
  over Y 288-296. It keeps the R1.2 Z roots and adds an R0.8 outward root (0.2 clearance to our wall). No step or column.
- **Our side, R1g:**
  - A shallow seam pocket at X offset 34.6 for the whole lug height, up to our floor. No cut into the collar, the ridge
    stays whole, and the wall to the skin is 1.7 or more.
  - Post-to-wall webs, so the lug bears on one face from r 18.5 out to the wall.
  - The lug slot at 0.5 per side.
  - A root relief for the R1.2 out to X offset 35.2.
- **Lug plates** for zero yaw play: flat printed PETG plates on each lug Z face, main flat face only (X offset 18.96-34.2 ×
  Y 288.2-294.6), with a Dia 4.4 bolt hole and a lip under the lug's free end.
  - 0.25-0.75 in 0.05 steps, two of each; picked after the ring (BENCH_TESTS 2b).
  - The lug bolt clamp pinches the last step shut.
  - Plates A / B take 14 min each, under 1 g.

**Checks so far.**
- **Halves:** mesh gate PASS. Back 5 h 29 / 124.6 g, front 4 h 49 / 108.2 g.
- **Closing path:** against our straight-lug FEA hub plus the 0.70 ring. Final overlap max 0.038, along the line-to-line
  flank only. Path hits are 0.05-0.18, flank faceting only. Against the D3b STL (6b2fd93) and against the lug plates with
  their lips: PASS (D3B_CHECK 4 and 4b; the lips were shortened to X offset 32.5 after they clashed, not yet re-sliced).
- **FEA model:** global 4.0, 0.8 on the lug bearing faces, 1.0 on posts / lugs / fins, about 390 k nodes.
  - Plates lumped as a 0.5 boss of our part inside the plate outline only, frictionless no-penetration to the lug.
  - The shim lumped into the end face, as before.

**Results**, SF at 0.5 / 1 / 2 mm (targets: 1.5 for yaw and G90, 1.2 for the stops):

| Case | Posts / webs (lowest) | Hub lugs (lowest) | Plate bearing | Inserts / bolts | Below target |
| --- | --- | --- | --- | --- | --- |
| YAW +17 | shear 2.74, vm 3.11 | extended lug outer root (X offset 34.4, Y 294.9): shear 1.20 / 1.58 / 2.41 (corrected, review M1); layer 1.40 or more | about 265 N per lug; mean 3.2 MPa; 1 mm 26; peak 55 at the outline corner | SF 7.2 / 11.8 | only model edges: the lumped-plate boss corner (0.84 / 1.54 / 2.88) and the lumped-shim end-face corner (0.98 / 1.89) |
| YAW -17 | shear 3.19, vm 3.44 | extended lug outer root: shear 1.15 / 1.54 / 2.44 (corrected, review M1); layer 1.40 or more | about 265 N per lug; mean 3.2 MPa; 1 mm 28; peak 54 | SF 7.1 / 10.7 | the same model edges |
| STOP_0, Dia 3.6 plate hole (superseded) | layer 1.35 / 2.83, shear 1.81 | the plate-hole rim (hub, -X lug): shear 0.50 / 0.98 / 2.79 | - | SF 4.0 / 35 | **the plate-hole rim** (see the Dia 4.4 rows); lug root layer 1.15 / 2.05 / 4.68 at X 148.6, Y 294.2 (by the rim) |
| STOP_124, Dia 3.6 plate hole (superseded) | 2.5 or more | the plate-hole rim (hub, +X lug): shear 1.06 / 2.07 / 6.27; groove bottom layer 1.54 | - | SF 6.9 / 11 | **the plate-hole rim** (see the Dia 4.4 rows) |
| **STOP_0, final (r1g2, Dia 4.4)** | post at the hole edge: shear 0.33 / 0.76 / 1.66, across-layer tension 0.62 / 1.35 / 2.62 (known item below) | hub face at the hole rim: vm 0.62 / 1.01 / 1.47, shear 0.72 / 0.98 / 1.30 (spot report); lug roots layer 1.97 / 2.85 / 4.69; R1.2 root inner end (-X) shear 2.99 / 3.18 / 4.95 | - | 22 MPa (SF 10.7) / 18 MPa | **the plate-hole edge: known item** |
| **STOP_124, final (r1g2, Dia 4.4)** | 2.1 or more (hole edge shear 2.13) | hole edge 7.5 or more; lug roots layer 2.66, shear 2.40; groove bottom layer 1.53 / 1.87 / 2.23; R1.2 root inner end 3.37 or more | - | SF 7.4 / 11.5 | none |
| **G90, final (r1g2)** | -X front post at the plate-hole edge: shear 1.12 / 3.08 / 10.6 (7 nodes at 0.5 mm), vm 1.20 / 3.31; otherwise layer 2.31 or more | hub lugs vm 2.22 / 4.18; groove bottom layer 2.44 / 2.98 / 3.95 | lug forces about 40 N; ring bearing mean 0.74 MPa, 30 deg sector 3.2 MPa, peak 7.3 MPa (SF 6 or more against 45) | 10 / 13 MPa | **the plate-hole edge at 0.5 mm only** (3.08 at 1 mm) |
| **YAW +17, final (r1g2, Dia 4.4)** | posts and webs 2.32 or more; plate-hole edge 2.32 / 3.00 / 4.72 | hub lug face at the hole 5.35 or more; R1.2 root inner end 3.08 or more (ours; the shoulder thread's FE governs, 1.54 / 1.27); **hub lug root at the lug's outer face by the plate edge (X offset 34.4, Y 294.9): shear 1.23 / 1.56 / 2.38 (full-body sphere averages, review M1)** | about 265 N per lug; mean 3.2 MPa; 1 mm 22; peak 32 | SF 7.6 / 12.5 | hub root by the plate edge (the shoulder thread's FE governs); model edges: the lumped-plate outline corner (1.15 / 1.58 / 2.09) and the lumped-shim end-face corner (0.96 / 2.06) |

**Torque share.** All of the yaw torque passes hub to arm through the plate faces. The lug bolts run along Z through the lug
and can't carry a Z force from it; they only tie our two posts. The pads carry under 1 N. Bolt preload adds no strength; it
closes the last pick step for zero play.

**One lug force.** 17 N·m over the two lugs at the bearing centroid (X offset about 32) is about 265 N per lug, which agrees
with the root-band section reads (258-272 N). Mean plate pressure 265 N / 82 mm² net = 3.2 MPa. The earlier 315-352 N "per
face" figures summed nodal (extrapolated) pressures over whole 0.5 mm cells and over-counted; they are withdrawn.

**Print orientation.** The halves print seam face down, so their layers lie in Z planes: the arm layer allowable (22.5) is
applied to σz and the interlayer shear to τxz / τyz.

**Review of 39154dd (2026-11-13):** findings and responses in `../20261111_r1c-delta/r1d/r1g/REVIEW_R1G_FINDINGS.md`. With
every node a candidate averaging centre (`allc_drops.txt`) the 0.5 mm values are unchanged; two whole-arm rows drop at 1 / 2 mm,
both in zones R1 excluded: STOP_124 shear 0.83 / 0.96 / 1.16 at the elbow stop-lug pad (X 139.5, Y 192.0, the load-application
patch; R1 listed 0.82 / 0.78 there) and STOP_0 layer 1.56 at 2 mm at X 153.9, Y 250.2 (the RS02 ring bond zone).

**Plate hole.** In the stops, the plate's Dia 3.6 hole edge sat 0.1 outside the hub lug's Dia 3.4 hole rim, so two sharp
edges pressed together. Dia 4.4 moves the plate edge 0.5 out onto flat lug face. It sits 0.2 outside our insert's Dia 4.0,
so the inserts must be flush (bench step).

**Lug bolts and inserts (review C, 2026-11-13).** The front-post insert goes in from the lug face, so the lug bolt's tension
pulls it out the way it went in.
- **r1g4 (decided):** plate hole Dia 3.8, top Y 294.7. The plate hole is smaller than the insert's Dia 4.0 hole, so the plate sits
  on the insert's rim and holds it captive (insert, plate, lug, plate, back post, bolt head). The strip above the hole is 0.8.
  Halves unchanged.
- **The insert's outer diameter and pull-out rating have no source in the repo.** Only "Ruthex M3 × 5.7" in a Dia 4.0 hole
  is recorded (`cad/prints/upper-arm/SETTINGS_CHECKLIST.md`). The "about 1-1.5 kN" in R1D_NOTES has no source either.
- **Lug-bolt torque capped at 0.3 N·m** (about 0.33-0.5 kN preload at K 0.2-0.3) until the coupon's insert check (BENCH_TESTS 2b
  step 4b: 0.3 / 0.5 / 0.7 N·m with plates in, insert movement recorded). The seam screws stay at 0.5 N·m.

**Known item, not a pass: the STOP_0 plate-hole edge (r1g2, plate hole Dia 4.4, final).** The reviewer judges it.
- **Where.** STOP_0 is the backup stop load. The -X lug's plate faces carry Fz 173 N (the "Fx 86 N" read earlier was a slab-average artefact: no contact carries X, review A2), and the twist of the lug puts the
  peak around its bolt, at the edge of the plate's Dia 4.4 hole.
- **Our post, front face (X 149.7, Y 292.0):**
  - SF at 0.5 / 1 / 2 mm: shear 0.33 / 0.76 / 1.66, vm 0.35 / 0.79 / 1.71.
  - The node sits on the lumped plate boss's 0.5 step corner (r 2.20 from the bolt axis, \|Z - CZ\| 5.000), 0.2 outside the
    brass insert's Dia 4.0.
  - Principal stresses averaged at 0.5 / 1 / 2 mm (MPa): p1 +31 / +28 / +12, p3 -113 / -28 / -8. Face-normal σz +13 / +12 / +3
    (across our layers, sphere averages: SF 0.62 / 1.35 / 2.62, 14 nodes at Z 11.6, the insert / PETG interface).
  - Reading: the 0.5 mm peak is compressive bearing at a contact edge. At 1 mm a tension of about 28 MPa remains in the corner of
    the lumped step. A real separate plate on a flat face has no step, so the 1 mm value is partly a lumping effect, but not
    entirely.
- **Hub lug face at its own Dia 3.4 bolt-hole rim (X 149.2, Y 291.6):**
  - SF (spot report): vm 0.62 / 1.01 / 1.47, shear 0.72 / 0.98 / 1.30.
  - Contact pressure 10.8 / 5.6 / 1.5 MPa; p3 -42 / -21 / -9 MPa; p1 +9 / +14 / +8 MPa.
  - Reading: compressive bearing at a contact edge.
- **Elsewhere:**
  - The 1 mm values are below 1.2; the 2 mm values are 1.66 (ours) and 1.30 (hub).
  - STOP_124 is clean at Dia 4.4 (hole edge 2.1 or more ours, 7.5 or more hub).
  - The yaw cases don't load this edge (3.3 or more).
- **Bench.** BENCH_TESTS 2b step 8: after the stop-load test, take the plates out and inspect the post faces and lug faces around
  each bolt for an imprint of the plate hole edge. Record its depth by feel, and photograph it.
- **Tried and dropped:** a Dia 6.0 plate hole (r1g3). It cuts through the plate's top edge (the bolt is 2.6 below it) and leaves
  horns, and our side got worse (shear 0.41 at 1 mm). A U-slot was not adopted either: the peak is at the side of the hole
  (Y 292.0), which a U-slot would not move.

**Hub D3b candidate (shoulder thread, 6b2fd93; STL SHA-256 b221df3d...ec80e) against R1g: all checks PASS**
(`../20261111_r1c-delta/r1d/r1g/D3B_CHECK.md`).
- Only the lugs differ from rev D, plus a local square spigot corner.
- The lug sits 0.200 inside our pocket, with 0.486 / 0.514 on the Z faces for the plates.
- Its roots clear our relief by 0.69 or more, and the square corner clears our collar by 0.022, the existing bore clearance.
- The closing path with the ring and plates is clean: the only overlap is the line-to-line ridge flank, 0.041.
- The groove, disc corner and disc face are unchanged.

**Hub under yaw: the shoulder thread's FE governs** (A_HUB_LUGS.md on `claude/project-thread-90ef87`).
- Its governing spot is the inner end of the R1.2 Z root at the r 23 bore wall: shear SF 1.54 at 304 N and 1.27 at 370 N
  (0.5 mm).
- Our FEA hub matches there in geometry: the root sections agree within 0.66 mm² and the bore is identical. But ours has no
  cable slot at the +X lug, and our mesh is too coarse there (1-6 nodes in a 0.5 mm sphere). Our values (shear 2.9 or more)
  are therefore optimistic and not used for the hub.

**Prints (not released):** in `cad/prints/upper-arm/`, all mesh-gated.
- Halves: `upper_arm_organic_{back,front}_r1g.3mf/.gcode` (5 h 29 / 124.6 g, 4 h 49 / 108.2 g).
- Hub-end coupon, cut at Y 284: `..._r1g_coupon` (72 min / 18.2 g, 67 min / 17.0 g).
- Shim ring set: `upper_arm_organic_shim_rings_{A,B,C}_r1g` (0.30-1.10 by 0.05).
- Lug plate set: `upper_arm_organic_lug_plates_{A,B}_r1g` (0.25-0.75 by 0.05, Dia 4.4 hole, about 14 min each).

Sheets: `r1g_back_half_sheet.png`, `r1g_front_half_sheet.png`, `r1g_shim_ring_set_sheet.png`, `r1g_lug_plate_set_sheet.png`,
`r1g_seam_section.png`.

**Open:**
- the D3b adoption into the shoulder thread's release (our checks were on the candidate 6b2fd93);
- the bench: hub-end coupon first (BENCH_TESTS 2b: ring pick, lug-plate pick, rock and twist checks, stop-load test and plate-hole imprint inspection).

Earlier, R1f (the D3 candidate with a step and column, plates lumped on the whole face): YAW gave posts 2.8 or more and hub
lug bodies 2.05 or more. Its step and strip corner values were lumped-plate artefacts, which R1g removes.

## R1e: the design for review (2026-11-12)

The ring geometry below (R1d ring) stays, but its crush-rib fit is retired. Joey chose a play-free joint, and **R1e** gets it
from a printed shim:
- **Flank line-to-line** as printed (gap 0), no ribs. Lead-ins at the ridge ends: the load flank relieved 0.1 along its normal
  over the last 2 mm of arc each side of the seam, both halves (so closing doesn't bind or scuff).
- **End face lowered 0.70.** A printed PETG shim ring, r 36.2-38.4 (2.2 mm wide, on the rev D disc's flat face, r 36.05-38.73),
  sits between our end face and the hub disc. The thickness is picked by trial at assembly from a set of 0.30-1.10 in 0.05 steps
  (17 sizes, 22 rings, 3 plates, 55 min, 9.1 g). Notches in the ring's inner edge mark it: t = 0.25 + 0.05 × N.
  - Tolerance stack (axial): arm flank to end face ±0.115, hub groove flank to disc ±0.15, flatness ±0.05 (arm) and ±0.1 (disc
    at its seam). Worst case ±0.415, RSS ±0.22. The set covers the worst case.
  - Pick: "start with the thickest ring and work down until the front half closes by hand with the seam shut; use that one".
    Residual play is at most one step (0.05 axial, ≤ 0.28 mm at the wrist).
  - Why not a wedge: closing is along Z, so seating the 30° flank across ±0.2 would need each half's hub end to move 0.4.
    Bending it that far needs about 9 kN against about 0.8 kN per screw. Notes: R1D_NOTES.md, "R1e".
- Unchanged from the ring design: slot edge break 1.2 × 1.6 for the rev D lug-root fillets, the 0.5 bore chamfer (moved down
  with the end face), the as-built bolt joint (brass inserts), fins, hub rev D (bc16e97).
- Outside: the shim shows as a thin band at the arm-hub junction, 0.6 inside our skin. The shoulder cuff ends about Y 313.6, so
  it doesn't cover it. The step visible in the band near θ 70-110 and 250-290 is the hub's own outer wall stepping out (r 38.76
  to 39.3). Pictures: `r1e_hub_end_front.png`, `r1e_hub_end_back.png`, `r1e_shadow_line_closeup.png`,
  `r1e_side_with_shoulder.png`, `r1e_junction_under_cuff.png` (the last two use the shoulder thread's WIP fork meshes).

R1e checks (`../20261111_r1c-delta/r1d/r1e/`):

| Check | Result |
| --- | --- |
| Slice + mesh gate, halves | Back PASS 5 h 25 / 123.8 g; front PASS 4 h 44 / 107.3 g |
| Accepted thin walls (back half) | Three counterbore exits, the same features as R1's accepted entries. A point-to-surface diff against the R1d ring half shows ≤ 0.05 mm there; the R1e tessellation merged two regions and stretched two 1-2 mm up the counterbore wall, out of the old boxes. Three entries added with that reason (`r1e/print_whitelist.json`). |
| Closing path against bc16e97 with a 0.70 ring | 0 path collisions (hub + ring, RS02, RS02 ring). Final overlap ≤ 0.041 mm (front) / 0.039 (back), only along the load flank: line-to-line through faceted meshes. None within about 9° of the seam (lead-ins). |
| Hub-end fit coupon (cut at Y 284) | Back PASS 69 min / 16.9 g; front PASS 64 min / 16.1 g; cut-plane slivers accepted in a coupon-only list. Procedure: BENCH_TESTS.md section 2b, pass rule included. |
| 0 gap G90 (flank line-to-line, shim lumped into the end face) | All ≥ 1.5. Lowest: end-face corner θ 296, shear 1.68 / 3.48 / 11.14 at 0.5 / 1 / 2 mm (0.81 at the 0.1 gap). Hub groove bottom / spigot core layer 2.20; posts layer 2.38. |
| 0 gap STOP_0, STOP_124 | Done on the clean 4.0 mesh (r1e_g00_stop_d, r1e_g00_stop124_d; the 0.4 / 0.5 lug-root refinement at global 5.0 broke the spigot-underside mesh and was dropped). STOP_124 is 1.33 or more. STOP_0 is 1.2 or more except the lumped end-face corner (shear 1.04 / 1.93). Superseded by R1g. |
| Shim ring bearing (from the lumped runs; the ring was **not** modelled as a separate body, see below) | End-face contact pressure of the 0 gap model mapped onto the ring annulus r 36.2-38.4 (516 mm2), arm side. Mean / net axial force / worst 30 deg sector mean / worst 0.5 mm / 1 mm average / peak (MPa, compression): G90 1.2 / 0.64 kN / 4.6 / 15.2 / 7.4 / 29; STOP_0 1.0 / 0.50 kN / 3.0 / 30.1 / 13.6 / 43; STOP_124 2.2 / 1.1 kN / 9.4 / 19.7 / 15.1 / 21; YAW +17 1.2 / 0.64 kN / 4.4 / 35.2 / 14.3 / 69. Against 45 MPa (the model's PETG yield; printed PETG compression is about 55-60 and through the layers is not a weak direction): sector means SF 4.8 or more, 1 mm averages SF 3.0 or more. The 0.5 mm values and the peaks all sit at r 36.40, the contact edge where the 0.5 bore chamfer meets the end face: a model edge, local to the ring's inner rim. Hand check: 1.1 kN over 516 mm2 is 2.1 MPa mean (the shoulder thread's figure is about 3 MPa per kN on their 324.6 mm2 seat; same order). `ring_bearing_lumped.txt` |
| **YAW_17** (RS02 17 N·m peak about the hub axis, both signs; 0 gap lumped model; global 4.0, 0.8 on posts / lugs / fins, lug-root fillets at 0.8) | **Below 1.5.** The ring carries no torque about the hub axis, so all of it goes through the lugs: 312-334 N per lug in Z (pads < 1 N). Loaded post (the one the lug pushes on, at its top edge by the slot break, Y 294.5): vm 0.99 / 1.41 / 1.86 (+17, +X front, n 6/31/170) and 0.95 / 1.47 / 2.05 (-17, +X back); the opposite-corner posts 1.17 / 1.09; post shear 1.07-1.54. Hub lug roots layer 0.92-0.96 / 1.32-1.38 / 2.1-2.2, shear 0.95-0.99 (0.8 mesh: the refined value would be lower). Hub lug bolt-hole bearing 1.19-1.26. Inserts vm 188 MPa (SF 1.27 vs brass yield). Bolts SF 4.9-5.4 (transverse shear only about 30 MPa: the load runs along the bolt axis). Fins ≥ 3.2. End-face corner θ 296 (+17) shear 0.69 / 1.23 / 2.88: the lumped model's contact edge, where R1e has the shim. G90 + yaw by superposition: the same figures within 0.05 except the end-face corner (0.49 / 0.88 / 2.11). `r1e_g00_yaw*3*.txt`; remedies in R1D_NOTES.md "YAW_17" |

Rejected variants, and why:
1. **R1c / R1d partial ridge with tapered ends:** failed at the ridge ends in STOP_0 (arm vm 0.64 / shear 0.71 at θ 143, confirmed
   with the corrected post-processing). Replaced by the full ring.
2. **0.1 flank gap + crush ribs (R1d nominal):** the ribs carry the flank load as point contacts and bed in under routine G90
   (crown rib about 95-130 N against about 41-51 N to flatten). That leaves play equal to the print gap: 0.115 / 0.231 axial,
   0.66 / 1.31 mm at the wrist for gaps 0.1 / 0.2. Joey asked for a play-free joint.
3. **Load-carrying ribs (R2 sizing on paper):** ribs strong enough for G90 at 1.5 need about 53 mm² of face, about 2 kN to crush
   on closing; the screws give about 0.8 kN each. Load-carrying and take-up conflict.
4. **Wedge seat by seam relief:** seating the 30° flank across ±0.2 needs each half's hub end to move 0.4 along Z. Bending it that
   far takes about 9 kN, and relieving the whole seam would open the elbow end.
5. **Split clamp band** inside the skin: in PETG the band can't both flex 0.4 under about 1 kN and carry the loads.
6. **TPU spring bias** in the end-face gap: no rattle, but only TPU-stiff when pushed: about 4 mrad of G90 rocking, 1.6 mm at the
   wrist.
7. **R0.8 round on the end-face inner edge** (instead of the 0.5 chamfer): would cost bearing, and is not needed. The G90 corner
   value it targeted was a contact-edge value of the gap design; at 0 gap it is 1.68.

Open caveats:
- **Upper hub approximated above Y 300.5.** The FEA hub is our ring hub plus the rev D lug-root fillet (the same edge selection as
  the shoulder thread). Through the joint (Y 295.5-300) its sections match bc16e97 within 0.1 %. Above that, rev D's outer wall
  and top boss differ, so the hub's upper-region figures are indicative only; the shoulder thread's FEA governs there. Our FEA
  hub also has a sharp spigot foot where rev D has about R0.23 (it doesn't touch the arm).
- **Mesh:** 4.0 mm global (5.0 in the refined stop runs), 0.8 on the seat, posts, lugs and fins. The lug-root fillets are refined
  to 0.4, not 0.3: 0.3 exceeded the solver's memory limit (458 k nodes). The groove band can't be refined, because its faces are
  full rings (2.3-3.0 M nodes).
- **Model:** frictionless contact, no bolt preload, linear PETG, isotropic stiffness with layer allowables. The shim ring is held
  on the disc by the touching-face bond, with no-penetration against our end face.
- **The ring was not modelled as a separate body.** A shim-body model (the ring as its own PETG body, bonded to the disc, frictionless no-penetration to our end face) was tried three times. The ring separated correctly in the normal direction, but the contact stuck tangentially: in STOP_0 about 10-11 N.m of the stop's twist went through the ring as shear (mean tau 0.54 MPa, slip 0.0005 mm) and the lugs carried nothing, with friction logged off on every contact set. The cause was not found within the time given, so those runs are dropped. The lumped, frictionless runs load the lugs, posts and hub fully, so they are the conservative cases for those parts; the ring's own bearing is taken from them (table above).
- **Shim creep:** the ring sees about 1-2 MPa mean and 3-9 MPa over the worst 30 deg sector in G90 and the stops, a few percent of PETG compressive strength in the sector means; at that level PETG creep is a few um on a 0.7 ring over long holds. The local 15-35 MPa at the inner edge (r 36.4) is a contact edge that beds in. The bench split-and-inspect step measures the ring after the cycles (thinner by 0.03 or more, a flattened band or a cut inner edge: stop).
- **Shim thickness:** printed accuracy about ±0.03-0.05 (first-layer squish on SuperTack). The pick by trial absorbs it; a set
  offset as a whole is reprinted shifted, never the arm.
- **Before the halves print:** the hub-end coupon must pass (closes by hand with a ring, seam shut, no rock after ten cycles,
  nothing scored).
- The seed slicer project sets no elephant-foot compensation; the seam lead-ins (0.1 × 2 mm) are what keep the ridge ends from
  binding. To be seen on the coupon.
- The accepted thin-wall entries for R1e (three counterbore exits) rest on the ≤ 0.05 mm surface diff described in the table above.

The R1d ring sections below are the history of how the ring and these numbers were reached. Cases 3-5 there are the rib design
that R1e replaces.

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
| 3. nominal STOP_0 (ribs 0.1 proud, touching): rib bedding | **θ 135 crush rib: arm shear 0.36 / 0.66 / 1.41, vm 0.47 / 0.80 / 1.59 (20-21); hub flank shear 0.70 / 0.90 / 1.57, layer 0.85** | 1.87 / 1.85 / 2.26 | 2.01 / 1.33 / 1.26 | 0.97 / 1.20 | rib-dominated (bore wall by the rib 0.53 / 0.39) |
| 4. nominal G90 (target 1.5): rib bedding | **crown crush rib θ 105: arm shear 0.43 / 0.73 / 1.70, vm 0.60 / 0.93 / 1.94 (18-20); hub flank shear 0.83, layer 1.15** | 3.04 / 2.32 / 3.12 | 8.4 / 18.4 / 7.8 | 1.28 / 1.99 | rib-dominated (bore wall by the rib 0.77 / 0.49) |
| 5. nominal STOP_124: rib bedding | **ribs θ 75 / 45: arm shear 0.36 / 0.60 / 1.41, vm 0.45 / 0.72 / 1.56 (18-22); hub flank shear 0.65, layer 0.86** | 1.74 / 1.64 / 1.91 | 2.42 / 1.48 / 1.46 | 0.93 / 1.35 | rib-dominated (bore wall by the rib shear 0.44) |
| 6. 0.2 gap STOP_0 | **hub lug root (fillet, -X lug +Z), shear 1.04 / 1.64 / 2.58, layer 1.11 / 1.65 / 2.73 (11)**; hub groove bottom layer 1.17; spigot core layer 1.19 | 1.79 / 2.72 / 2.46 | 1.83 / 1.11 / 1.04 | 1.17 / 1.25 | 1.25 / 2.28 / 6.19; 1.30 / 2.45 / 5.95 |
| 7. 0.1 gap STOP_0 repeat, 0.3 mm on the lug-root fillets | not run: superseded by R1e / R1g | | | | |
| 8. 0 gap (flank in contact, no ribs) G90 | not run: superseded by R1e / R1g | | | | |
| 9. 0 gap STOP_0 | not run: superseded by R1e / R1g | | | | |
| 10. 0.2 gap G90 | not run: superseded by R1e / R1g | | | | |
| 11. 0.1 gap STOP_124 (highest lug load, flank bearing) | not run: superseded by R1e / R1g | | | | |

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
2. **Rib bedding, expected, not a strength failure (cases 3 and 4).** With the ribs 0.1 proud and touching (the as-assembled
   state), the crush ribs carry the flank load as point contacts: the θ 135 rib in the stop (arm shear 0.36 at 0.5 mm), the
   crown ribs θ 75 / 105 in G90 (0.43). A rib's flank face (about 0.9 mm²) holds about 41-51 N before flattening; the crown ribs
   see about 95-130 N normal in G90. So they bed in within the first routine cycles until the flank bears, which is the
   strength case covered by the 0 / 0.1 / 0.2 gap runs. Play once bedded: axial 0.115 / 0.231 mm and rocking 0.09° / 0.18° for
   gaps 0.1 / 0.2 (0.66 / 1.31 mm sideways at the wrist), showing only on load reversal.
   **Flag: hub flank marking under a rib (hub shear 0.70 stop, 0.83 G90, local), for the shoulder thread and the reviewer.** R2
   options: wider / longer ribs that crush flush on assembly, or a line-to-line flank. A fit coupon tests closing, crush and
   play on a printed rev D hub.
   Earlier wording of this item: **Nominal stop: the θ 135 crush rib carries the flank load.** It is overloaded at the rib (arm shear 0.36 at 0.5 mm, 0.66
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
