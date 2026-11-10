# Finishing the rev B5 board

**Nothing is open (2026-11-10).** Every connection is routed and the checks pass. The state, the rule exceptions (G2's via
through the L6 MID mirror among them, still to be confirmed at the review) and the hand-laid copper are in
[LAYOUT_RULES.md](../LAYOUT_RULES.md), "Routing state" and "Exceptions and hand-laid copper".
[open_nets.csv](open_nets.csv) lists what is open: only its header.

## Rules for any further hand edit

- No new vias in the VBUS band, Y 180-190 mm, X 130-160 (18 signal vias are there).
- Don't unlock or drag locked tracks: the port and U8 templates, the gate drives and the Kelvin pairs are locked.
- E-stop nets (ESTOP class) keep 1.5 mm from 54 V copper; the DRC holds it. Inside U1, U2, U7 and U8's courtyards 0.15 mm applies.
- No tracks on In1 or In4, no via in or touching a pad, no via in a MID pour (route_checks check 7 lists the allowed ones).

## Checks

From `hardware/power-board/schematic` (KiCad's Python as `$KP`):

```
OPEN_MAX=0 bash tools/verify_board.sh   # DRC with schematic parity, open nets, route_checks, check.py; exit 1 on a failure
"$KP" tools/pour_width.py ../layout/marengo_pdu_revb.kicad_pcb   # narrowest VBUS and MID cross-sections
```

verify_board.sh copies the board next to the schematic before the DRC. Run in layout/, KiCad's parity check only prints
"Failed to fetch schematic netlist" and checks nothing.

Done means: DRC shows no violations, `unconnected 0`, `parity 0`; route_checks shows 0 in checks 1/2 and 4 to 8; check.py
shows `FAILS 0`. Then re-render (`tools/render_export.py`, `tools/render_routed.py`) and commit the board,
open_nets.csv and the renders.
