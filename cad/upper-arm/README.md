# Upper arm clamshell, left

Draft 4, 2026-11-09. Only the front and back halves changed from draft 3 (2026-11-08); the ring, hub, loop clip and
carrier are as in draft 3.

Status: **the gate, support, slice and FEA results below are draft 3 results, awaiting a rerun on the draft 4 halves.** On
draft 3 the mesh gate passed and the support check was done, but the governing lateral case did not pass in the FEA model
(see Checks). The two-reviewer gate is still to come, so don't print yet.

## Changes from draft 3

From `ua_parts.py` (commit 886117b):

- **Skirt trim on the ring plane.** The RS02-side skirt outboard of the ring is trimmed at Y 242.1 (`Y_SKIRT`, the ring /
  halves plane at Y 242 plus the 0.1 mm clearance) instead of Y 240. The halves now have one lower edge across X, with no
  step at the ring end, where the draft 3 lateral-case minimum sat. The cut still removes the skirt's down-facing tip.
- **Post-root fillets.** The front half's four seam posts and two hub-lug posts are true cylinders run up to the skin they
  meet, with a fillet at the root: 2 mm (`POST_FILLET`), stepping down to 0.5 mm where a larger one won't build, and none
  if no radius builds. The radius each post got is printed by the build and not recorded in the repo. The back-half posts
  are unchanged: flat-ended 0.25 mm into the skin, because a post run down to the skin would leave a 0.5 mm wall round the
  Ø6.5 counterbore.
- **Ring kerf, FEA model only.** `ua_parts.py fea_contact` builds a model with the ring cut free of the halves along their
  printed clearances and the ring-pin hole through both bodies, for the contact FEA. The printed parts don't change.
- **Mesh whitelist.** One new back-half entry: the oblique exit of the Ø3.4 ring-pin hole through the ring-pocket face, a
  wedge of about 3 mm² under the ring, inside the closed arm.

## Files

| Part | File (`cad/upper-arm/`) | Export (`cad/exports/upper-arm/`) |
| --- | --- | --- |
| Front half (`upper` in the scripts) | `upper_arm_shell_front_left.SLDPRT` | `.step`, `.stl` |
| Back half (`lower`) | `upper_arm_shell_back_left.SLDPRT` | `.step`, `.stl` |
| RS02 seat ring (`ring`) | `upper_arm_elbow_ring_left.SLDPRT` | `.step`, `.stl` |
| Hub disc (`hub`) | `upper_arm_hub_left.SLDPRT` | `.step`, `.stl` |
| Loop clip (`clip`) | `upper_arm_loop_clip_left.SLDPRT` | `.step`, `.stl` |
| Spring carrier, unchanged | `upper_arm_spring_carrier_left.SLDPRT` | `.step`, `.stl` |
| Master the parts are cut from | `upper_arm_clam_master_left.SLDPRT` | none |

The master is the one-piece db71b23b upper arm (marengo) with the cable window and cover suppressed, so the outer skin is
continuous to ±0.03 mm. It was built in marengo by `ua_master.py`; only its result comes here.

## Scripts

In `cad/scripts/arm/`. They run on Joey-PC with SolidWorks and Bambu Studio installed, from that folder.

```
python ua_parts.py ring hub upper lower clip   # cut the parts from the master, save them and their exports
python ua_parts.py fea fea_contact             # bonded and ring-contact FEA models, into cad/_sim/upper-arm/
python ua_gate_run.py                          # mesh gate + support check, into cad/_wip/arm-gate/
python ua_slice.py                             # Bambu Studio slices and grams, into cad/_wip/arm-slices/
```

- `ua_names.py` maps the script job names to the file names above.
- `swg.py`, `sk.py`, `swlib.py`: SolidWorks helpers in arm coordinates. They run this session's own SolidWorks instance through
  `tools/solidworks/sw_instance.py` (PID file in `cad/_wip/arm-sw/`, or `ARM_SW_DIR`).
- `build.py` + `p2_seed.json`: the Bambu Studio project builder. The seed is the reviewed P2 L04B print project with its mesh
  removed, so every setting is the P2 process (PETG, 0.2 mm).
- `mesh_check.py` + `mesh_whitelist.py`: the mesh gate and its reviewed exceptions. `support_check.py`: support on visible faces.
- `cad/scripts/fea/`, run from the repo root: `p3_fea.py` solves a linear static case in SolidWorks Simulation and reports
  bulk and print-layer SF; `ua_fea.py` holds the bonded cases and `ua_fea_contact.py` the ring-contact cases;
  `fea_parts.py` reads the saved nodal stresses per printed part.
