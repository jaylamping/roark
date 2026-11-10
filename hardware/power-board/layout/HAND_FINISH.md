# Finishing the rev B5 board

**Nothing is open in the routing (2026-11-10).** Every connection is routed and `verify_board.sh` passes. The state,
the rule exceptions and open items (13, among them G2's via through the L6 MID mirror and the latch supply's spacing)
and the hand-laid copper are in [LAYOUT_RULES.md](../LAYOUT_RULES.md), "Routing state" and "Exceptions and hand-laid
copper". [open_nets.csv](open_nets.csv) lists the open connections: only its header.

## Rules for any further hand edit

- No new vias in the VBUS band, Y 180-190 mm, X 130-160 (18 vias of other nets are there; pour_width.py fails on a 19th).
- Don't unlock or drag locked tracks: the port and U8 templates, the gate drives and the Kelvin pairs are locked. Change a
  template in its script (port_copper.py, u8_block.py) and run it with `MODE=sync`; put any other hand-laid copper in
  schematic/tools/hand_laid.specs and lay it with lay_path.py.
- E-stop nets (ESTOP class) keep 1.5 mm from 54 V copper; the DRC holds it. The one exception is inside U1's courtyard,
  between F.Cu pads, tracks and vias, where U1's own UVLO and SH_P pins are 0.2 mm apart.
- Nothing closer than 0.2 mm anywhere (JLCPCB's minimum for 2 oz outer copper); there is no fine-pitch rule.
- No tracks on In1 or In4. No via in or touching a signal pad (the vias in the power pads and under the FET tabs are the
  filled and capped ones). No via of another net in a MID pour, and at most 2 vias on a gate net: route_checks checks 7
  and 8 pin the excepted vias to their coordinates.
- A track must end inside what it joins, not on its edge: joint_check.py fails on a joint with under 0.1 mm of overlap.
- After any change to the B.Cu pours, rebuild the heatsink pad openings (heatsink_pads.py) and the guards (estop_guards.py).

## Checks

From `hardware/power-board/schematic`:

```
bash tools/verify_board.sh      # the whole set; exit 1 on any failure; about 3 minutes
bash tools/verify_selftest.sh   # shows every check failing on a broken copy, then the real board passing; about 10 minutes
```

verify_board.sh copies the board next to the schematic before the DRC (run in layout/, KiCad's parity check only prints
"Failed to fetch schematic netlist" and checks nothing) and refills the zones with the project rules. It fails on every
DRC violation type except the three silkscreen ones on its allow-list, on any open connection, on a schematic parity
item, and on any of: route_checks.py (checks 1 to 10), joint_check.py, the template, U8-block and hand-laid copper
checks, pour_width.py, heatsink_pads.py, check.py and bom_check.py.

Done means `verify_board: PASS`. Then take the refilled copy it wrote (`KEEP=<dir>`, `<dir>/verify.kicad_pcb`) as the
board, re-render (`tools/render_export.py`, `tools/render_routed.py`, `kicad-cli pcb render` for the two 3D views) and
commit the board, open_nets.csv and the renders.
