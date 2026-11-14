# Upper arm, stage 1: print the hub-end test set, then test it on the bench

**Status: ready to print, hub first, once I say go.** The shoulder thread released the hub for stage 1 (2026-11-14). The two arm
halves stay on hold until these tests pass (see "What happens after").

Stage 1 is a short test of the arm's hub end before the 10 h of halves:
- the **shoulder hub**, printed first, because everything else is fitted to it;
- a cut-down **hub-end coupon** (both halves);
- the **shim rings** and **lug plates** that take up the play;
- a printed **yaw lever** to load it.

The hub is the shoulder thread's part, and its print file is on the PCs (below). Everything else is in `cad/prints/upper-arm/` on
branch `left-arm-organic-r1`.

## 1. Print (white PETG, Cool Plate SuperTack, no glue, 0.4 High Flow nozzle)

For every plate:
- Open the `.3mf` with **File > Open Project**. Keep the project's settings when Bambu Studio asks.
- Don't move or rotate anything: it is already the right way up.
- The general checks are in [SETTINGS_CHECKLIST.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/SETTINGS_CHECKLIST.md).

| Order | File (3MF) | Picture | Time | PETG | Differs from your arm defaults |
| --- | --- | --- | --- | --- | --- |
| **1 (first)** | **Shoulder hub, rev D3c7:** `shoulder_hub_left_revD3c7.3mf` on Joey-PC in `J:\code\prints\shoulder-hub\` (on holly-pc in `C:\joe\prints\shoulder-hub\`), with its README. The STL is [shoulder_hub_left.STL](https://github.com/jaylamping/roark/blob/claude/project-thread-90ef87/cad/exports/shoulder/shoulder_hub_left.STL) at commit 355aa9b (SHA-256 a73103ad…259b, checked against ours) | [plate](https://github.com/jaylamping/roark/blob/claude/project-thread-90ef87/hardware/shoulder/study-20261111/checks/hub_print/shoulder_hub_left_revD3c7_plate.png) | 2 h 47 min | 81.9 g | **100 % infill, no brim**; tree supports with a blocker over the groove and lugs (support only in the dish under the RS02 face). **RS02 face (the flat 50 mm ring) down, lugs up: don't turn it.** |
| 2 | [lug plates A](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_lug_plates_A_r1h_d34.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/reviews/upper-arm/20261112_ring-delta/r1h_d34_lug_plate_set_sheet.png) | 19 min | 1.8 g | **0.10 layers, first layer 0.25**, 100 % infill, no support, no brim |
| 3 | [lug plates B](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_lug_plates_B_r1h_d34.3mf) | same sheet | 19 min | 1.5 g | **0.10 layers, first layer 0.20**, 100 %, no support, no brim |
| 4 | [shim rings A](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_shim_rings_A_r1g.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/reviews/upper-arm/20261112_ring-delta/r1g_shim_ring_set_sheet.png) | 21 min | 3.8 g | **0.10 layers, first layer 0.20**, 100 %, no support, no brim |
| 5 | [shim rings B](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_shim_rings_B_r1g.3mf) | same sheet | 21 min | 3.8 g | **0.10 layers, first layer 0.15**, 100 %, no support, no brim |
| 6 | [shim rings C](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_shim_rings_C_r1g.3mf) | same sheet | 13 min | 1.5 g | **0.10 layers, first layer 0.20**, 100 %, no support, no brim |
| 7 | [coupon, back](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_back_r1g_coupon.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_back_r1g_coupon_sheet.png) | 1 h 12 min | 18.2 g | none: as the halves (6 walls, 50 %, tree supports, 5 mm outer brim) |
| 8 | [coupon, front](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_front_r1g_coupon.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_front_r1g_coupon_sheet.png) | 1 h 7 min | 17.0 g | none: as the halves |
| 9 | [yaw lever](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_coupon_yaw_lever.3mf) | [sheet](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/upper_arm_organic_coupon_yaw_lever_sheet.png) | 1 h 46 min | 72.4 g | **100 % infill, no support, no brim** |

Total: about 8 h 27 min and 202 g (the hub 2 h 47 min and 81.9 g of it).

- **The hub's own notes** are in its README and in the hub section of
  [PRINT_NOTES.md](https://github.com/jaylamping/roark/blob/claude/project-thread-90ef87/hardware/shoulder/study-20261111/cad-pass1/PRINT_NOTES.md).
  - Leave its two small top holes (the ones a 4 mm pin won't enter) for now; they are reamed later, when the shoulder goes
    together.
  - The shoulder thread mentions ironing the disc face if the slicer offers it. It is not set in the 3MF, so print it as it is.
- **Don't change the layer heights of the plates and rings.** Their thickness is built from those layers.
- The coupons' tree supports come out of the hub seat; pick them off the ridge flanks.
- The plates have notches (wide = 0.25, narrow = +0.05), and the rings have notches (thickness = 0.25 + 0.05 × notches).
- [SUPERSEDED.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/prints/upper-arm/SUPERSEDED.md) lists what not
  to print.

## 2. Bench

The short version for this first iteration. The full reasoning is in section 2b of
[BENCH_TESTS.md](https://github.com/jaylamping/roark/blob/left-arm-organic-r1/cad/upper-arm/BENCH_TESTS.md).

**Bolts: snug, nothing more.** Turn them with two fingers on the short end of the 2.5 mm hex key, then stop. Don't lean on it.
The brass inserts sit in PETG, and a hard turn pulls them out. "Loose" means backed off a quarter turn.

**Reading movement: a 300 mm pointer.**
- Fix the pointer:
  1. Glue a small block (about 10 × 20 × 10 mm) with epoxy or CA gel onto the front coupon's outer skin, on its +Z side, in the
     band between the yaw lever and the hub.
  2. Glue a 300 mm steel ruler flat on top of the block, pointing straight out from the hub axis.
- Clamp a second ruler (0.5 mm marks) to the base under the ruler's tip, and draw a pen line across the tip.
- Read the line against the marks with a phone photo, about 0.1 mm.
- Before the loads, push the tip sideways with a finger and let go: it must come back to its mark. If it doesn't, re-glue it.
- The numbers below are for the tip 300 mm from the hub axis. Never read the lever itself: it sits loosely on the coupon.

| # | Do | Pass |
| --- | --- | --- |
| 0 | **Hub, after printing:** pull the support out of the dish; push a 3.8 mm drill shank through both lug holes; measure the spigot (the round part between the groove and the lugs) in two directions; look at the groove's sloping flanks. | Both holes take 3.8 freely (clear them with a 3.8 drill if not). Spigot: send me both numbers (CAD 71.6). Flanks smooth. |
| 1 | **Gauge the plates:** a 3.4 mm drill shank in each plate hole. | Takes 3.4, **not** 3.8 |
| 2 | **Inserts:** heat-set 2 in the front coupon. | Flush with the face |
| 3 | **Bare fit:** hub into the back coupon, close the front by hand. No ring, no plates. | Note only |
| 4 | **Ring pick:** thickest ring first, close by hand, step down until the seam shuts by hand. | One ring closes by hand |
| 5 | **Plate pick:** blue marker on the plate tops, close and bolt (snug), open, check. Then step plates down, alternating sides, until it closes by hand. | No blue on the hub fillet; one pick closes |
| 6 | **Bolt it** (snug), clamp the hub upright, coupon on top. Rock and twist it by hand. | Seam shut; no click, no free turn |
| 7 | **Play:** lever on, pointer fixed. Bolts loose. 1 kg at the lever's hook one way, photo; 1 kg the other way, photo; three times. Then snug the bolts again. | **Travel ≤ 0.3 mm** (a plate one size too thin reads about 0.6) |
| 8 | **Yaw:** 8.7 kg at the hook, 10 s, each way. Photo loaded and unloaded. | **≤ 2.2 mm** loaded; back to the start |
| 9 | **Stop load:** 8.7 kg at the hook plus 4.5 kg hanging sideways on a cord round the coupon at the lug line, 10 s, each way. Then once more with the bolts loose, watching a pen mark on the coupon's side against a ruler. | Pointer ≤ 2.2 and back; with the bolts loose, the side mark moves ≤ 0.25 |
| 10 | **Last, and optional: proof.** 13 kg at the hook, 10 s, each way. Skip it if you'd rather keep the coupon. | No click, crack or whitening; back to the start |
| 11 | **Open it and look**, and photograph everything: ring, plates, inserts, the hub's lugs and lug roots (the rounded corner where each lug meets the hub), the groove. | Inserts not lifted or spun; plates not cracked; no whitening or cracks; imprints at most felt, nothing that catches a fingernail |

Twelve steps (0-11).

**What this short version gives up:**
- **No torque numbers.** "Snug" replaces the 0.3 N·m cap, so the clamp varies from bolt to bolt. That matters little: the play
  check runs with the bolts loose, and the plates carry the yaw and stop loads.
- **No test of how much torque the inserts take.** That waits for the arm.
- **No 24 h re-check.**
- **The pointer reads to about 0.1 mm.** The sideways movement under the stop load with the bolts snug can only be checked as "no
  visible movement".

**If you own a dial indicator or a torque screwdriver,** BENCH_TESTS 2b has the instrument version. Neither is needed here.

## 3. Tools and consumables

| Item | For |
| --- | --- |
| 2.5 mm hex key | Every bolt, snug |
| 2 × M3 × 25 DIN 912 socket-head bolts | The two lug bolts (the length matters) |
| 2 × brass heat-set inserts, Ruthex M3 × 5.7 (Dia 4.0 hole), and a soldering iron (about 220-230 °C) | The front coupon (step 2) |
| 3.4 and 3.8 mm drills, used shank-first as gauges, plus a 3.8 drill to clear the hub holes if needed | Steps 0 and 1 |
| Calipers | The hub's spigot (step 0) |
| A 300 mm steel ruler, a second ruler with 0.5 mm marks, a small block, epoxy or CA gel, and a clamp for the scale | The pointer (steps 7-10) |
| Luggage scale, or water: 1 L = 1 kg (1, 4.5, 8.7, 13 kg) | Steps 7-10 |
| Cord and an S-hook | Hanging the loads |
| Blue marker (or pencil graphite) | Step 5 |
| A vise or G-clamps holding the hub upright by its top end; it must not move under 13 kg on the lever | Steps 6-10 |
| Torch and phone camera | Photos, step 11 |

## 4. What happens after

- **The halves are released** (back R1h, front R1g; about 10 h 15 min and 233 g) when every row passes, and you send me the
  spigot numbers and the photos.
- **Stop and send me the photos** if any of these happens:
  - a pass fails;
  - a plate hole takes 3.8;
  - no ring closes, or even the thickest rocks (the set is offset; I'll send a shifted one);
  - an insert lifts or spins;
  - anything clicks, cracks or whitens;
  - an imprint catches a fingernail.

## 5. Results form

| Item | Result |
| --- | --- |
| Hub: holes take 3.8? Spigot, two numbers? Flanks smooth? | |
| Plates: holes take 3.4, not 3.8? | |
| Bare fit: closes? play? | |
| Ring picked (notches) | |
| Plates picked: -X lug front / back, +X lug front / back | |
| Blue on the hub fillet? | |
| Rock and twist: click or free turn? | |
| Play, three tries (≤ 0.3) | |
| Yaw, each way, loaded / back (≤ 2.2) | |
| Stop load: pointer, and side mark with the bolts loose (≤ 2.2 / ≤ 0.25) | |
| Proof done? Click, crack or whitening? | |
| After opening: inserts lifted or spun? Plates cracked? Whitening? Imprints (none / felt / catches)? | |

**Photos:** the printed hub; the dial or pointer set-up; every pointer reading; after the test, the ring, each plate, the inserts,
both hub lugs and their roots, and the groove.
