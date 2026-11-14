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
| (hub) | the shoulder thread's D3c7: [shoulder_hub_left_revD3c7_candidate.STL](https://github.com/jaylamping/roark/blob/claude/project-thread-90ef87/cad/exports/shoulder/shoulder_hub_left_revD3c7_candidate.STL) (commit 96f74ab, SHA-256 a73103ad…259b, checked against ours: `D3C7_CHECK.md`) | | | | **No sliced 3MF exists for it yet.** Its print file and settings come from the shoulder thread; don't slice it yourself until they say how it prints. |

Total: about 5 h 40 min and 120 g.

- **Don't change the layer heights of the plates and rings.** Their thickness is built from those layers.
- The coupons' tree supports come out of the hub seat; pick them off the ridge flanks.
- The plates have notches (wide = 0.25, narrow = +0.05), and the rings have notches (thickness = 0.25 + 0.05 × notches).
- [SUPERSEDED.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/SUPERSEDED.md) lists what not
  to print.

## 2. Bench

The full procedure, with the reasons, is section 2b of
[BENCH_TESTS.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/upper-arm/BENCH_TESTS.md). The short version
follows. It needs no special instruments: torque comes from a weight hung on the hex key, and movement is read with a long pointer
and photos. If you buy a torque screwdriver and a dial indicator, use them instead (see "Alternative" at the end of this section).
The test is the same either way.

### 2.1 Torque without a torque screwdriver: a weight on the hex key

With the hub clamped upright, the lug bolts lie sideways, so the hex key's long arm can stick out level.

1. Turn the bolt in by hand until the head just touches.
2. Put the 2.5 mm hex key in with its long arm **level** (horizontal), on the side where a weight hanging from it turns the bolt
   tighter (clockwise seen from the head).
3. Tie a loop of thread round the arm near its end and tape it so it can't slide.
   - **Measure the hang distance d**: from the centre of the bolt to the thread, along the arm.
   - A standard 2.5 mm key's long arm is only about 56 mm, and a long-arm key about 90 mm, so measure; don't assume.
4. Hang a small cup or bag from the thread, then fill it with water to the weight in the table. Weigh cup + thread + water
   together on a kitchen scale, or use a measuring jug (1 mL of water = 1 g) plus the empty cup's weight.
   - Weight in grams = 102 000 × torque (N·m) ÷ d (mm).
   - The key's own weight is a few grams near the bolt and can be ignored.

   | Hang distance d | 0.3 N·m | 0.5 N·m | 0.7 N·m |
   | --- | --- | --- | --- |
   | 50 mm | 612 g | 1020 g | 1427 g |
   | 56 mm (standard key) | 546 g | 910 g | 1274 g |
   | 60 mm | 510 g | 850 g | 1189 g |
   | 80 mm | 382 g | 637 g | 892 g |
   | 90 mm (long-arm key) | 340 g | 566 g | 793 g |
   | 100 mm | 306 g | 510 g | 714 g |

5. **Add the weight gently.** Lower it by hand until it hangs free; never drop it.
   - If the key swings down, the bolt turned. Lift the weight off, move the key to the next flat so the arm is level again, and
     hang it again.
   - The bolt is at that torque when hanging the weight no longer moves the key for 5 s.
   - For "a quarter turn loose", just back the bolt off a quarter turn by hand.

### 2.2 Reading movement without a dial indicator: a 300 mm pointer and photos

The coupon turns only a few hundredths of a millimetre, so a long pointer magnifies it. A tip 300 mm from the hub axis moves 7.5
times more than the coupon does at 40 mm.

- **The pointer:** a 300 mm steel ruler, lying flat (its width horizontal, which makes it very stiff sideways).
- **Where it goes:** the yaw lever covers the coupon's cut end, so the pointer is fixed below the lever, to the coupon's outer skin,
  on the front coupon's +Z side (90° from the lever's arm, so the lever and the cords can't touch it).
