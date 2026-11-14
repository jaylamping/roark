# Upper arm, stage 1: print the hub-end test set, then test it on the bench

**Status: ready, not released.** Print it when the shoulder thread releases the hub and I say go. The two arm halves stay on hold
until these tests pass (see "What happens after").

Stage 1 is a short test of the arm's hub end before the 10 h of halves:
- a cut-down **hub-end coupon** (both halves);
- the **shim rings** and **lug plates** that take up the play;
- a printed **yaw lever** to load it.

The hub is the shoulder thread's part. Everything here is in `cad/prints/upper-arm/` on branch `left-arm-organic-r1`.

## 1. Print (white PETG, Cool Plate SuperTack, no glue, 0.4 High Flow nozzle)

For every plate:
- Open the `.3mf` with **File > Open Project**. Keep the project's settings when Bambu Studio asks.
- Don't move or rotate anything: it is already the right way up.
- The general checks are in [SETTINGS_CHECKLIST.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/SETTINGS_CHECKLIST.md).

| Order | File (3MF) | Picture | Time | PETG | Differs from your arm defaults |
| --- | --- | --- | --- | --- | --- |
| 1 | [lug plates A](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_lug_plates_A_r1h_d34.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/reviews/upper-arm/20261112_ring-delta/r1h_d34_lug_plate_set_sheet.png) | 19 min | 1.8 g | **0.10 layers, first layer 0.25**, 100 % infill, no support, no brim |
| 2 | [lug plates B](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_lug_plates_B_r1h_d34.3mf) | same sheet | 19 min | 1.5 g | **0.10 layers, first layer 0.20**, 100 %, no support, no brim |
| 3 | [shim rings A](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_shim_rings_A_r1g.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/reviews/upper-arm/20261112_ring-delta/r1g_shim_ring_set_sheet.png) | 21 min | 3.8 g | **0.10 layers, first layer 0.20**, 100 %, no support, no brim |
| 4 | [shim rings B](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_shim_rings_B_r1g.3mf) | same sheet | 21 min | 3.8 g | **0.10 layers, first layer 0.15**, 100 %, no support, no brim |
| 5 | [shim rings C](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_shim_rings_C_r1g.3mf) | same sheet | 13 min | 1.5 g | **0.10 layers, first layer 0.20**, 100 %, no support, no brim |
| 6 | [coupon, back](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_back_r1g_coupon.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_back_r1g_coupon_sheet.png) | 1 h 12 min | 18.2 g | none: as the halves (6 walls, 50 %, tree supports, 5 mm outer brim) |
| 7 | [coupon, front](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_front_r1g_coupon.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_front_r1g_coupon_sheet.png) | 1 h 7 min | 17.0 g | none: as the halves |
| 8 | [yaw lever](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_coupon_yaw_lever.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_coupon_yaw_lever_sheet.png) | 1 h 46 min | 72.4 g | **100 % infill, no support, no brim** |
| (hub) | from the shoulder release: *to be filled* | | | | |

Total: about 5 h 40 min and 120 g.

- **Don't change the layer heights of the plates and rings.** Their thickness is built from those layers.
- The coupons' tree supports come out of the hub seat; pick them off the ridge flanks.
- The plates have notches (wide = 0.25, narrow = +0.05), and the rings have notches (thickness = 0.25 + 0.05 × notches).
- [SUPERSEDED.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/SUPERSEDED.md) lists what not
  to print.

## 2. Bench

The full procedure, with the reasons, is section 2b of
[BENCH_TESTS.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/upper-arm/BENCH_TESTS.md). The short version
follows. "Dial" means the dial indicator on a stand fixed to the same base as the hub clamp, reading the coupon itself. Never read
the lever.
- Its tip rests on a small flat-sided block (a 10 mm cube, CA-glued) on the coupon's flat cut end, about 35-38 mm from the hub
  axis.
- The block's flat side faces along the turning direction, because the coupon's round side just slides past a dial tip.
- The limits below are for 40 mm. Multiply them by your radius / 40: at 36 mm, × 0.9.
- A second dial on the coupon's -X side reads the sideways slip (steps 11-12).

