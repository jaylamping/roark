# Order package: main power board, rev B5

Made by [schematic/tools/fab_package.sh](../schematic/tools/fab_package.sh) from
[layout/marengo_pdu_revb.kicad_pcb](../layout/marengo_pdu_revb.kicad_pcb) and checked against it by
[schematic/tools/fab_check.py](../schematic/tools/fab_check.py) (result in [CHECK.txt](CHECK.txt); `BOARD.sha256` is the
board file's hash, and verify_board.sh fails if the package is older than the board). **Nothing has been ordered or
uploaded.** Order steps and prices: [PRODUCTION_RUN.md](../PRODUCTION_RUN.md), section 8.

## What to give the fab

Upload `marengo_pdu_revb-gerbers.zip` (the 14 files of `gerbers/`). On the order form:

| Item | Value |
|---|---|
| Board size | 100 × 170 mm, 1 design, no panel |
| Layers | **6** |
| Thickness | 1.6 mm |
| Copper | **2 oz outer, 0.5 oz inner** |
| Surface finish | **OSP** |
| Via covering | **Epoxy filled and capped (IPC-4761 type VII), all vias.** 971 of the 1,865 vias are in pads (the FET tabs' heat path, the power GND pads, the bare heatsink pads). If the form asks per drill size: 0.3 mm (1,862 vias) and 0.5 mm (2). The board setup says capping and filling yes, but the Gerbers do not carry it |
| Solder mask | both sides, any colour. **The ten large openings on the bottom (B.Mask) are intended:** bare copper pads for the heatsink's gap pad, each inside one FET's drain copper. Answer "keep as designed" if asked |
| Silkscreen | top only carries text; bottom is empty |
| Minimum track / space | **0.2 mm / 0.2 mm** (the fab's minimum for 2 oz outer copper); smallest drill 0.3 mm, smallest via pad 0.6 mm; inner-plane clearance 0.3 mm (0.25 mm at the VBUS pours on L3/L4) |
| Stack | L1 parts and power pours, L2 GND, L3 and L4 signals with VBUS pours over the stem, L5 GND, L6 power mirrors and heatsink pads. Ask which prepreg sits between L1 and L2 and put it in schematic/tools/stack.py (the absorber loop was simulated for 0.21 mm and 0.10 mm) |
| Stencil | frameless, top side, from `gerbers/marengo_pdu_revb-F_Paste.gtp` |
| Electrical test | flying probe, 100 % |

## Files

| File | What |
|---|---|
| `gerbers/*-F_Cu.gtl`, `-In1_Cu.g1` … `-In4_Cu.g4`, `-B_Cu.gbl` | copper, L1 to L6 |
| `gerbers/*-F_Mask.gts`, `-B_Mask.gbs` | solder mask (openings) |
| `gerbers/*-F_Silkscreen.gto`, `-B_Silkscreen.gbo` | silkscreen |
| `gerbers/*-F_Paste.gtp` | paste, top (every part is on the top side) |
| `gerbers/*-Edge_Cuts.gm1` | outline |
| `gerbers/*-PTH.drl`, `-NPTH.drl` | Excellon drills, mm: 1,906 plated hits (1,865 vias and 41 pad holes), 12 unplated |
| `marengo_pdu_revb-gerbers.zip` | the 14 files above |
| `marengo_pdu_revb-pos.csv` | centre, rotation and side of the 244 machine-placeable parts (the board is hand-assembled; this is for a pick-and-place quote or a placement aid). 18 more parts are fitted by hand only: through-hole parts, wire pads, test points, the copper link |
| `bom-jlc.csv` | Comment, Designator, Footprint, Quantity for the 262 fitted parts of one board |
| `bom-digikey.csv` | order quantities for two sets with spares, value or manufacturer part number, references; from [kit-2sets.csv](../kit-2sets.csv), which also lists the buck board. Passives are given by value, size and rating, not by a distributor's part number: pick those in the cart |

The Gerber and drill files carry no creation date, so running the script again on an unchanged board gives identical
files.

## What fab_check.py compares

File set and layer functions, six copper layers, the outline (100.00 × 170.00 mm), the drill hits per tool against the
board's vias and pad holes, the ten heatsink openings on B.Mask, the position file and both BOM files against the
board's fitted parts, the zip against `gerbers/`, and the board file's hash. It reads the Gerbers as text (format,
units, end of file, coordinates, X2 file function); it does not render them. Open the zip in a Gerber viewer or the
fab's preview before paying, and look at the bottom mask and the inner layers.
