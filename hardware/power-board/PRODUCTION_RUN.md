# Power system: production run (rev B5)

2026-11-07. One production run of every board, **hand-assembled by Joey**: the fab supplies bare boards and stencils only,
and we buy every part ourselves. Joey wants **2 complete sets** (one in the robot, one spare). The fab minimum is 5 boards,
so 5 + 5 bare boards are ordered and 2 + 2 are built. **All prices are estimates until the carts and fab quotes are run**
(pricing research 2026-11-07, sources in section 5).

## 1. Cost, 2 sets (cheapest route first)

| Item | 2 sets |
| --- | --- |
| Board parts for 2 main + 2 buck, cheapest per line (mostly LCSC, the rest DigiKey or Mouser), with spares on cheap parts | about $200 |
| LCSC shipping (Global Direct or DHL) | about $20 |
| US duty on the LCSC share (China origin, about 37.5 %; LCSC ships duty-unpaid) | about $55 |
| Bare boards, JLCPCB: 5 main (100 × 170, 6 layers, 2 oz outer / 0.5 oz inner, OSP, filled thermal vias: **$82.80 quoted 2026-11-09**, 7–8 day build) + 5 buck (about 60 × 85, 4 layers, 1 oz, to quote: about $20–35) | about $105–120 |
| 2 frameless stencils (JLC) | about $16 |
| JLC shipping, DHL | about $25–45 |
| JLC prepaid duty (US DDP: 35 % on boards, 90 % on stencils) | about $51–57 |
| **Total, 2 sets** | **about $470–515** |
| Heatsink kit, thermal option D (chosen; [THERMAL_OPTION.md](THERMAL_OPTION.md)): 120 × 69 × 36 mm extruded heatsink (no cut), insulating 0.5 mm pad, 2 × M3, 2 sets | about $41–53 |
| Conformal coat (Joey chose coating, 2026-11-09): MG Chemicals 419D acrylic, 55 mL brush bottle, enough for both boards; Kapton tape for masking | about $10 |
| Tools (section 6), one-off | about $110–200 |

**Why this is above the $370–470 estimated earlier:** US duty adds about $105–115 across parts, boards and stencils. JLC's
free ENIG finish ended in July 2026, and 2 oz copper costs extra. Without duty the total is about $365–400. Since
2026-11-09 the main board is 6 layers with 2 oz outer copper (Joey picked it over 1 oz plus copper bars), about $14 under
the 4-layer 2 oz board (JLC quotes, qty 5: 4 layers 2 oz outer $96.47, 4 layers 1 oz $57.67, 6 layers 1 oz $44.00,
6 layers 2 oz outer $82.80).

**The other part-buying routes, 2 sets:**

| Route | Parts landed | vs cheapest |
| --- | --- | --- |
| (C) cheapest per line, LCSC first | about $275–300 | – |
| (B) LCSC for commodity parts + DigiKey for ICs | about $280–300 | about the same |
| (A) everything from DigiKey (one shipment, no duty, $8.49 shipping) | about $375 | **about $80–95 more**, and 6 IC lines are out of stock at DigiKey today (INA237, both LM5069, TPS7A4001, TPS3431, LM5146) |

**Recommendation: route B or C.** The split saves more than the $25 threshold, and DigiKey can't supply six of the ICs
right now anyway. Where both have stock, buy the ICs from DigiKey (no duty, genuine TI) and everything passive from LCSC.

**Levers still open:**
- The main board is 6 layers, 2 oz outer / 0.5 oz inner, OSP (2026-11-09); that is
  already assumed above. OSP is flat like ENIG (fine for the QFN and 0.5 mm pitch parts) but has a shelf life of about
  6 months and tolerates few heat cycles: assemble within a few months of delivery, in one reflow pass plus the
  through-hole step. HASL isn't offered at 6 layers. ENIG is an option at extra cost if the boards will wait.
- PCBWay is about 1.5–2.5 × JLC for 4-layer 2 oz boards (estimate, section 5). JLC is the pick.

## 2. Boards in the run