- After `ua_parts.py` rewrites an export, record it: `python tools/cad/record_export.py exports/upper-arm/<file> upper-arm/<part>.SLDPRT --config Default --settings "..."`.

## Parts and printed mass

Sliced in Bambu Studio with the P2 process: PETG, 0.2 mm, `ua_slice.py`. **The grams are draft 3 results.** The front and
back halves have not been sliced since the draft 4 rebuild; the ring, hub and clip are unchanged.

| Part | What it is | Print | Sliced |
| --- | --- | --- | --- |
| Front half | Half above the seam (Z > 6). Four Ø7.5 seam posts and two hub-lug posts with root fillets, Ruthex inserts, M3 × 30 pilots and Ø5.9 pin sockets. Fuse pockets from the master | Seam face down. 4 walls, 50%, with 6 walls and 100% on the posts, the hub band (Y 286–303) and the ring capture | **55.6 g** |
| Back half | Half below the seam. Matching posts with Ø5.5 × 1.2 pins and counterbores. Ø10 trunk entry through the back wall below the hub, with a tie boss. Ø6.8 RS00-branch exit at Y 270 through the back-inboard wall, with a tie boss | Seam face down. Same settings | **53.5 g** |
| Ring | RS02 seat ring, X 150.8–166.2, keeping the master hoop OD (cut at r 44.25). It takes the skin flare below Y 242 and has a top slot widened to Z −9.5..18. One M3 insert on the back OD at Y 246.5 | 6 walls, 100% | **32.3 g** |
| Hub | Hub disc: a 4 mm plate at the yaw RS02 face with six windows, the old tube floor opened, a spigot r 28–35.8, and two seam lugs rooted in the spigot | RS02 face down. 6 walls, 50%, with 100% on the plate, the bosses and the spigot | **63.4 g** |
| Loop clip | Elbow back-loop saddle for the **unchanged** carrier: a 3 mm foot, and two crush-ribbed spigots in the carrier's Ø9.4 screw-access bores at 44° and 84° | Standing on its flat end. **No support** | **7.7 g** |

**Total, draft 3: 204.7 g sliced for the four arm parts.** The one-piece db71b23b arm sliced at 229.0 g on the same process, and weighed **202 g** on the scale. That is 10.7% lighter, so expect **about 180 g**, plus the 7.7 g clip.

The parts are small and thin, so 6 walls plus shells make them nearly solid; dropping the halves to 4 walls saved little. The real savings came from the hub plate (6 → 4 mm), the windows and the floor opening.

## Seam and fasteners

- **Seam:** Z split at Z 6.
- **Seam posts:**
  - At X 147.5 and 193.5 (23 mm off the tube axis), Y 262 and 278.
  - Each lower post ends 0.25 mm into the inner skin at its centre. Nearer the wall, a vertical post pokes out through the curved outer skin, which the first draft did.
  - Upper posts run up to the upper skin, with a root fillet (draft 4).
  - M3 × 30 from below, through a counterbore whose floor is the post end.
- **Hub lugs:** posts at X 147.5 / 193.5, Y 292, with M3 × 40.
- **Ring pin:** one M3 × 12 along Z from the back, at (X 158.5, Y 246.5), into a ring insert.
  - It replaces draft 1's lug. That lug sat inside the master's port slot and hung on 0.2 mm skins.
  - Draft 2 had a second pin from the front, but Joey wants clean front skin. Two pins side by side on the back hit the ring end faces.
  - The ring is keyed against turning by its flare faces against the halves at Y 242, plus this pin.

## Visible holes

Every screw head is on the back (lower, −Z) half. The front (upper) half has no holes in its outer skin.

| Where | Hole | Purpose |
| --- | --- | --- |
| Back, X 147.5 / 193.5, Y 262 and 278 | 4 × Ø6.5 counterbore, flat floor at the post end, head recessed 3.7–4.3 mm | M3 × 30 seam screws |
| Back, X 147.5 / 193.5, Y 292 | 2 × Ø6.5 counterbore, flat floor, recessed about 3 mm | M3 × 40 hub-lug screws |
| Back, X 158.5, Y 246.5 | 1 × Ø6.5 counterbore, flat floor, recessed about 5 mm | M3 × 12 ring pin |
| Back, X 171, Y 289, below the hub | Ø10 | Trunk entry. A tie boss is just inside |
| Back-inboard wall, Y 270 | Ø6.8 | RS00 branch out to the loop clip. A tie boss is just inside |

