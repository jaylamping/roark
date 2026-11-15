# Option C (the arm's 10 A fuse in our upper arm): our check (2026-11-15)

## DECIDED (Joey, 2026-11-15 18:27Z, roark PR 93 `HARNESS_INTERFACE.md`): one 10 A fuse in our neck. IT FITS.

- **The fuses:** ONE 10 A fuse (Littelfuse 0997010.WXN, 58 V, standard MINI, one inline holder on the 18 AWG pair) just below the
  yaw joint. Apart from it, only the hand's 3 A below the shoulder. The elbow RS02's 5 A drop fuse and the 5 A S4 segment fuse are
  **dropped**.
- **So the neck holds:** the 10 A holder, the M14 splice (no holder beside it), the plug break, the RS02's own cable and the
  3.5 × 13 bundle reserve on its route, with the tie bridge in place.
- **(a) It fits** (`neck_pack/pack_decided.json`). The same method as section 1 below, with the holder as a 16 × 11 × 40 box (the
  assumed 36 × 14 × 9 plus clearance):
  - All the items found room in **95 of 400** random layouts.
  - With the holder grown 2 mm each way (18 × 13 × 42): still **17 of 400**.
  - Example layout:
    - holder body Y 251-290 at X 164, Z -11;
    - plug break Y 259-290 at X 179, Z -12;
    - splice Y 251-290 at X 160, Z -1;
    - RS02 cable at X 160, Z 7.
  - **Where:** the holder body stands along the neck in Y 251-290, **12 to 51 mm below the hub seat** (our end face, Y 302).
  - **The 70 mm:** the neck's straight run is about 40 mm, so the 15 mm of straight wire at each end isn't a straight box. It
    continues along the trunk itself: up into the hub's bore above, and down past the tie bridge below. The only bends are gentle
    S-offsets of about 10 mm at R 11.5 or more.
- **(b) The fuse changes with the front half off, the hub left on the motor and the arm on the robot** (section 3):
  - Take out 2 seam screws and 2 lug bolts, all from behind the arm, then lift the front half forward.
  - The 3 mm longer fork skirt stays 16.2 mm above the halves' top.
  - Support the forearm while the front half is off.
- **(c) Tied down with no change to the halves** (section 2):
  - Two 2.5 mm ties lash the holder body to the bundle, and the bundle is tied at the existing tie bridge.
  - Hold the holder to pull the fuse.
  - A snap-on clip for the bridge bar is possible later as a separate part.
- **(d) The pair's length from the hub to the holder is fixed.** Both ties turn with the arm; all the yaw take-up is in the
  shoulder's cable space.
- **(e) 18 AWG continues below the elbow as one pair** (settled 2026-11-15; the elbow cable rig uses it). With the S4 fuse dropped,
  S4 sits behind the 10 A and must stay 18 AWG.
- **Fallback, not needed:** two insulated 2.8 mm spade crimps on the fuse blades under heat-shrink (11 × 5 × 30) fit in 352 of 400.
- **The halves (R1h back, R1g front) do not change.**

Everything below is the check made before the decision (with up to three holders). It stays as the record; its sections 2 and 3
(fixing, reach) apply unchanged.

**The ask.** The shoulder thread proposes option C (not decided by Joey): the 16-to-18 AWG splice stays in the shoulder behind the
yaw RS02, and its 10 A inline fuse moves into our upper arm just below the yaw joint. They want a pocket of about 70 × 16 × 11 mm
on the power pair's run (holder about 36 × 14 × 9, **assumed**, plus 15 mm of straight wire each end), somewhere that opens with
the arm on the robot and not in the hub's bore. Source: roark `hardware/shoulder/study-20261111/checks/WIRING_CONSEQUENCES.md`,
"Option C in detail", commit 2e57336.

**Short answer:**
- **The neck (Y 251-295) is already full.** Today's set (two MINI holders, the M14 splice, the plug break, the RS02's cable, the
  3.5 × 13 bundle reserve) just fits. **A third holder does not fit,** with or without the plug break.
- **A 70 mm straight pocket fits nowhere in the upper arm** above the drum. The neck's straight run is about 40 mm (Y 251-290).
  The holder body fits; its pigtails then follow the trunk's own path above and below it.
- **Tidier, and it fits: let the 10 A fuse replace our 5 A S4 segment fuse.** By the trunk README's logic that segment fuse
  only protects the step down to 18 AWG at M14. With 18 AWG from the shoulder and a 10 A fuse above it, that step is gone.
  That keeps two holders in the neck, but the plug break then has to go (or the holders have to be smaller than assumed; section 6).