- **Fixing it so it can't wobble:**
  1. Glue a small block (about 10 × 20 × 10 mm, scrap PETG or wood) onto the coupon's outer skin in the free band between the
     lever and the hub disc. Use 5-minute epoxy, or thick CA gel, filling the slight curve of the skin, over its whole face.
  2. Glue the ruler flat on top of that block with at least 20 mm of overlap, pointing straight out from the hub axis. Use
     epoxy or CA gel, and wait for full cure.
- **Check the joint (do this once, then again before the proof):** with the bolts at 0.3 N·m, press the pointer tip sideways
  with a fingertip (a light push), then let go, each way, three times.
  - It must come back to the same mark every time (within 0.1 mm).
  - It may move a little while pressed (the ruler and coupon flex); the return is what matters.
  - If it doesn't come back, the glue joint is rocking and would read as play: re-glue it.
  - The pointer carries no load in the tests, so its own bending doesn't enter the readings. Only a loose joint does, and this
    check catches that.
- **The scale:** fix a second ruler (0.5 mm marks) to a block clamped to the same base as the hub clamp, right under the pointer's
  tip, its marks running the way the tip moves. Put a fine pen line across the pointer's tip.
- **Reading:** a phone photo straight down at the tip, from the same spot each time (rest the phone on a stack of books or a jig),
  zoomed in. Read the pen line against the marks to about 0.1 mm. Every reading is a photo; keep them.
- **Measure R**, the distance from the hub axis to the pen line. The pass numbers below are for R = 300. For another R, multiply
  by R / 300; keep R at 250 or more.
- **Sideways slip (steps 11-12)** is a sliding movement, not a turn, so the pointer can't magnify it. Read it directly:
  - put a pen line on a piece of tape on the coupon's -X side, above the cord;
  - read it against a ruler fixed to the base beside it.

### 2.3 Steps and pass numbers

| # | Do | Pass (pointer tip at R 300) |
| --- | --- | --- |
| 1 | Bare fit: hub into the back coupon, close the front by hand. No ring, no plates. | Note only |
| 2 | Calipers: every ring (4 places) and every plate (2 places), written on the form. | A whole set off by the same amount: note it |
| 3 | Hole gauges: drill shanks in each plate hole and each hub lug hole. | Plate takes 3.4, **not** 3.8. Hub lug takes 3.8. |
| 4 | Inserts: measure the knurl diameter and length of 3, then heat-set 2 in the front coupon and 1 in the scrap block. | Flush to 0.05 below the face |
| 5 | Scrap-block insert (clamp the block so its bolt lies sideways): torque an M3 bolt to 0.3, 0.5, 0.7 N·m by the weight method, checking a pen line after each. | No movement at 0.3 |
| 6 | Ring pick: thickest ring first, close by hand, step down until the seam shuts by hand. | One ring closes by hand |
| 7 | Plate pick: blue marker on the plate tops, close and bolt (0.3 N·m), open. Then step plates down, alternating sides, until it closes by hand. | No blue on the hub fillet; one pick closes |
| 8 | Bolts at 0.3 N·m; rock and twist by hand, 10 cycles. Fit the pointer and check its joint. | Seam shut (no light through it); no click, no free turn; pointer returns to its mark |
| 9 | **Play:** bolts a quarter turn loose. Hang 1 kg at the lever's hook one way and photo the tip; then 1 kg the other way and photo; 3 times. | **Travel ≤ 0.30 mm.** A tight pick reads about 0.1-0.15; a pick one plate step loose reads about 0.57. |
| 10 | Re-tighten to 0.3. Yaw: 8.7 kg at the hook, 10 s, each way. Photo loaded and unloaded. | **Loaded ≤ 2.2 mm** (expected about 1.7); back within 0.15 |
| 11 | Stop load: 8.7 kg at the hook toward the front side, plus 4.5 kg hanging sideways from a cord round the coupon at the lug line, -X side, 10 s. Then the mirror. Photo the pointer and the slip mark. | **Pointer ≤ 2.2**, back within 0.15. **Slip mark: no visible movement** (under about 0.1). |
| 12 | Same stop load with the bolts a quarter turn loose; photo the slip mark loaded, then after re-tightening. | **Slip ≤ 0.25**; back to the start mark (no visible offset) |
| 13 | Proof: 13 kg at the hook, 10 s, each way, bolts at 0.3. Then open it and look at the **hub lug roots**: the outer R1.2 round where each lug's Z faces meet the hub, on both lugs, both faces, with the torch. Photograph each one. | No click; no crack or whitening anywhere, including the hub lug roots; pointer back within 0.23 |
| 14 | Open it and photograph: ring, ridge, plate holes, plate corners, hub lug edges. | Imprints at most "felt", nothing that catches a fingernail |
| 15 | Close again with the same ring and plates, 0.3 N·m, leave 24 h, re-torque, redo steps 8 and 9. | Same passes |
| 16 | Last: the coupon's 2 inserts, 0.3 → 0.5 → 0.7 N·m by the weight method, with the pen line. | None moves at 0.3 (record where they move) |

