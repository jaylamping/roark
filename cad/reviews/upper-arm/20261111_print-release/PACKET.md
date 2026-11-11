# Upper arm, concept A: print-release review packet

Commit: `7ad4452c0c3343b3bb413d53554b3e7f396a4fe0` (branch `left-arm-organic`, jaylamping/roark). Parts: front half, back half, RS02 mounting ring (all
`data/cad`, STEP and STL, arm frame in mm: elbow axis along X at Y 209.861, Z 5.986; shoulder yaw axis X 170.49). Sliced
Bambu P2S projects and coupons: `data/prints`. Today's hub (unchanged) and the vendor RS02 placed in the arm are in `data/cad`.

## What the parts are

- **Halves:**
  - Split on the side plane Z 5.986 and printed seam face down.
  - Two M3 seam posts in the neck, plus an M3 through each lug of today's hub. Inserts are in the front half.
  - The drum holds the elbow RS02.
  - A printed 60° stop lug on the drum's inboard end runs in a slot in the forearm.
- **RS02 mounting ring:**
  - 11.8 mm thick, printed flat on its RS02 face.
  - Screwed to the RS02 flange with 6 × M3 × 16. 6.2 mm of thread against the vendor's 8 mm.
  - A window for the plug at φ 1.5°, so the plug goes in on the bench toward the neck.
  - A notch for the unused socket, and pockets for the socket-tab screw heads.
- **Torque path ring → halves:**
  - Four keys on the halves' rib (φ 80 and 120 in the back half, 240 and 280 in the front) run through open slots in the
    ring to 0.3 mm short of the RS02 flange.
  - Each key bears on one face only:
    - +T (ring turning +X about the elbow axis): keys 0 and 2.
    - −T: keys 3 and 1.
  - Clearances: 0.1 mm on the bearing faces, closed by two 0.25 mm crush ribs per face. 1 mm on the faces that must never
    bear first.
- **Layer directions:**
  - Halves: layers normal to Z. Key bending (σx) and shear (τxy) are in-plane; σz is across the layers.
  - Ring: layers normal to X. σx is across the layers.
- **Assembly:** the ring and RS02 drop into the back half along −Z, and the front half closes along −Z. `rs02_fit.json`
  checks this with the vendor model.

## Checks done (results in `data/checks`, `data/fea`)

1. **Fit with the vendor RS02** (`rs02_fit.json`):
   - Flange-to-ring gap 0.0 mm. RS02 front to the stop 0.2 mm.
   - Interference with the RS02: {'front': 0.0, 'back': 0.0, 'rs02_ring': 0.0}.
   - Plug and cable envelope against the halves: {'front': 0.0, 'back': 0.0}. Plug against the ring: 0.0.
   - Slide-in from 60 mm down to seated: 0 at every step down to 5 mm. At 2 mm and 0 mm the only overlap is the crush ribs,
     designed 0.15 mm interference: {'assembly_vs_back': 2.79, 'front_closing_vs_assembly': 2.79}.
   - Plug pull-out with the front half off: {'0': 0.0, '5': 0.0, '10': 0.0, '15': 0.0, '20': 0.0}.
2. **Print** (`*_check.json`, `*_meshcheck.txt`, `views/sheet_*.png`):
   - The mesh gate is `marengo hardware/tools/mesh_check.py`. Whitelist entries, each with a reason: `print_whitelist.json`.
   - Support on a visible face is judged against the assembled arm, including the hub, the forearm cheeks and the caps.

| Plate | Height mm | Time | g | Mesh gate | Support on visible faces from the G-code, mm² |
| --- | --- | --- | --- | --- | --- |
| ring | 11.8 | 0 h 57 | 19.04 | PASS | 0.0 |
| back | 44.5 | 5 h 03 | 116.52 | PASS | 0.0 |
| front | 44.5 | 4 h 35 | 104.36 | PASS | 0.0 |
| stub_coupon | 24.0 | 0 h 37 | 6.4 | PASS | n/a |
| key_coupon | 17.5 | 0 h 32 | 9.97 | PASS | n/a |

3. **One key carrying the RS02's peak, 17 N·m** (34 N·m solved, stresses halved). The ring is fixed on its flange face, the
   halves at the hub seat. The force is normal on the bearing face. Ring results exclude nothing; the halves' 'bulk' is the
   whole model away from fixtures.

