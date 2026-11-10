# Order package: 12 V buck board, rev B5

Made by [tools/fab_package_buck.sh](../tools/fab_package_buck.sh) from
[layout/marengo_buck12.kicad_pcb](../layout/marengo_buck12.kicad_pcb). It is checked against that board by
[tools/fab_check_buck.sh](../tools/fab_check_buck.sh), with the result in [CHECK.txt](CHECK.txt). `BOARD.sha256` is the
board file's hash, and verify_buck.sh fails if the package is older than the board. **Nothing has been ordered or
uploaded.**

It goes in the same order as the main board (../../fab), as a second design with the same options.

## What to give the fab

Upload `marengo_buck12-gerbers.zip` (the 14 files of `gerbers/`). On the order form:

| Item | Value |
|---|---|
| Board size | 60 × 85 mm, 1 design, no panel |
| Layers | **6** |
| Thickness | 1.6 mm |
| Copper | **2 oz outer, 0.5 oz inner** |
| Surface finish | **OSP** |
| Via covering | **Epoxy filled and capped (IPC-4761 type VII), all vias.** 28 of the 139 vias are in SMD pads (the GND pads of the input ceramics, C1, C2, C24 and D3, Q1's drain tab, the shunts' four sense pads, TPV6), plus U1's four 0.2 mm thermal vias in its exposed pad (JLC fills 0.15-0.55 mm). Drills: 0.3 mm (139 vias), 0.2 mm (4, U1's exposed pad), 1.02 mm (24 connector pins) |
| Smallest drill | **0.2 mm** (the four in U1's exposed pad; JLC's 6-layer minimum is 0.15 mm) |
| Solder mask | both sides, any colour; no openings drawn on the bottom |
| Silkscreen | top only; the bottom file holds only the bottom mask openings plotted clear and prints nothing |
| Minimum track / space | **0.2 mm / 0.2 mm**; via 0.6/0.3 mm; inner-plane clearance 0.3 mm |
| Stack | L1 parts and power pours, L2 GND plane (under the hot loop), L3/L4 signals and GND fill, L5 GND plane, L6 mirrors of VIN_P, VIN and VOUT and GND fill. The same stack as the main board |
| Stencil | frameless, top side, from `gerbers/marengo_buck12-F_Paste.gtp` |
| Electrical test | flying probe, 100 % |

## Files

| File | What |
|---|---|
| `gerbers/*` | 12 Gerbers (L1–L6, both masks, both silkscreens, top paste, outline) and the PTH / NPTH Excellon files |
| `marengo_buck12-gerbers.zip` | the 14 files above |
| `marengo_buck12-pos.csv` | centre, rotation and side of all 73 parts (all top side). The board is hand-assembled; this is for a quote or as a placement aid. The six Micro-Fit headers are in it but are soldered by hand |
| `bom-jlc.csv` | Comment, Designator, Footprint, Quantity for the 73 parts |
| `bom-digikey.csv` | the buck rows of [kit-2sets.csv](../../kit-2sets.csv): quantities for two sets with spares, manufacturer and DigiKey part numbers, supplier notes. The mating plugs are in the kit's assembly rows ([SOURCING.md](../../SOURCING.md) for lines DigiKey could not supply) |

Open the zip in a Gerber viewer before paying.
