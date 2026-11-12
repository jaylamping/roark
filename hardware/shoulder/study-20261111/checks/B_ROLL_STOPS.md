# Check (b): roll stops at the stop torque (2026-11-12)

**Geometry** (`dims.STOP_SLOT`, `build_fork_rear` `STOP_TOOTH`, `build_cap` `STOP_RING` / `STOP_SLOT`):

- **Tooth** (fork rear):
  - A sector r 27-33, ±10° about 193°, with 0.8 mm corners.
  - It stands on the housing's front face at Z -41.8 and reaches Z -33 (8.8 mm).
  - Root section: 6 mm radial × 10.5 mm tangential (mean of 9.4 at r 27 and 11.5 at r 33). Area 63 mm²; bending modulus
    6 × 10.5² / 6 = 110 mm³.
- **Slot** (rear cap): r 25-35, from the cap's rear face (Z -39.3) to a floor at Z -31, with 2 mm all round the tooth.
  - At either stop (-11 / +110), the tooth's flat flank meets the slot's flat end wall.
  - The contact is Z -39.3…-33, 6.3 × 6 = **38 mm²**, centred at r 30.
  - The lever from the tooth root to the contact centroid is 5.65 mm.
- **Print directions:**
  - The fork rear prints upright: layers normal to Y. At 193° the stop force is 97% along Y, so it pushes across the
    tooth's layers. The tooth's bending stress (along Z) lies in the layer plane. The transverse shear acts on the layer
    planes.
  - The cap prints front face down: layers normal to Z. The wall load lies in its layer plane.
- **Strengths:** as check (a). PETG bulk 45 MPa; across or along layers in shear 22.5 MPa.

## Loads

| Case | Roll torque | Force at r 30 |
|---|---|---|
| Arm weight at the stop (1.32 kg distal, about 0.2 m lever, arm well out) | about 2.6 N·m | 87 N |
| RS03 driving into the stop at its rated torque (about 20 N·m, assumed: not in the files) | 20 N·m | 667 N |
| RS03 stalled into the stop at its peak torque (about 60 N·m, assumed, the same figure the front-blend check used) | 60 N·m | 2000 N |
| Uncontrolled hit at 2 rad/s (arm about 0.06 kg·m² about the roll axis, 0.12 J; stop stiffness about 1.5 kN/mm at r 30) | equivalent 18 N·m | about 600 N |
| Uncontrolled hit at 5 rad/s (0.75 J) | equivalent 45 N·m | about 1500 N |

The stop stiffness is a rough estimate. The tooth alone is about 4.7 kN/mm in shear plus bending; the cap wall, fork
rear arm and 6808 add compliance. The hit forces scale with the square root of the stiffness.

## Results (hand calculation, tooth as a short cantilever; conservative for bending at this L/h = 0.54)

| Case | Tooth bending σz (in layers) | Bulk SF | Shear across layers τ = 1.5F/A | Layer SF | Wall bearing | SF (45) |
|---|---|---|---|---|---|---|
| Arm weight | 4.5 MPa | 10 | 2.1 MPa | 11 | 2.3 MPa | 20 |
| 20 N·m / 2 rad/s hit | 34 MPa | **1.3** | 16 MPa | **1.4** | 18 MPa | 2.5 |
| 60 N·m stall | 103 MPa | **0.44** | 48 MPa | **0.47** | 53 MPa | **0.85** |
| 5 rad/s hit | 77 MPa | 0.58 | 36 MPa | 0.63 | 40 MPa | 1.1 |

## What it means

- **The stops are a backup to the software limits, not a full-torque hard stop.**
  - They carry the arm's weight easily.
  - They carry a rated-torque push or a slow (about 2 rad/s) uncontrolled arrival with SF about 1.3.
  - A peak-torque stall or a fast hit breaks the tooth. Shear across its layers goes first, then the cap's wall bearing.
- **Required in the controller** (this goes to the software project):
  - roll soft limits 2-3° inside the stops (-8…-9 and +107…+108)
  - torque limited to about 10 N·m within 5° of either stop
  - speed limited to about 2 rad/s near the stops.
- **Options if a full-torque hard stop is wanted:**
  1. **Wider tooth:** ±16° instead of ±10° (16.8 mm tangential). Bending modulus 282 mm³. At 60 N·m: σ 40 MPa (bulk SF
     1.1), layer shear 30 MPa (SF 0.75). It still does not carry a 60 N·m stall, but its rated-torque SF becomes 3.3 / 1.9.
     - The slot gets 12° longer. The stop angles are unchanged; they are driven by `ROLL_STOP_IN` / `ROLL_STOP_OUT`.
     - It needs a check against the cap's screw bosses and windows before adopting.
  2. **A steel core:** a Ø4 × 12 dowel through the tooth along Z, pressed into the housing face. The steel carries the
     shear (over 6 kN), and the PETG only bears.
     - The cap wall still crushes at about 53 MPa under a 60 N·m stall. Doubling the contact height (a slot 6 mm deeper
       into the drum side) would bring it to about 27 MPa.
  3. **Both,** for a stop that survives a stall with SF about 1.5. That costs a deeper cap, about +6 mm of drum length,
     which isn't available without moving the cap.