### 2.4 What the substitutes lose, compared with the instruments

- **Weight on the hex key, instead of a torque screwdriver:** about ±10 % on the torque (the hang distance measured to ±2 mm on
  56 mm, the arm a few degrees off level, the water weighed to a few grams).
  - That is fine for 0.3 / 0.5 / 0.7 N·m steps; it is slower.
  - Friction can stop the bolt a little early: it is at the torque only once the weight no longer moves the key.
- **Pointer and photos, instead of a dial indicator:**
  - 0.1 mm at R 300 is 0.013 mm at the coupon's 40 mm, nearly as fine as the 0.01 dial, so the play, yaw and proof readings keep
    their meaning. A one-step-loose pick still fails clearly (0.57 against 0.30).
  - What is lost:
    - **the stop load's sideways check with the bolts tight** (0.05 mm with a dial), which becomes "no visible movement, under
      about 0.1";
    - the sideways return after the loosened-bolt slip (0.03 with a dial), which becomes "no visible offset";
    - live reading: each reading is a photo, so you can't watch it move;
    - a glue joint that loosens during the loads would read as play. That is why the return check is repeated before the proof.

### 2.5 Alternative: torque screwdriver and dial indicator

If you have a torque screwdriver (0.3-0.7 N·m, 2.5 mm hex bit) and a dial indicator (0.01 mm) on a stand, use them for the same
steps.
- Set every torque with the screwdriver instead of the weight.
- The dial reads a 10 mm cube glued to the same place as the pointer's block: the coupon's outer skin, +Z side, below the lever.
  - The cube's side faces along the turning direction. Put the dial tip on it, square to that side, about 40 mm from the hub axis.
  - A second dial on the coupon's -X side reads the slip.
- Pass numbers at the dial (r 40):
  - play ≤ 0.04 (one step loose reads about 0.076);
  - yaw ≤ 0.29, back within 0.02;
  - stop load: yaw ≤ 0.29 and sideways ≤ 0.05, both back within 0.02;
  - slip with the bolts loose ≤ 0.25, back within 0.03;
  - proof back within 0.03.
- Scale the numbers by r / 40 if the tip sits elsewhere.

## 3. Tools and consumables