- **Hidden holes:** the hub's M4 holes and windows sit under the yaw RS02 face. The ring's carrier-screw holes sit between the carrier and the RS02.
- **Why the counterbores look oval from the side:** the screws are vertical and break out of the curved underside at an angle.
- **Pins:** Ø5.5 × 1.2 pins on the lower posts locate the halves.

## Checks

Every result in this section was taken on draft 3 and awaits a rerun on the draft 4 halves, except where a draft 4 result
is cited with where it is recorded. The draft 3 gate and FEA data are in the review packet
[`reviews/upper-arm/20261108_clamshell-draft3/`](../reviews/upper-arm/20261108_clamshell-draft3/README.md).

**Mesh gate:** `ua_gate_run.py`, with `mesh_check.py` and the whitelist in `mesh_whitelist.py`. Draft 3: all five parts pass.

The whitelist holds:
- the master's own reviewed spots;
- four ring parting-line feathers, where the master hoop OD runs tangentially into the hoop-to-tube fillet;
- the oblique exits of the counterbores and the RS00 hole on the curved underside.

Each entry carries its reason.

**Support on visible faces** (`support_check.py`, judged against the assembled arm), draft 3:

| Part | Visible faces needing support |
| --- | --- |
| Upper | None. The 84 mm² it flags are insert-hole ceilings and fuse-pocket faces inside the shell |
| Lower | 0.4 mm² |
| Ring | 0 |
| Hub | None visible. The 183 mm² it flags are the lug faces under the spigot, inside the closed arm |
| Clip | Prints with support off. Its overhangs are the short spigot cantilevers, hidden in the bores |

In draft 3 the RS02-side skirt was trimmed above Y 240, because its tip was the one visible down-facing band. Draft 4
trims it at Y 242.1, which also removes that tip.

**Seam FEA, draft 3** (`ua_fea.py`, run in marengo; the script is now in `cad/scripts/fea/`):

- **Model:** the db71b23b cases on a one-body model of the clamshell geometry: hub lightening, posts, skirt and ring trims, widened slot.
  - Load: remote load on the six carrier-screw holes in the ring.
  - Fixed: the hub face that clamps on the yaw RS02.
  - Bonded at the seam. The seam tractions are then read off to check the bolted joint.

| Case | Part SF away from load and fixture (yield 45 MPa) | Layer SF | Seam σz peak / mean tension | Seam shear mean / p95 |
| --- | --- | --- | --- | --- |
| LC1A (300 N, 17 N·m) | 3.49 | 3.47 | 0.42 / 0.07 MPa | 0.31 / 1.01 MPa |
| LC1B | 3.49 | 5.01 | 0.15 / 0.03 | 0.31 / 1.01 |
| LC1C (lateral) | 2.54 | 2.18 | 0.64 / 0.16 | 0.06 / 0.19 |
| LC2 (17 N·m twist) | **1.98** | 2.83 | 0.44 / 0.04 | 0.36 / 0.93 |

- **Joint load:** at most about 65 N of shear per side and under 30 N of opening.
- **Joint capacity:** two M3 posts per side at roughly 300 N preload after PETG creep, plus two Ø5.5 pins. The joint stays closed with margin.
- **Weakest spot:** LC2's 1.98 sits where the Y 262 upper post meets the upper skin, a square junction at 3 mm mesh. Draft
  4 adds the post-root fillet there; LC2 has not been rerun on it.
- One-piece db71b23b on its own fixture, for reference:

| Case | SF |
| --- | --- |
| LC1A | 2.23 |
| LC1C | 2.56 |
| LC2 | 4.24 |

**Governing case, draft 3** (Joey: arm straight, 5 kg at the hand about 0.5 m from the shoulder pitch, plus self-weight):

- **Load at the elbow point:** 62 N along gravity plus 17.2 N·m, which gives 24 N·m at the hub face.
- **Sweep:** shoulder pitch 0/45/90/135/180°, gravity g = (0, −cos θ, −sin θ) in the arm frame. Lateral is gravity along ±X, with the moment about Z.
- **Pass marks:** 1.5 bulk, 1.25 layer, and 2.0 at 90° for the motor-holding creep.
- **How SF is taken:** per part, with each part's own layer normal (halves Z, ring X, hub Y). Points within 4.5 mm of the loaded carrier-screw holes and the fixture face are excluded.

