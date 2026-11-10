# Finishing the rev B5 board

**One connection is open (2026-11-10): G2**, from Q2 pin 1 (the gate, at 153.2, 160.2) to R2 pin 2 (124.8, 139.3).
Everything else is routed and checked; the background is in [LAYOUT_RULES.md](../LAYOUT_RULES.md), "Routing state".
[open_nets.csv](open_nets.csv) lists what is open.

## G2

Q2's gate pin sits in a 1.7 mm slot between Q1's tab and Q2's own pins. The MID band covers L1 just north of it and the
MID mirror covers L6 under it, so G2 can leave in two ways only, and each breaks a layout rule:

| Way | What it does | Rule it breaks |
|---|---|---|
| a. One via at (149.9, 160.2), then In2/In3 to R2 | 51 mm, 3 vias in the trial; both measured MID and VBUS widths unchanged | no via through a MID pour; gate nets at most 2 vias |
| b. F.Cu north across the L1 MID band | no via | cuts the L1 MID pour (MID must not get narrower) |

A third way needs a placement change: R2 at Q2's gate, as R1 is at Q1's (about 2 x 3 mm that isn't free there now).

To apply way a once it is approved (from `hardware/power-board/schematic`, KiCad's Python as `$KP`):

```
SOFTZ=1 "$KP" tools/lay_path.py ../layout/marengo_pdu_revb.kicad_pcb work/g2a.kicad_pcb "/G2=F:150.9,160.19 149.9,160.19;v:149.9,160.19;3:149.9,160.19 149.9,159.2"
# DRC on work/g2a.kicad_pcb (tools/verify_board.sh work/g2a.kicad_pcb writes drc.json with KEEP=<dir>), then:
G2_VIAS=1 COMPONENTS=1 WINDOW=20 SECONDS=400 "$KP" tools/finish_route.py work/g2a.kicad_pcb work/g2b.kicad_pcb <drc.json> G2
```

## Rules while finishing by hand

- No new vias in the VBUS band, Y 180-190 mm, X 130-160 (18 signal vias are there).
- Don't unlock or drag locked tracks: the port and U8 templates, the gate drives and the Kelvin pairs are locked.
- E-stop nets (ESTOP class) keep 1.5 mm from 54 V copper; the DRC holds it. Inside U1, U2, U7 and U8's courtyards 0.15 mm applies.
- No tracks on In1 or In4, no via in or touching a pad.

## Checks

From `hardware/power-board/schematic`:

```
bash tools/verify_board.sh            # DRC with schematic parity, open nets, route_checks, check.py; exit 1 on a failure
"$KP" tools/pour_width.py ../layout/marengo_pdu_revb.kicad_pcb   # narrowest VBUS and MID cross-sections
```

verify_board.sh copies the board next to the schematic before the DRC. Run in layout/, KiCad's parity check only prints
"Failed to fetch schematic netlist" and checks nothing.

Done means: DRC shows no violations, `unconnected 0`, `parity 0`; route_checks shows 0 in checks 1/2, 4, 5 and 6; check.py
shows `FAILS 0`. Then re-render (`tools/render_export.py`, `tools/render_routed.py`) and commit the board,
open_nets.csv and the renders.