- **Recommendation:** keep the tooth as is, put the limits above in the controller, and widen the tooth to ±16° in the
  next cap/fork-rear revision. It is cheap and roughly triples the rated-torque margin.
- **Not analysed:** fatigue from repeated stop contacts; contact stress concentration at the 0.8 mm corners (the flank
  meets flat-to-flat, so it is small); FEA of the tooth root (the hand calculation over-predicts bending for a tooth this
  short, so it is conservative).

## Rev 2 proposal: a hard stop that carries a peak-torque stall (2026-11-12, not applied)

Joey chose a **hard** stop at -11° inward, and the frame clears only because of it. So the stop has to carry the motor,
not just back up the software.

**Motor figures (vendor manual):** RS03 User Manual rev 261013, §1.3 "Electrical characteristics" (printed page 10; in
jaylamping/marengo `hardware/docs/robstride/RS03_User_Manual_261013.pdf`):
- rated load 20 N·m (tested at 100 rpm)
- peak load 60 N·m
- no-load speed 200 rpm (21 rad/s)

The crate's §4.1.13 limit table (limit_torque 0-60) agrees with the peak.

**Targets:**
- SF ≥ 1.5 (bulk and layer) at 20 N·m and at a 2 rad/s uncontrolled hit
- SF ≥ 1.0 at a 60 N·m stall

### The lever that matters: load the tooth in its layer plane

- The fork rear prints upright (layers normal to Y).
- **Today:** the tooth sits at 193°. Its load is 97% along Y, so the root's transverse shear runs across the layers
  (layer SF 0.47 at a stall).
- **At 270°** (straight below the roll axis) the tooth's radial direction is -Y. Its bending stress (along Z) and its shear
  (Z-X) then both lie in the layer plane, so bulk strength applies to both.
- **A second tooth is not possible.** A second slot at 90°, or anywhere else 144° long, would cross the cap's cable spoke
  at 106-164° (`TRUNK_ANG` 135°, 32.8 wide, carrying the 16 × 6 and 10 × 5 channels). There is no room for two
  non-overlapping slots.

### Options (hand calculation, as above; lever 5.65 mm from the root to the contact centroid, contact height 6.3 mm)

| | Tooth | Mean r | Section b × h | Peak 60 N·m: force | Bending σ / SF | Shear τ / SF (von Mises) | Cap wall bearing / SF | Rated 20 N·m: lowest SF |
|---|---|---|---|---|---|---|---|---|
| Now | r 27-33, ±10°, at 193° | 30 | 6 × 10.5 | 2000 N | 103 / 0.44 | 48 / **0.47 (across layers)** | 53 / 0.85 | 1.31 |
| A | r 30-40, ±11.5°, at 270° | 35 | 10 × 14.0 | 1714 N | 29 / 1.53 | 18 / 1.42 | 27 / 1.65 | 3.7 |
| **A2 (best printed-only)** | **r 30-40, ±14°, at 270°** | 35 | 10 × 17.1 | 1714 N | **20 / 2.27** | **15 / 1.73** (1.50 even read as across layers) | **27 / 1.65** | **≥ 4.5** |

**2 rad/s hit:**
- The arm is about 0.06 kg·m² about the roll axis, so the hit carries 0.12 J. That is 600-980 N at r 35 for a stop
  stiffness of 1.5-4 kN/mm, i.e. 21-34 N·m equivalent.
- A2 at 34 N·m: lowest SF about 2.9.

### A2 in detail

- **Tooth** (fork rear): a sector r 30-40, ±14° about fork angle 270°, 0.8 mm corners, from the housing face (Z -41.8)
  to Z -33.
  - It needs a pad on the housing outside its r 33: a sector r 33-42 over ±24°, Z -41.8…-45.9.
  - Printed upright, the tooth's outer face (r 40) faces down: a small removable support under it. That face carries no
    load. The two contact flanks are vertical.
- **Slot and ring** (rear cap):
  - Slot r 28-42 (2 mm all round), floor at Z -31 as now.
  - Ring r 26-44 on the plate, 20° past each slot end, so the end walls have 20° of ring behind them. Shear-out over that
    footprint across the cap's layers: 14 MPa, SF 1.6.
  - Clear of the cap screw bosses (r 45-55 at 0°, 180°, 270°) by 3 mm, and of the spoke (106-164°): the slot runs
    245°…34°.
  - The old slot and ring at 193° go.