| Key (direction) | Ring | Halves key (fine) |
| --- | --- | --- |
| key 0 (φ 80, back half), +T | slot 1.76, layer (σx) 3.62; no exclusion 1.75 — fine: slot 1.50, layer (σx) 2.80; no exclusion 1.50 | bulk 1.62, layer (σz) 1.82; no exclusion 1.62 |
| key 2 (φ 240, front half), +T | not run — fine: slot 1.60, layer (σx) 3.54; no exclusion 1.59 | bulk 1.84, layer (σz) 2.14; no exclusion 1.84 |
| key 3 (φ 280, front half), −T | slot 1.78, layer (σx) 3.58; no exclusion 1.79 — fine: slot 1.50, layer (σx) 2.66; no exclusion 1.50 | bulk 1.86, layer (σz) 1.86; no exclusion 1.87 |
| key 1 (φ 120, back half), −T | not run — fine: slot 1.60, layer (σx) 3.46; no exclusion 1.59 | bulk 1.96, layer (σz) 1.90; no exclusion 1.97 |

   Every key meets SF 1.5, bulk and layer, at 17 N·m. The lowest is halves key 0, at its tip where its joint to the drum wall
   ends (`views/hotspot_key0.png`). The key torque coupon (`data/prints/upper_arm_organic_key_coupon.3mf`) is the bench proof.

4. **Two keys sharing 34 N·m:**

| Case | Ring | Halves |
| --- | --- | --- |
| keys 0 + 2 sharing 34 N·m (17 each) | slot 1.50, layer (σx) 2.80; no exclusion 1.50 | bulk 1.30, layer (σz) 1.50; no exclusion 1.30 |
| keys 3 + 1 sharing 34 N·m (17 each) | slot 1.50, layer (σx) 2.65; no exclusion 1.50 | bulk 1.64, layer (σz) 1.16; no exclusion 1.64 |

5. **Stop lug.** One pad face loaded. 444 N is half of 889 N (linear). Nodes within 2 mm of the pad are left out
   (`stop_post.py`).

| Case | Lug root at 889 N, bulk / layer | Lug root at 444 N, bulk / layer | Elsewhere at 444 N, bulk / layer | No exclusion at 444 N |
| --- | --- | --- | --- | --- |
| STOP_0 | 1.17 / 0.95 | 2.34 / 1.9 | 2.68 / 1.42 | 0.82 (pad edge) |
| STOP_0_fine | 1.15 / 0.92 | 2.3 / 1.84 | 2.76 / 1.36 | 0.78 (pad edge) |
| STOP_124 | 1.17 / 1.07 | 2.34 / 2.15 | 1.56 / 1.33 | 1.05 (pad edge) |
| STOP_124_fine | 1.14 / 1.1 | 2.28 / 2.2 | 1.77 / 1.41 | 0.87 (pad edge) |

6. **Global cases.** Bonded model, ring merged. The ring zone X 152.8–165.8 is left out (the ring cases cover it).
   Bulk SF / layer (σz) SF:

| Case | Coarse (3 mm) | Fine (2 mm) |
| --- | --- | --- |
| 5 kg, arm horizontal (G90) | 3.61 / 3.08 (no exclusion 1.83) | 3.20 / 3.32 (no exclusion 2.05) |
| G0 / hanging | 54.99 / 35.73 (no exclusion 28.12) | not run |
| G45 | 4.99 / 3.98 (no exclusion 2.45) | not run |
| G135 | 5.06 / 4.63 (no exclusion 2.44) | not run |
| G180 | 50.21 / 55.54 (no exclusion 26.16) | not run |
| lateral + | 4.53 / 4.20 (no exclusion 4.53) | not run |
| lateral − | 4.47 / 4.41 (no exclusion 4.46) | not run |
| 17 N·m twist about the arm (LC2) | 7.72 / 3.62 (no exclusion 6.74) | not run |
| 17 N·m on the RS02 housing (E17) | 3.67 / 3.02 (no exclusion 1.79) | not run |
| 34 N·m on the RS02 housing (E34) | not run | 1.71 / 1.84 (no exclusion 1.28) |

7. **Cable passages:** table in `data/UPPER_ARM_README.md`.

### What is left out of a figure, and why (pictures in `views/excl_*.png`)

Every table gives the excluded figure and, beside it, the peak with nothing left out. An un-excluded peak that isn't a
load or fixture artefact counts.

- **Merged RS02 ring zone, X 152.8–165.8** (bonded global cases): the ring is bonded to the rib and the wall, so the ring and
  its bond edges are artefacts, and the ring and keys have their own cases. Bonded contact edge: `views/excl_ring.png`.
  The halves' rib-to-wall corner at X 154.1 lies in this zone and is a real peak. It is reported as such in table 4 and in
  E34's no-exclusion column, and it was the reason for the R2 round.
