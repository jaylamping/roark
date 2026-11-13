# Shoulder: what the software must enforce (2026-11-13)

These limits come from the hardware checks. The printed parts were sized assuming the controller enforces them, so they
are part of the design, not tuning suggestions. They are written for the left shoulder; mirror them for the right
(roll and yaw angles change sign with the mirror, the values stay the same).

## Roll joint (RS03): soft limits and torque near the hard stops

| Item | Value |
|---|---|
| Soft position limits | -9° to +108° |
| Within 5° of either stop (-11° to -6° and +105° to +110°) | torque at most 17 N·m, speed at most 1 rad/s |
| Elsewhere | the RS03's own limits (60 N·m peak, 20 rad/s) |

**Why:**
- **The stops are printed.** The hard stops at -11° and +110° are part of the printed fork. They are good to the rated
  20 N·m, not to a full 60 N·m stall.
- **Joey's decision (2026-11-13):** the parts stay as built, and the controller is the stall protection.
- **The soft limits** keep the stops for faults and deliberate homing.
- **The 17 N·m cap** keeps the printed fork above its strength target (layer safety factor 1.5).
- **The 1 rad/s cap:** an arrival at 1 rad/s is about 10-17 N·m equivalent at the stop, and 2 rad/s would be 21-34 N·m.

Source: [B_ROLL_STOPS.md, "FOR SOFTWARE"](study-20261111/checks/B_ROLL_STOPS.md).

## Yaw joint (RS02): zero offset, connector, torque

- **Zero offset:**
  - The RS02 is mounted turned +40° from its original clocking, so its power and CAN plug fits inside the fork front.
  - The yaw joint's zero therefore carries a **+40° offset** against the motor's own zero.
  - Set it once in the joint configuration; the hardware has no other reference for it.
- **Connector:**
  - The RS02's XT30(2+2) socket at **228°** (in the fork front's frame) is the one in use.
  - The second socket, at 48°, is capped and must stay unused (one connector per motor, robot-wide).
- **Torque limit:**
  - Yaw torque must not exceed the RS02's **17 N·m** peak.
  - That peak is the design load of the hub's two lugs, which carry the yaw torque into the arm: 304 N per lug at 17 N·m.
  - The hub meets its strength target at that load with some margin, and at the conservative 370 N per lug. No margin is
    left for anything above the motor's own peak.

Sources:
- [CAD_NOTES.md, "RS02 re-clocked +40°"](study-20261111/cad-pass1/CAD_NOTES.md)
- [PRINT_NOTES.md, "RS02 plug and clock"](study-20261111/cad-pass1/PRINT_NOTES.md)
- [A_HUB_LUGS.md, yaw torque through the lugs and rev D3c4](study-20261111/checks/A_HUB_LUGS.md)

## Yaw joint: position limits (provisional)

| Item | Value |
|---|---|
| Soft position limits | **-85° to +85°, assumed.** Joey has not fixed the yaw travel yet |
| Rule | **Never enable yaw without a position limit** |

**Why:**
- **Nothing stops yaw mechanically.** The shoulder has no yaw hard stop.
- **A runaway winds the cable.** The arm's wires cross the joint in a flat loop under the RS02. Past about +130° (with
  the hub's cable window at 68°) the loop is pulled tight; past +166° the window passes the fork's exit and the bundle is
  wrapped. On the other side it wraps at about -194°.
- **The zero must be right first.** A yaw zero that is off by the +40° offset, or by a 60° step of the hub's screw
  pattern, eats most of the margin. Set and check the zero before the first enable.
- The design was checked for yaw -90° to +90° only.

Sources: [OPEN_ASSUMPTIONS.md, items 1 and 2](study-20261111/checks/OPEN_ASSUMPTIONS.md);
[CABLE_LOOP_RIG.md](study-20261111/checks/CABLE_LOOP_RIG.md).

## All three motors: temperature limits (provisional until a bench run)

| Motor | Start reducing torque at | Stop (hold position at low torque, or disable) at |
|---|---|---|
| RS03, pitch and roll | **50 °C** reported motor temperature | **60 °C** |
| RS02, yaw | **50 °C** | **60 °C** |

**Why:**
- **The motors sit in printed PETG.** PETG creeps from about 60 °C, and the joints are clamped at only 0.3 N·m, so a
  warm seat lets them go loose.
- **The drive does not protect the plastic.** Its own over-temperature fault is at a thermistor reading of 135 °C (RS02)
  and 145 °C (RS03).
- **The rated torque assumes a metal heat sink.** RobStride rates the RS02 at 6 N·m on a 260 × 280 mm aluminium plate and
  the RS03 at 20 N·m on a 215 × 220 mm plate. In PETG the continuous torque is lower, by an amount nobody has measured.
- **Where the numbers come from:** the seat cannot be hotter than the winding that heats it. Holding the reported
  temperature to 60 °C therefore holds the seat under 60 °C. That is safe but probably too strict; the bench run below
  measures the real difference so the limits can be raised.
- Ambient range of the drives: -20 to 50 °C.

**Bench run to replace these numbers (Joey):**
1. Tape a thermocouple to the printed seat, on the plastic, right beside the motor's mounting face: for an RS03, on the
   boss next to a mounting screw; for the RS02, on the fork front's seat ring between two of the M3 screws. Tape a second
   one in free air.
2. Hold a steady torque with the joint still: start at a quarter of the rated torque (RS03 5 N·m, RS02 1.5 N·m), using a
   weight on a measured lever.
3. Log every 10 s for 30 min, or until it settles: the drive's reported temperature, both thermocouples, the current.
4. Stop at once if the seat reaches 55 °C.
5. Repeat at half the rated torque if the first run settled under 45 °C at the seat.
6. Report: the settled seat and reported temperatures at each torque, and the time to settle. The limits are then set so
   the seat stays at or under 50 °C.

Sources: RS02 user manual 260713 and RS03 user manual 261013, sections 1.2, 1.3 and 3.3
([marengo docs/robstride](https://github.com/jaylamping/marengo/tree/main/hardware/docs/robstride));
[OPEN_ASSUMPTIONS.md, item 3](study-20261111/checks/OPEN_ASSUMPTIONS.md).

## All printed-to-RobStride joints: low preload

- **Torque:** the screws joining printed parts to the RobStride motors are tightened to only **0.3 N·m** (M4), so they
  don't crush the printed bosses.
- **Re-torque:** they need a re-torque **after 24 hours** and **again after the first bench session**, while the plastic
  settles.
- **No threadlocker** is used in testing.
- **For software:** treat a joint that starts to show backlash or position drift against its encoder as a loose joint,
  not a tuning problem.
- **For bench procedures:** include the two re-torque steps.

Source: [PRINT_NOTES.md, "Screws" and "Torque without a torque screwdriver"](study-20261111/cad-pass1/PRINT_NOTES.md).