- **Travel:** -11…+110 unchanged (still driven by `ROLL_STOP_IN` / `ROLL_STOP_OUT`). The slot is 149° of arc instead of 141.
- **Mass:** about +5 g in total (tooth +1.2, housing pad +1.5, cap ring +2.5 net).
- **Not checked yet:** the swept tooth against everything inside the drum over the full travel. The slot depth and floor
  are as now, so only the larger radius is new.

### With a pin

- **Variant:** A2 plus a Ø5 × 20 hardened dowel (h6, about 0.15 each) through the tooth along Z, pressed 11 deep into
  the housing pad.
- The steel takes the root bending and shear, at SF over 5.
- But the PETG then bears on the pin inside the tooth: 1714 / (5 × 8.8) = 39 MPa at a stall, SF 1.15. That becomes the
  weak point, lower than A2's printed root (1.73).
- **Verdict:** the pin is not worth it. A2 printed-only is the recommendation.

**Recommendation:**
- Adopt A2 in the next cap and fork-rear revision.
- Keep the controller limits from above as a second layer: they cost nothing.
- FEA of the A2 tooth root and cap wall once it is modelled; the hand calculation is conservative for bending at this
  L/h.

## A2 built and checked by FEA at the 60 N·m stall (2026-11-12)

**Built into the real parts** (`dims.STOP_SLOT`, approved):
- tooth r 30-40, ±14° at fork angle 270°
- pad on the housing: r 33-42, ±24°, between the housing face and the joint plane
- cap slot r 28-42, centred at 319.5°, 149° of arc
- ring r 26-44, 20° past each slot end
- Masses: cap 85.2 g (+0.7), fork rear 72.5 g (+2.1, which includes the 6808 changes)
- **Outside the outline:**
  - Nothing new is proud of the skin.
  - The pad sits in the 4 mm gap between the cap's rear face and the fork rear, below the axis and within the arm's
    width (X ±17). Seen from the side through that gap, it reads as the arm reaching 4 mm closer to the cap.
  - The cap's slot opening on its rear face now reaches r 42 (was 35). That face is behind the fork rear. Its outer
    part (r 35-42) shows through the same gap only where the fork rear's r 35 cheek doesn't cover it.
- **The software limits stay** as a second layer: roll soft limits 2-3° inside the stops; torque about 10 N·m and speed
  about 2 rad/s within 5° of either stop.

**FEA:** linear static, PETG as before, 1714 N (60 N·m at r 35) as a normal force on the contact flank. Mesh 1.5 mm,
0.5 mm on the tooth, slot and pad.

| Case | Hold | Where | Bulk vm peak / 1 mm avg | SF peak / avg | Layer stress peak / 1 mm avg | Layer SF peak / avg |
|---|---|---|---|---|---|---|
| `STOP_A2_CAP` | 3 × M3 holes and the front face on the drum | slot end wall and floor edge | 43.6 / 21.0 | **1.03 / 2.14** | σz (cap layers) 18.2 peak | **1.24** |
| `STOP_A2_TOOTH_J` | the 2 joint screws to the fork front, and the 6808 seat radially | tooth root (outer flank corner) | 104.8 / 51.9 | 0.43 / **0.87** | σy 83 / 15 | 0.27 / 1.5 |
| | | pad edge at r 42 (where it meets the leg) | 125.3 / 64.6 | 0.36 / **0.70** | | |
| | | rear leg at Y 390 (narrowest, round the cable channel) | 85.8 / 76.2 | **0.59** | σy 46 / 37 | 0.61 |
| | | joint-screw zone (X ±17, Y 357) | 72.3 / 58.9 | 0.76 | σy 80.5 / **58.1** | **0.39** |

(`STOP_A2_TOOTH`, held over the fork rear's whole front face, is not used: that face runs under the pad, so it put an
artificial fixed edge at the pad.)

### What the FEA shows that the hand calculation did not

- **The cap is fine.** At a 60 N·m stall it meets SF ≥ 1.0, bulk and layer.
- **The tooth is close.** Its own root is 0.87 at the 1 mm average. A 1.5 mm root fillet, and blending the pad into the
  leg instead of ending it at r 42 with a corner, should bring the tooth and pad to ≥ 1.0. (The hand calculation took
  the tooth alone, with no root notch.)