- **Hub seat, Y > 290** (global cases): a rigid fixture on today's unchanged hub joint, a fixture singularity.
  `views/excl_seat.png`.
- **Stop lug pad, within 2 mm** (stop cases): a 0.4 mm pad carries the load, and its edge is a load-application
  singularity. `views/excl_pad.png`.
- **One-key and pair cases:** nothing is left out on the ring. The halves figure leaves out 2 × the element size around the
  hub-seat fixture only.

## Not done, or unverified

- No contact FEA. Keys and the stop lug are loaded as forces on faces, and the ring is fixed on its whole flange face. That
  stands in for 6 × M3 friction, about 38 N·m at 0.35 N·m tightening, by hand calculation.
- The crush ribs are wiped along their length as the ring slides in (Z), not pressed square-on. They are meant to shave to a
  line-to-line fit on the first assembly. Not tested.
- The 6808 fit on the printed Ø40.0 stub was checked with the stub coupon (2026-11-11): a perfect fit, no caliper reading.
- Model versions: the final geometry is v26 (commit above). Re-run on v26: E34 fine, both pairs (ring and halves), the four
  ring one-key cases, and halves key 0 alone. From v25: halves keys 1, 2 and 3 alone, and G90 fine. v25 differs from v26
  only in the rib-to-wall corner round (R1, now R2) and the ring's matching chamfer (1.2, now 2.2). From v23: the stop and
  the other global cases. v23 also lacks keys 1 and 2 running into the wall and the wall thickening past the key tips. Per case: `data/fea/fea_versions.json`.
- The global cases below the fine mesh were run once, at 3 mm.
- PETG properties are assumed: E 1.9 GPa, yield 45 MPa, layer strength 0.5 × yield.
- The FEA models are SolidWorks files, not in this packet. Each result carries the model's SHA256 in `data/fea`.

## Stated deviation: the neck-opening corner

The elbow torque crosses from the drum into the neck where the rib meets the drum wall, at the two edges of the neck opening
(back half φ 41°, front half φ 336°; X 154–155, r about 41.5). It now has an R2 round, up from R1. At 34 N·m, with nothing
left out:
- E34 (pure 34 N·m, bonded): bulk SF 1.28, layer (σz) SF 1.10.
- Keys 3 + 1 sharing 34 N·m: 1.64 / 1.16.
- Keys 0 + 2 sharing 34 N·m: 1.52 / 2.43.

At the RS02's own 17 N·m peak it is about SF 2.2 on both. The target was 1.5 at 34 N·m. The corner is layer-limited, because
on the back half's seam-down layers it bends across them. Picture: `views/hotspot_neckcorner.png`. The arm will be torque
tested on the bench.

A candidate fix is being built while you review: a web from the rib to the wall under both neck-opening edges, on the rib's
inboard side (X 144.5–147.4, where the ring isn't), at φ 30–50 and 325–345. Inside only, and the harness keeps at least
3.5 × 13.

## Hardware already made

- **RS02 ring:** Joey printed it before the last change, with a 1.2 mm outer chamfer on its rib-side face. CAD now has 2.2 mm
  there to clear the R2 round, which touches a 1.2 mm chamfer at 0.00 mm. He will break that edge by hand to about 2 × 45°.
  Nothing else on the ring has changed since his print.
- **Stub coupon:** printed. A 6808 fits the Ø40.0 stub perfectly.

## Questions

1. Is the neck-opening corner (1.28 bulk / 1.10 layer at 34 N·m, about 2.2 at 17 N·m) acceptable for a first print that will
   be bench torque tested? If not, what is the least you would change?
2. Is the candidate web worth it? Or is there a better internal fix for a layer-limited corner on a seam-down printed half,
   with no change to the outside and no change to the ring?
3. Is anything in the key / ring / crush-rib assembly likely to bind or crack on first assembly or on service removal?
   Look at the ring and RS02 going into the back half along −Z, the front half closing along −Z, the 0.15 mm crush ribs on
   the bearing faces, the 1 mm free faces, and Joey's hand-chamfered ring.
4. Is the RS02 placement right against the vendor model? Look at the socket clocking, the screw holes used, the tab-head
   pockets and the plug window.
5. Is anything in the print files wrong for the P2S? Look at orientation, supports, the 100% modifiers, settings flagged as
   changed, and SuperTack with a 5 mm brim.
6. Is the stop rating (444 N, 17 N·m) honest at the lug root, given the pad exclusion and the pad-edge figures?
7. Anything in the cable passages, the plug window or the rib gap that would pinch or chafe the trunk?
