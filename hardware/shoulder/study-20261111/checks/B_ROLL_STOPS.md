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