- **The halves (R1h back, R1g front) do not change** in any variant that fits. Fitting all three holders would need a bigger neck,
  meaning a new outer shape or thinner neck walls, and the neck corner is the arm's governing FE region. Not recommended.
- **A fuse change** is the same as today: front half off (2 seam screws, 2 lug bolts, from the back), with the forearm supported.
  The longer fork skirt doesn't get in the way.

## 1. The neck, by numbers (`cad/scripts/arm/neck_pack.py`, results in `neck_pack/`)

**Method.** Every 1 mm from Y 300 down to 230:
- **The free cavity:** inside the closed halves' outline, minus the R1h/R1g halves, the RS02 ring, the vendor RS02 and the adopted
  hub E1, each grown by 0.5 mm.
- **The bundle reserve:** the 13 × 3.5 box sits on the checked route from r 21.5 (θ 68: the S down from the hub's bore, past the
  tie bridge).
- **The other items** are rigid boxes standing along Y, placed on a 1 mm grid, 0.5 mm clear of the walls and of each other.
  - The search runs 400 times, each with a random order and random positions. "n of 400" says how often all the items found
    room; 1 means only just.
  - Rigid boxes are pessimistic for loose wire and fair for the holders and plugs.

**Free cavity, mm²:** Y 295: 2817 · 290: 2377 · 285: 2503 · 280: 2203 · 275: 1787 · 270: 1455 (the seam posts) · 265: 1835 ·
260: 1635 · 255: 1605 · 250: 1771 · 245: 735 · 240: 399 (the drum top, round the RS02). Below Y 250 there is no room for a holder.

**Items (every size assumed until Joey measures what he buys):**

| Item | Section × length (mm) |
| --- | --- |
| MINI holder, ours (M14 drop 5 A; S4 segment 5 A) | 15 × 10 × 38 |
| MINI holder, option C 10 A (the shoulder's 36 × 14 × 9 plus clearance) | 16 × 11 × 40 (body only) |
| Plug break: XT30 pair plus a JST-GH 2-pin pair, mated | 12 × 11 × 32 |
| M14 splice lump on the trunk | 8 × 8 × 40 |
| The elbow RS02's own cable, up to the splice | Ø7 × 30 |
| Bundle reserve (on its route) | 13 × 3.5 |

**Results:**

| Variant | Holders | Plug break | Fits? |
| --- | --- | --- | --- |
| Today | 5 A drop, 5 A S4 | yes | **only just: 1 of 400** |
| Today without the break | 5 A drop, 5 A S4 | no | yes, 106 of 400 |
| Option C, the 10 A body alone | 10 A | - | yes: Y 251-290, 126 positions |
| Option C, the 70 mm straight pocket | 10 A | - | **no, anywhere in Y 231-298** |
| Option C, all three holders | 10 A, 5 A drop, 5 A S4 | yes | **no** (0 of 400) |
| Option C, all three holders | 10 A, 5 A drop, 5 A S4 | no | **no** (0 of 400) |
| **10 A replaces S4** | 10 A, 5 A drop | yes | **no** (0 of 400) with the assumed 16 × 11 holder; with a holder our size (15 × 10 × 38) it is today's case, only just |
| **10 A replaces S4, no break** | 10 A, 5 A drop | no | **yes, 61 of 400** |

**Honestly: the neck is crowded now.** Three holders plus a splice plus a plug break is too much for it.

## 2. Where the 10 A holder sits, and how it's held

- **Position:** standing along the neck, its body in Y 251-290: **12 to 51 mm below the hub seat** (our end face, Y 302).
  - The example layout has it on the back half's side of the cavity (X 164, Z -11), beside the bundle.
  - Its upper pigtail runs up with the trunk into the hub's bore. The lower one runs down with the trunk past the tie bridge.
    The bends are gentle S-offsets of about 10 mm over the pigtail's length, at R 11.5 or more.
  - Not in the hub's bore.
- **Fixing, with no change to the halves:**
  - Two 2.5 mm cable ties lash the holder body to the trunk bundle, one at each end.
  - The bundle is tied, as now, through the existing tie bridge's slot (R1h back half, -X wall, Y 255-261).
  - The bridge's slot takes only one tie, so the holder hangs on the bundle, not on its own tie.
  - Pulling the fuse: hold the holder body in one hand. The pull goes into the bundle's ties, not up the wires into the hub.
  - If a dedicated fixing is wanted later: a printed clip that snaps onto the tie bridge bar. It is a separate part, so the halves
    don't change.
- **The pair's length from the hub's tunnel to the holder is fixed.** The bundle is tied in the hub's bore (the shoulder's tie to
  the screw tube) and at our bridge. The hub is bolted to the yaw RS02's output, so both ties turn with the arm, and nothing between
  them moves when the arm yaws. All the yaw take-up is in the shoulder's cable space.