- **The real limit is the torque path.** At the stop, the full motor torque runs RS03 → fork front → the 2 × M4 joint →
  the fork rear's leg → tooth → cap.
  - The fork rear is the only roll-side part next to the cap, so any stop on the cap puts the fork rear and its joint in
    this path.
  - The leg at Y 390 (narrowest, round the cable channel) reaches 76 MPa at the 1 mm average: SF 0.59.
  - At the two joint screws the stress runs across the layers: σy 58 MPa at the 1 mm average, layer SF 0.39.
  - Two screws 34 mm apart carry a 60 N·m couple as about 1.8 kN each, along Y, which is across the layers.
- **At the rated 20 N·m** (a third of these stresses):
  - tooth 2.6, pad 2.1, leg 1.8, cap ≥ 3
  - joint-screw zone layer SF **1.16**: short of the 1.5 target

### Options for the torque path (for the coordinator; not applied)

1. **Strengthen the joint.**
   - Four M4 instead of two, on a wider span: add two at Y about 345 under the sleeve's ring top, if the r 47 sleeve is
     taken. Spread the bosses so the couple arm grows from 34 to about 60 mm. That roughly halves the per-screw load.
   - Add two printed shear keys (bosses on the fork front's pad engaging pockets in the fork rear) that carry the couple
     in bearing in the layer plane.
   - Expected joint layer SF: about 1.0 at a stall, about 3 at rated.
2. **Thicken the leg at Y 380-395** round the cable channel (a 2.4 mm wall now). A +2 mm wall each side raises its
   section modulus about 1.8 times: SF about 1.05 at a stall. It changes the back profile slightly.
3. **Accept stall protection from the controller** (a torque limit of 25 N·m or less near the stops). The stop then has
   SF ≥ 1.5 everywhere at rated torque once option 1 is in, and the stall case is a firmware duty, written in the
   software project's requirements.
- **My recommendation:** 1 + the root fillet and pad blend, plus the controller limit as the second layer. Option 2 only
  if Joey wants the stop to survive a stall on its own.

### Option 4 (a stop on the motor side, so the fork joint is out of the path): checked, dropped

- **The idea:** a fixed lug on the drum's front lip (Z 28.3-36, r 43-56), engaging an arc groove in the fork front's back
  face (Z 39 → 44), right beside the RS03 output.
- **Why it doesn't fit:**
  - **Groove window.** The fork front's two RS02 access bores (Ø7, at X +16 and -8.8, running up through the cheek)
    cross the groove's radius band (r 42-53) at ±67.6…72.4° and ±99.6…102.1° about the roll axis. Keeping 2 mm of wall
    to them leaves one window, 109.6°…250.4°: 140.8°. The groove needs 121° of travel plus the lug width plus 2 × 2 mm.
  - **Lug strength.** The drum prints with its axis vertical (layers normal to Z). A lug standing up in Z and loaded
    tangentially bends across its layers.
    - At the only width that fits (15°): layer SF 0.49-0.71 at a 60 N·m stall.
    - Lugs strong enough (20° at 6 mm high: layer SF 1.27; 25°: 1.98) need 146-151° of groove, which don't fit.
  - **The reverse** (a tooth on the fork front, a groove in the lip): the lip's 8 × M4 counterbores at r 49 leave only
    33.8° of free arc between them.
  - Inside r 43 is the RS03's own face, which can't be cut.
- So the stop stays on the cap, and the fork joint stays in the torque path. Option 1 follows.

## FOR SOFTWARE: roll-joint limits near the hard stops (required, all options)

The printed stops at -11° and +110° are hard stops: the frame clears only because of the inward one. The controller
keeps them inside their rated duty. These numbers go to the software project (roll joint, RS03, left shoulder; mirror
them for the right).

| Item | Value | Why |
|---|---|---|
| Soft position limits | **-9° … +108°** (2-3° inside the stops) | The stops are only touched in a fault or on purpose |
| Torque limit within 5° of either stop (-11…-6° and +105…+110°) | **≤ 17 N·m** | Gives layer SF ≥ 1.5 in the fork rear's leg, the pad junction and the joint on the current parts (SF 1.32-1.37 at 20 N·m in the FEA, scaling linearly) |
| Speed limit within 5° of either stop | **≤ 1 rad/s** | A 1 rad/s arrival is about 10-17 N·m equivalent at the stop (arm about 0.06 kg·m² about the roll axis); 2 rad/s would be 21-34 N·m |
| Outside those zones | the RS03's own limits (60 N·m peak, 20 rad/s; manual 261013 §1.3 and §4.1.13) | |

- These hold whatever is decided for the printed stop. They are the second layer even if the leg2 version or a stronger
  joint is adopted.
- **Whether the printed stop must survive a full 60 N·m stall** (needing more mass and outline than leg2), or whether a
  stall is the controller's job with the printed stop good for rated torque, is Joey's call.