| Board | Status | Size | Stackup | Parts per board |
| --- | --- | --- | --- | --- |
| **Main power board** ([marengo_pdu_revb](schematic)) | schematic done, ERC clean; routed, 0 open, verify_board.sh passes; open items before fab in [LAYOUT_RULES.md](LAYOUT_RULES.md), "Exceptions and hand-laid copper" | 100 × 170 mm | 6 layers, 1.6 mm, 2 oz outer / 0.5 oz inner, OSP, **every via epoxy-filled and capped** (section 8, step 3) | [bom-rev-B.csv](bom-rev-B.csv) |
| **12 V buck and 12 V distribution** ([buck12](buck12), LM5146, 12 A; split S1 2026-11-09) | schematic done, ERC clean, check_buck.py clean; layout not started | about 60 × 85 mm | 4 layers, 1.6 mm, 1 oz (to quote) | 53 lines, 73 parts |

Not in the run:
- **DVE adapter:** dropped. Since split S1 the buck board carries the 12 V distribution and J24 carries I2C and SP_EN, so the DVE no longer drops in.
- **Pack sense board:** dropped; the BMS sits on the pack.
- **Rev A logic board:** its functions are all on the main board.
- **Arm junction boards:** ruled out.

Both boards are ordered as **two separate designs in one JLC order**, not one panel, so each can be re-spun alone.

## 3. Hand-assembly design rules (applied 2026-11-07)

- **No 0402 parts.** Every resistor and capacitor is 0603 or larger (78 parts moved up from 0402).
- **One part per value and size.** Capacitor value strings are consolidated, e.g. one 100 nF 50 V X7R 0603 line instead of
  four, so the kit has fewer lines.
- **Leadless packages that stay** (no leaded package exists in the family):

| Part | Package | Why it stays | Fit |
| --- | --- | --- | --- |
| TPS259541 (buck U3, U5) | WSON-8 2 × 2 mm, 0.5 mm pitch | the TPS2595 family is DSG-only | hot plate; the hardest part in the run, place it with tweezers under magnification |
| TPS3431S (U25) | VSON-8 3 × 3 mm, 0.65 mm | DRB is its only package | hot plate |
| LM5146 (buck U1) | VQFN-20 3.5 × 4.5 mm | RGY is its only package | hot plate; the buck board is the practice run |
| BSC040N10NS5 / BSC070N10NS5 | SuperSO8 (leads visible) | low-inductance power stage | hot plate |
| TPS7A4001 (U2) | HVSSOP-8 with exposed pad | leaded already | hot plate |

- **Fine-pitch leaded ICs are already in their most hand-friendly packages:** LM5069 (MSOP-10, its only package), INA237
  (VSSOP-10), TPS48100/TPS48111 (VSSOP-19). The 0.15 mm gaps inside the U2 and U7 footprints are footprint geometry, not
  a package choice.
- **Probe pads added** on BAT, SW_D, ABS, CL_D, V_L1–V_L3, PORT_FLT_N, WDO_N and +3V3_PI, on top of the existing GATE,
  GATE_A, UVLO, FLT_A, VCTL, RUN, VBUS, BRK_IN and MID pads and the three GND loops.
- **Thermal relief:** solid connections only where current needs them (the power pads, the FET tabs, the pigtail and pack
  pads); every small-signal pad on a pour gets thermal relief, so it reflows and reworks normally.
- **Every part survives a full hot-plate reflow.** The EEH-ZC/ZA hybrids, the EEE-TK can, the XAL inductors, the shunts
  and the JST GH connectors are all reflow-rated. The through-hole parts (Micro-Fit and Mini-Fit headers, the Keystone
  3568 fuse holder, the pigtails and the 8 AWG pack pair) go on afterwards with the iron.

## 4. Kit list

[kit-2sets.csv](kit-2sets.csv) lists every fitted line for 2 main + 2 buck boards: 175 lines and 864 parts,
counting spares. Spares are about 15 % (minimum 2) on cheap passives, small diodes, small transistors and 1206 fuses only;
expensive parts get none. The off-board parts (BMS, Class T fuse, brake resistors, thermostats, harness) are in the pack
plan and REVB5_CHANGES.

**Part numbers fixed** (2026-11-07, schematic and BOM updated):