| # | Do | Pass |
| --- | --- | --- |
| 1 | Bare fit: hub into the back coupon, close the front by hand. No ring, no plates. | Note only |
| 2 | Calipers: every ring (4 places) and every plate (2 places), written on the form. | A whole set off by the same amount: note it |
| 3 | Hole gauges: drill shanks in each plate hole and each hub lug hole. | Plate takes 3.4, **not** 3.8. Hub lug takes 3.8. |
| 4 | Inserts: measure the knurl diameter and length of 3, then heat-set 2 in the front coupon and 1 in the scrap block. | Flush to 0.05 below the face |
| 5 | Scrap-block insert: torque an M3 bolt to 0.3, 0.5, 0.7 N·m, checking a pen line after each. | No movement at 0.3 |
| 6 | Ring pick: thickest ring first, close by hand, step down until the seam shuts by hand. | One ring closes by hand |
| 7 | Plate pick: blue marker on the plate tops, close and bolt (0.3 N·m), open. Then step plates down, alternating sides, until it closes by hand. | No blue on the hub fillet; one pick closes |
| 8 | Bolts at 0.3 N·m; rock and twist by hand, 10 cycles. | Seam shut (0.1 feeler won't enter); no click, no free turn |
| 9 | **Play:** bolts a quarter turn loose; 1 kg at the hook one way, read the dial, then 1 kg the other way, read again; 3 times. | **Travel ≤ 0.04 mm** |
| 10 | Re-tighten to 0.3. Yaw: 8.7 kg at the hook, 10 s, each way. Read the dial loaded and unloaded. | **Loaded ≤ 0.29 mm**; back within 0.02 |
| 11 | Stop load: 8.7 kg at the hook toward the front side, plus 4.5 kg hanging sideways from a cord round the coupon at the lug line, -X side, 10 s. Then the mirror. Read both dials. | **Yaw ≤ 0.29, sideways ≤ 0.05**; both back within 0.02 |
| 12 | Same stop load with the bolts a quarter turn loose; read the sideways slip. | **Slip ≤ 0.25**; back within 0.03 after re-tightening |
| 13 | Proof: 13 kg at the hook, 10 s, each way, bolts at 0.3. | No click, crack or whitening; back within 0.03 |
| 14 | Open it and photograph: ring, ridge, plate holes, plate corners, hub lug edges. | Imprints at most "felt", nothing that catches a fingernail |
| 15 | Close again with the same ring and plates, 0.3 N·m, leave 24 h, re-torque, redo steps 8 and 9. | Same passes |
| 16 | Last: the coupon's 2 inserts, 0.3 → 0.5 → 0.7 N·m with the pen line. | None moves at 0.3 (record where they move) |

## 3. Tools and consumables

| Item | What it is for | If you don't have it |
| --- | --- | --- |
| **Dial indicator, 0.01 mm, with a stand** (magnetic base on a steel plate, or clamped to a block), plus a **10 mm flat-sided block and CA glue** for it to read on | Steps 9-13: play, yaw and slip, read on the coupon | **Feeler gauges against a block clamped to the base.** Steps 9-12 then only resolve about 0.02-0.05. A tight pick (≈0.02) and a one-step-loose pick (≈0.08) can still be told apart, but anything from 0.03 to 0.06 is unclear and needs the dial. A cheap dial indicator is the one thing worth buying. |
| **Calipers** (0.01 mm) | Step 2 (ring and plate thickness), step 4 (inserts) | A micrometer. Without either you lose the check for a whole set printed thick or thin; the trial picks still work. |
| **Drill shanks, 3.4 and 3.8 mm** (from a metric HSS drill set) | Step 3: catches an old Dia 3.8 plate file, and checks the hub's lug holes | Read the file name and notches instead. You lose the physical check. |
| **4.0 mm drill** (by hand) | Clearing the insert holes before setting them | Any 4.0 mm bit in a pin vise |
| **Torque screwdriver covering 0.3-0.7 N·m** (for example a 0.3-1.2 N·m type) and a **2.5 mm hex bit** | Steps 5, 7, 8, 16 | **None; don't run the test without it.** By feel, 0.3 N·m is unreliable, and the insert check is lost. |
| **Luggage scale (0-15 kg or more)** or known weights: 1 kg, 4.5 kg, 8.7 kg, 13 kg | Steps 9-13 | Water in bottles or a bucket: 1 L = 1 kg (1 L, 4.5 L, 8.7 L, 13 L), hung from a cord. |
| **Cord loop and an S-hook** | Hanging the 4.5 kg sideways (steps 11-12) and the hook load | Any strong string |
| **Blue marker** (or engineer's blue) | Step 7: plate tops against the hub fillet | Pencil graphite, rubbed on |
| **Fine pen** | Witness lines on the inserts (steps 5, 16) | Any fine marker |
| **Feeler gauges, 0.05 and 0.1 mm** | Inserts flush (step 4); seam shut (step 8) | A sheet of 80 g paper is about 0.1 |
| **Straightedge** | Inserts flush (step 4) | The calipers' depth rod |
| **2 × M3 × 25 DIN 912 socket-head bolts** | The two lug bolts | No substitute: the length matters |
| **1 × M3 bolt, 12 mm or so** | The scrap-block insert check (step 5) | Any M3 that reaches the full insert depth |
| **3 × brass heat-set inserts, Ruthex M3 × 5.7** (Dia 4.0 hole): 2 for the front coupon, 1 for the scrap block | Holding the lug bolts | The same insert as the arm, or the test doesn't apply |
| **Scrap PETG block, 8 mm or thicker, with a 4.0 mm hole** | Step 5, the insert check | Print a 20 × 20 × 10 mm block |
| **Soldering iron with an M3 insert tip** (about 220-230 °C for PETG) | Setting the inserts | The plain tip works if you are careful to keep it square |
| **A way to clamp the hub with its axis vertical**, coupon on top: a bench vise with soft jaws on the hub's top end | Steps 8-13 | G-clamps holding the hub's top end to the bench edge, with a wooden block. It must not move under 13 kg at 200 mm (25 N·m). |
| **Torch and phone camera** | Step 14 | - |

## 4. What happens after

- **The halves are released** (back R1h, front R1g; about 10 h 15 min and 233 g) when all of these hold:
  - every row of the form passes;
  - the shoulder thread has released the hub;
  - the hub lug root is agreed with the shoulder thread (their analysis governs there);
  - your insert result from step 16 is in.
- **Stop and send me the form, the readings and the photos** if any of these happens:
  - any pass in the table fails;
  - a plate hole takes the 3.8 shank;
  - no ring closes, or even the thinnest rocks (the set is offset: I'll send a shifted set);
  - an insert moves at 0.3 N·m;
  - anything clicks, cracks or whitens;
  - an imprint catches a fingernail.

## 5. Results form

| Item | Result |
| --- | --- |
| Hub file and print date | |
| Bare fit (step 1): closes? play? | |
| Ring thicknesses measured (if a set is offset, note it) | |
| Plate thicknesses measured | |
| Hole gauges: plates 3.4 yes / 3.8 no; hub lugs 3.8 yes | |
| Inserts: knurl Dia / length (3); flush? | |
| Scrap-block insert: moved at (0.3 / 0.5 / 0.7 / none) | |
| Ring picked (notches, mm) | |
| Plates picked: -X lug front / back, +X lug front / back | |
| Blue on the hub fillet? | |
| Seam shut at 0.3 N·m? Rock and twist: click or free turn? | |
| Dial radius actually used (mm) | |
| Step 9 play travel, 3 tries (≤ 0.04) | |
| Step 10 yaw, loaded each way / unloaded (≤ 0.29 / within 0.02) | |
| Step 11 stop load: yaw dial, sideways dial, loaded / unloaded | |
| Step 12 slip, bolts loose: loaded / unloaded after re-torque (≤ 0.25 / ≤ 0.03) | |
| Step 13 proof: click / crack / whitening? Back within 0.03? | |
| Step 14 imprints (none / felt / catches) at each place, with photos | |
| Step 15 after 24 h: step 8 and step 9 again | |
| Step 16 coupon inserts: moved at (0.3 / 0.5 / 0.7 / none) | |
| Pass / fail overall | |

**Photos:** the ring (both faces), each plate (both faces, hole edge and top corner), the post faces round each lug bolt, both
hub lug faces including the outer front edge, the ridge flank, the dial set-up, and anything that looks wrong.