## 3. Reach: the front half really does come off with the arm on the robot

- **What comes out:**
  - The 2 seam screws (M3, driven from the back half).
  - The 2 hub lug bolts (along Z at Y 292, heads on the back posts).
  - All four are reached from behind the arm (-Z).
  - Then the front half lifts off straight forward (+Z), clear of the hub's groove.
- **The fork skirt, from the adopted shoulder (roark 2e57336, moved 3.00 mm into our frame):**
  - Its lowest point anywhere within r 80 of the yaw axis is Y 317.5: **16.2 mm above the halves' top (Y 301.3)**.
  - The fork rear stays at Z -33 or further back and above Y 343, far from the lug-bolt and seam-screw tool paths.
  - So the 3 mm longer skirt doesn't block the front half or the tools.
- **The catch: support the forearm while the front half is off.** With the lug bolts out, the back half (carrying the elbow
  RS02 and the forearm) hangs on the hub by its half of the ridge only. It is free to drop backward (-Z). Rest the forearm on
  something, or have someone hold it.

## 4. The fuse logic (the trunk README, marengo `hardware/electrical/wiring/left-arm-trunk/README.md`)

- **Today's scheme:**
  - 16 AWG trunk down to M14, 18 AWG from M14 to M15. The board's port trips at 15 A.
  - The **5 A S4 segment fuse at M14** is there because the trunk steps down to 18 AWG there, and 15 A is too much for it.
  - The **5 A M14 drop fuse** is the elbow RS02's own (one fuse per drop, Joey's rule).
- **Under option C:**
  - The arm is 18 AWG from the shoulder's splice (Joey, 2026-11-15), and the 10 A fuse sits above everything in the arm.
  - Every 18 AWG conductor below it, S4 included, is then protected at 10 A. **So the S4 segment fuse is no longer needed to
    protect wire**, and the 10 A can take its place.
  - The M14 drop fuse stays.
- **What S4's own fuse still gave, for the power thread to weigh:**
  1. Selectivity: a fault in S4 itself (the elbow crossing, the most-flexed wire in the arm) would blow the 10 A and take the
     elbow RS02 down with it, instead of the forearm only. Faults in the forearm's drops are still cleared by their own 3 A fuses.
  2. Heat: in option A3, S4 is coiled under the inboard elbow cap. Up to 10 A in a coil runs warmer than up to 5 A.
- **18 AWG below the elbow: yes.** S4 is one 18 AWG pair (settled 2026-11-15; the elbow cable rig uses it). If the S4 fuse is
  dropped, S4 must stay 18 AWG: 20 AWG behind a 10 A fuse is not acceptable. The forearm's drops (RS00 3 A, the hand 3 A) are
  fused at their own value.

## 5. What a fuse change takes, by variant

| Variant | Where the fuse is | To change it |
| --- | --- | --- |
| A | the shoulder's cavity behind the yaw RS02 | strip the fork rear (the shoulder thread's "strip-down") |
| B | no separate fuse | nothing to change; the board's 15 A port trip protects |
| C, 10 A replaces S4 (recommended if C) | our neck, with the M14 drop fuse | support the forearm; out with 2 seam screws and 2 lug bolts from the back; front half off; swap the fuse; refit. About 10 minutes. The same as any of our neck fuses today. |
| C, all three holders | doesn't fit without changing the halves | - |

All the neck fuses come out the same way. There is no hatch: adding one would change the halves, and the front half is the
cover the trunk README asks for.

## 6. The plug break (our earlier request 2)

- Today it fits only just. With the 10 A in the neck, it fits only if the holders are no bigger than our assumed 15 × 10 × 38.
- If it has to go, removing the arm means unsoldering at M14 again. That is the price of option C in our neck, unless:
  - the holders bought are small enough, or
  - the plug break moves upstream, into the shoulder (the shoulder thread's call).

## 7. For Joey and the other threads

1. **Power thread:** is S4 OK at 10 A (one 18 AWG pair, coiled in A3)? If yes, the 10 A replaces the S4 segment fuse and option
   C fits in our neck.
2. **Joey:** measure the 58 V-rated MINI holder you buy. At 15 × 10 × 38 or less, the plug break can stay too.
3. **Shoulder thread:** a 70 mm straight pocket doesn't exist here. The holder body stands in Y 251-290 and its pigtails follow
   the trunk.
4. **Arm (us):** nothing to change in the halves. Option C in our neck needs no reprint.