| Case | Upper bulk / layer | Lower | Ring | Hub | Seam σz peak, shear mean |
| --- | --- | --- | --- | --- | --- |
| G0 (hanging) | > 40 | > 40 | 19.7 | > 200 | 0.05, 0.00 MPa |
| G45 | 4.22 / 8.7 | 10.0 | 5.8 | 23 | 0.09, 0.08 |
| **G90 (horizontal, motor holding)** | **3.10 / 7.0** | 6.3 / 7.5 | 10.9 / 9.6 | 17.3 / 9.3 | 0.12, 0.11 |
| G135 | 4.55 / 9.9 | 9.7 | 5.6 | 26 | 0.08, 0.08 |
| G180 (overhead) | > 40 | > 40 | 19.7 | > 200 | 0.03, 0.00 |
| **Lateral +X** | 2.14 / 3.55 | **1.17** / 3.95 | 1.69 / 9.3 | 21 / 10.9 | 0.97, 0.04 |
| **Lateral −X** | 2.14 / 2.43 | **1.17 / 0.93** | 1.69 / **0.99** | 21 / 10.6 | 0.88, 0.04 |

**Pitch sweep, draft 3:** passes. The minimum is 3.10 bulk at 90°, above the 2.0 creep mark. The seam carries almost nothing in pitch.

**Lateral, draft 3: does not pass in this model.** The minimum is at (166.4, 240.0, ±22.5), the re-entrant corner where the ring's +X end face meets the RS02-side skirt trim (Y 240).

- **Why the model may overstate it:** the one-body model bonds the ring to the halves there. In the real parts that boundary is a 0.15 mm gap, and the load goes through:
  - the pocket contact;
  - the flare faces at Y 242;
  - the ring pin.
- **What it does show:** the lateral moment, about 19 N·m at that section, has to cross the ring-to-halves interface. That interface is not verified.
- **Next, as planned after draft 3:** a contact model (no-penetration between the ring and the halves, with the pin bonded), plus a geometry fix at that corner:
  - match the skirt trim and the ring flare tip at one Y, so there is no step at X 166.35;
  - put a 3 mm radius on the corner.
- **Where draft 4 stands on it:**
  - The skirt trim now matches the ring plane (Y 242.1), so the step is gone. The 3 mm corner radius is not in the code.
  - The contact model is built by `ua_parts.py fea_contact` and solved by `ua_fea_contact.py`, with the ring pin as a pin
    connector. No contact result is recorded in the repo.
  - On the bonded model the ring's end face still meets the halves at a re-entrant edge along X 166.35, Y 242.1. The
    comment above `KERF_EDGE` in [`cad/scripts/fea/fea_parts.py`](../scripts/fea/fea_parts.py) records that the peak on
    that edge grows with mesh refinement in the lateral case (front layer SF 1.72 / 1.62 / 1.16 at 3 / 2 / 1.5 mm), and
    treats it as a model artefact: in the printed parts it is the 0.1 mm kerf. `fea_parts.py` leaves out nodes within
    3 mm of it. No per-part draft 4 table is recorded.

## Elbow back loop

- **Clip:**
  - Saddle at 60°, r 48, in the loop plane X 132.
  - 8.4 mm U-groove, 8 mm flat, tilted 15° outward, R25 floor run-outs over 45°.
  - 4.5 × 2 mm cable-tie tunnel.
  - The block extends to w −12.5 so the run-out leaves no sliver.
- **Foot:** kept at r ≥ 31.5 to clear the forearm hub (draft 1 hit it by 1.2 mm), with cut-outs around the 6808 retainer heads.
- **Fit:**
  - Carrier penetration 0.2 mm (the crush ribs).
  - 1.35 mm or more from every screw head and washer.
  - Clear of the forearm by 2.5 mm or more through 0–124°.
- **Sizing** (`loop_sweep.py` in marengo):
  - 190 mm free, bend radius at least 27.9 mm.
  - Bow about 70 mm at 0°.
  - Clearances: forearm 8.5 mm, RS02 26, carrier screws 16.
  - The nearest saddle edge is 1.7 mm away at 120–124°.
- **Retorque:** the clip pulls off by hand for the carrier-screw retorque. See marengo `hardware/docs/assembly.md`.
- **Forearm saddle:** on the cheek rim at 140°. It comes with the forearm clamshell.

## Not in this draft

- Splice cradle: the splice sits loose in the tube, tied to the trunk relief.
- Two-reviewer gate.