| Item | What it is for | If you don't have it |
| --- | --- | --- |
| **A 300 mm steel ruler** (the pointer), a **second ruler with 0.5 mm marks** (the scale), **a small block** (about 10 × 20 × 10 mm, scrap PETG or wood), **5-minute epoxy or CA gel**, a **block and clamp** to hold the scale on the base, and a **phone** for the photos | Steps 8-13: play, yaw and slip (section 2.2) | Alternative: a **dial indicator, 0.01 mm, on a stand** (section 2.5). Without a pointer or a dial the play test can't be read: don't skip it. |
| **Calipers** (0.01 mm) | Step 2 (ring and plate thickness), step 4 (inserts) | A micrometer. Without either you lose the check for a whole set printed thick or thin; the trial picks still work. |
| **Drill shanks, 3.4 and 3.8 mm** (from a metric HSS drill set) | Step 3: catches an old Dia 3.8 plate file, and checks the hub's lug holes | Read the file name and notches instead. You lose the physical check. |
| **4.0 mm drill** (by hand) | Clearing the insert holes before setting them | Any 4.0 mm bit in a pin vise |
| **2.5 mm hex key** (measure its long arm), **thread and tape**, a **small cup or bag**, water, and a **kitchen scale or measuring jug** | Every torque (steps 5, 7, 8, 16): the weight method of section 2.1 | Alternative: a **torque screwdriver** covering 0.3-0.7 N·m with a 2.5 mm bit (section 2.5). By feel alone, 0.3 N·m is unreliable: don't. |
| **Luggage scale (0-15 kg or more)** or known weights: 1 kg, 4.5 kg, 8.7 kg, 13 kg | Steps 9-13 | Water in bottles or a bucket: 1 L = 1 kg (1 L, 4.5 L, 8.7 L, 13 L), hung from a cord. |
| **Cord loop and an S-hook** | Hanging the 4.5 kg sideways (steps 11-12) and the hook load | Any strong string |
| **Blue marker** (or engineer's blue) | Step 7: plate tops against the hub fillet | Pencil graphite, rubbed on |
| **Fine pen** | Witness lines on the inserts (steps 5, 16) | Any fine marker |
| **Feeler gauges, 0.05 and 0.1 mm** | Inserts flush (step 4); seam shut (step 8) | A sheet of 80 g paper is about 0.1; or check the seam against a light |
| **Straightedge** | Inserts flush (step 4) | The calipers' depth rod |
| **2 × M3 × 25 DIN 912 socket-head bolts** | The two lug bolts | No substitute: the length matters |
| **1 × M3 bolt, 12 mm or so** | The scrap-block insert check (step 5) | Any M3 that reaches the full insert depth |
| **3 × brass heat-set inserts, Ruthex M3 × 5.7** (Dia 4.0 hole): 2 for the front coupon, 1 for the scrap block | Holding the lug bolts | The same insert as the arm, or the test doesn't apply |
| **Scrap PETG block, 8 mm or thicker, with a 4.0 mm hole** | Step 5, the insert check | Print a 20 × 20 × 10 mm block |
| **Soldering iron with an M3 insert tip** (about 220-230 °C for PETG) | Setting the inserts | The plain tip works if you are careful to keep it square |
| **A way to clamp the hub with its axis vertical**, coupon on top: a bench vise with soft jaws on the hub's top end | Steps 8-13 | G-clamps holding the hub's top end to the bench edge, with a wooden block. It must not move under 13 kg at 200 mm (25 N·m). |
| **Torch** | Steps 13-14 | - |

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
| Method (pointer + weight / dial + torque driver); pointer R or dial r (mm); hang distance d (mm) | |
| Step 9 play travel, 3 tries (pointer ≤ 0.30 at R 300 / dial ≤ 0.04) | |
| Step 10 yaw, loaded each way / unloaded (pointer ≤ 2.2 / within 0.15; dial ≤ 0.29 / 0.02) | |
| Step 11 stop load: pointer (or yaw dial), slip mark (or sideways dial), loaded / unloaded | |
| Step 12 slip, bolts loose: loaded / after re-torque (≤ 0.25 / no visible offset, or ≤ 0.03 with a dial) | |
| Step 13 proof: click / crack / whitening? Back within 0.23 (pointer) or 0.03 (dial)? Pointer joint re-checked? Hub lug roots (4 places): whitening or crack? Photos taken? | |
| Step 14 imprints (none / felt / catches) at each place, with photos | |
| Step 15 after 24 h: step 8 and step 9 again | |
| Step 16 coupon inserts: moved at (0.3 / 0.5 / 0.7 / none) | |
| Pass / fail overall | |

**Photos:** the hub lug roots after the proof (both lugs, both Z faces), the ring (both faces), each plate (both faces, hole edge and top corner), the post faces round each lug bolt, both
hub lug faces including the outer front edge, the ridge flank, the pointer (or dial) set-up, every pointer reading, and anything that looks wrong.