| Was | Problem | Now |
| --- | --- | --- |
| TPS48111AQDGXRQ1 | not orderable | TPS48111**L**QDGXRQ1: TI's only orderable TPS48111-Q1 code (datasheet ordering addendum), the same device |
| TPS3431DRBR | doesn't exist | TPS3431**S**DRBR |
| WSK2512R0050FEA (5 mΩ) | wrong Vishay code | WSK2512**5L000**FEA |
| WSK25121L500FEA (1.5 mΩ, 6 ports) | not stocked, and WSK2512 is only 1 W (about 26 A continuous at 1.5 mΩ) | **Bourns CSS2H-2512K-2L00F, 2 mΩ, 5 W at 70 °C**, on the same split-pad Kelvin land. Thresholds kept: RISCP 3.4k → 4.64k (about 40 A short circuit), RIWRN 26.1k → 20k (30 A overload). port_sim: 0 bank trips; latch_sim 0 fails |
| CSS4J-4026R-L500F | it's a Bourns part | text only |
| XAL7030-222MEB | obsolete | XAL7030-222MEC |
| Mini-Fit "5566-02A" | series code | order Molex 39-28-1023 (footprint unchanged) |
| 0466xxx.NR fuses | LCSC carries .NRHF | either is fine |

Biggest lines (2 sets, cheapest source):
- 16 × IPB017N10N5LF: about $51 (LCSC/Rochester) vs $88 at DigiKey.
- 26 × EEH-ZC1K470P: about $13–16 (LCSC) vs about $25.
- 12 × INA237: about $22 (LCSC).
- TPS48111 × 6 + TPS48100 × 2: about $31 + $9.
- 2 × XAL1010-682: about $14 (Mouser).

## 5. Bare boards and stencils, fab comparison (qty 5 each, estimates)

| Fab | Main 100 × 170 (6L 2/0.5 oz OSP since 2026-11-09; this table was for 4L 2/1 oz ENIG) | Buck | Stencil | Shipping to US | Duty |
| --- | --- | --- | --- | --- | --- |
| **JLCPCB** | about $70–100 (2/2 oz on JLC3313: $90–130; 1/0.5 oz: $35–45) | about $45–65 | frameless about $7–9, framed $15–20 (+$15–30 shipping) | DHL about $25–45 | DDP prepaid: 35 % boards, 90 % stencils |
| PCBWay | about $120–180 | about $80–110 | frameless $15–20, framed $25–35 | DHL about $25–40 | duty on arrival |
| Elecrow / AllPCB | no published 4-layer pricing | | | | |

