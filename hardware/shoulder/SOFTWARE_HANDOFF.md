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