Sources: [JLC copper options](https://jlcpcb.com/help/article/jlcpcb-copper-weight),
[JLC US tariff FAQ](https://jlcpcb.com/help/article/us-tariff-policy-faq) (updated 2026-10-29),
[DigiKey shipping](https://www.digikey.com/en/help-support/delivery-information/delivery-time-and-cost),
[LCSC duties](https://lcsc.com/faqs/shipping-delivering/customs-duties-taxes). The tariff rates (37.5 % aggregate
Section 301 on China-origin goods, de minimis suspended) come from a secondary source; confirm them at checkout. JLC's
online quote tool couldn't be run from here, so run it before ordering.

**Stencils:** frameless, one per design. Tape the stencil down with the spare bare boards around the target board as
height shims.

## 6. Tools

Joey has a good iron with many tips and a low-power hot-air gun. To buy:

| Tool | Pick | About |
| --- | --- | --- |
| **Hot plate**, at least 100 × 170 mm of usable area, enough power for a 6-layer board with 2 oz outer copper | UYUE 946C, 200 × 200 mm, 800 W, set point to about 350 °C ([listing](https://www.fruugo.us/electric-hot-plate-soldering-preheating-station-946c-lcd-digital-display-for-pcb-smd/p-405311245); often cheaper on Amazon or AliExpress, check the 110 V version) | $80–170 |
| **Solder paste** | **Sn63/Pb37, no-clean, Type 4** (e.g. Chip Quik SMD291AX in a jar, or an equivalent from LCSC). Melts at 183 °C, peaks at 210–225 °C | $15–30 |
| Gel flux | no-clean tacky gel flux (e.g. Amtech NC-559 class) | $10 |
| Tweezers | fine, straight and curved, ESD-safe | $10 |
| Kapton tape | 10–20 mm | $5 |
| Squeegee / old card, IPA, brush, magnifier or loupe | | $10 |
| Thermocouple multimeter probe (check the board top, not the plate setting) | | $10–15 |

**Paste: leaded Sn63/Pb37, not low-temperature SnBi.**
- SnBi (138 °C) would make reflow on a heavy board much easier.
- But SnBi joints are brittle and creep at elevated temperature, and this board's FET tabs and shunts run at 70–100 °C on a
  vibrating robot.
- Sn63/Pb37's 183 °C melt is still easy on a 200 × 200 mm hot plate.

## 7. Assembly procedure (per board)

Work on the buck board first; it's the practice run. Inspect and test between every step.

**A. Buck board (warm-up)**
1. Clean the bare board with IPA. Tape the stencil over it, with spare boards around it as shims. Print paste in one firm
   pass, then lift the stencil straight up. Check every pad has paste and none bridged; reprint if not.
2. Place parts with tweezers, smallest first: LM5146, the two TPS259541 eFuses and the two INA237 meters, then the
   resistors and capacitors, the SuperSO8 FETs, the diodes, the WSK2512 shunts, and the inductors and the cans last.
3. Reflow on the hot plate:
   - preheat at 150 °C for 90–120 s;
   - then set about 235–245 °C until the paste around the largest part goes shiny (the thermocouple on the board top
     should read 210–220 °C);
   - hold for about 30–45 s, then slide the board off onto a metal surface to cool.
   - Don't nudge anything while it's molten.
4. Inspect under magnification: bridges on the LM5146 and the INA237s, the WSON eFuses' side fillets, tombstoned 0603s. Fix with gel flux and the iron, or the
   hot-air gun for the QFN.
5. Hand-solder J1 to J6 (Micro-Fit), on the plate at about 150 °C preheat to help the iron.
6. Test before it touches the main board:
   - meter for shorts VIN–GND and VOUT–GND;
   - bench supply at 30 V and 0.2 A limit, then 48 V: check UVLO on at about 30 V and 12 V out with no load;
   - then a 1–5 A resistive load: check the output ripple and that nothing gets hot.

**B. Main board**
1. Clean, print paste with the main stencil, inspect.
2. Place in groups and check each group against the placement print before moving on:
   - the fine-pitch ICs (TPS3431, TPS48100/TPS48111, INA237, LM5069, TPS7A4001);
   - the 0603 passives, block by block;
   - SOD/SOT parts;
   - shunts, D2PAK-7 FETs, SMC diodes;
   - the cans last.
3. Reflow: the same profile, with a longer preheat (2–3 min). The 6-layer board with 2 oz pours lags the plate: watch the
   paste around the D2PAK tabs and the cans, not the plate reading.
4. Inspect all the fine-pitch ICs, the VSON watchdog (look at the side fillets) and the FET tabs (solder flowed out to the
   pad edge). Rework with flux and the iron, or the hot-air gun.
5. Wash off the flux (IPA and a brush) around U1, U7, U8 and the latch block, no-clean flux included, and let it dry
   fully (warm air or 30 min). The ESTOP_SAFE nets need clean, dry board: U1 pin 2 (SH_P, 54 V) sits 0.15 mm from pin 3
   (UVLO), and leakage of about 0.44–0.57 MΩ there closes bank B by itself (UVLO 33k to GND plus U1's 21 µA hysteresis
   sink against 54.6–57.5 V). Inspect the gap under magnification: no residue, no solder whisker. An unpowered ohmmeter
   check can't see it in-circuit (UVLO has 33k to GND and SH_P about 50 kΩ to GND through the MID bias and the absorber
   bleed), so the leakage check is powered: bring-up step 15. The whole-board conformal coat comes after bring-up
   (step 10).
6. Through-hole parts, with the board on the plate at about 150 °C (below the paste's 183 °C melt) so the iron doesn't
   fight the 2 oz copper:
   - Micro-Fit and Mini-Fit headers and the F2 fuse holder;
   - 16 AWG limb pigtails (14 AWG on the legs later), tinned first, large chisel tip at about 370 °C;
   - the 8 AWG pack pair last, the largest chisel tip at about 400 °C. Heat the pad and the wire together until the solder
     wicks fully into the hole.
7. Cable ties through the tie holes; clean the flux again.
8. Heatsink (option D): drill 2.5 mm and tap M3 at 7.5 and 89.5 mm from one end of the 120 mm heatsink, on the centre
   line, deburr. Thermal pad on the clean bottom copper, heatsink on with 2 × M3 × 12 stainless + washers through
   HS1/HS2, snug and even (about 0.5 N·m).
9. Bring-up per [REV_B_PARTS.md](REV_B_PARTS.md) steps 1–15, starting at the current-limited bench supply. Never go
   straight to the pack.

Hot air is for rework only (removing or reseating a part). Joey's low-power gun can't reflow the 2 oz board by itself.
10. **Conformal coat, after bring-up passes** (Joey's decision, 2026-11-09; the board is laid out for it: IPC-2221B
    51–100 V coated assembly spacing (A5/A7) is 0.13 mm, used as 0.2 mm between 54 V domains, against 0.6 mm bare; [LAYOUT_RULES.md](LAYOUT_RULES.md) "Clearance"). Bring-up runs uncoated so
    every pad stays probeable and reworkable. Then: wash and dry again (IPA, warm air), mask the Micro-Fit and Mini-Fit
    headers, the JST GH connectors, the F2 fuse holder, the pigtail and pack solder joints' contact faces, every test
    point, the M3 and heatsink holes and the bottom copper under the heatsink pad. Brush or spray an acrylic conformal
    coat (MG Chemicals 419D class), two thin coats, cure per the datasheet, inspect under UV. After coating, rework means
    stripping the coat locally and recoating.

## 8. Order checklist

1. The thermal option is decided ([THERMAL_OPTION.md](THERMAL_OPTION.md)), main board placed and routed and DRC
   clean, and the buck board laid out and DRC clean.
2. Part numbers fixed (section 4) and the BOM regenerated; kit CSV regenerated with suppliers chosen per route B/C.
   **Joey prefers one source for all board parts:** re-check DigiKey stock for the 6 ICs out of stock on 2026-11-07
   (INA237, LM5069-1/-2, TPS7A4001, TPS3431S, LM5146). If they're back, order everything from DigiKey (route A) and
   accept the about $80–95 premium; otherwise DigiKey for everything it stocks plus one LCSC order for the rest.
3. JLC quote for both designs, frameless stencils: main 6 layers, 2 oz outer / 0.5 oz inner, OSP; buck 4 layers, 1 oz.
   Confirm the main board's L1–In1 prepreg (tools/stack.py) and update section 1.
   **Main board, on the order form, every time (the Gerbers don't carry it):**
   - **Via covering: "Epoxy Filled & Capped" (IPC-4761 type VII), for all vias.** The board has 971 of its 1,903 vias in
     pads: under the ten FET tabs (about 50 each, the heat path to the heatsink), in the power GND pads and in the
     bare heatsink pads on the bottom. Unfilled, they wick the solder out of the tab joints on the hot plate and leave
     open holes in the bare pads under the gap pad. The board file says the same (board setup: capping yes, filling
     yes), but JLC builds from the order form. If the form offers the option per drill size only, it must cover the
     0.3 mm vias (970 in pads) and the 0.5 mm ones (one in a pad).
   - Outer copper 2 oz, inner 0.5 oz; surface finish OSP; solder mask on both sides with the ten openings on the
     bottom (B.Mask) left as drawn: they are the heatsink pads, not an error. Answer "keep as designed" if JLC asks.
   - **Minimum spacing:** JLC's capability page gives 0.2 mm (8 mil) track and space for 2 oz outer copper. The board
     meets it everywhere: its narrowest track and its smallest gap are both 0.2 mm (the pads of U1, U7 and U2 are at
     TI's land-pattern widths; [LAYOUT_RULES.md](LAYOUT_RULES.md), "Clearance").
4. The big review on the routed boards (Fable plus several Opus). Fix everything blocking.
5. Gerbers, drill files and stencil (paste) layers exported; polarity of every diode, can and IC checked in the 3D view.
6. Order the boards, the parts (LCSC + DigiKey), the tools, and the off-board parts (pack plan, REVB5_CHANGES), so they all
   arrive together.
