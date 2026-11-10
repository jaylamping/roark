# Power board rev B: layout rules

2026-11-07, rev B5; routing state and exceptions as of 2026-11-10. These rules come from the Opus round 5 layout review ([opus-review-r5/5-layout.md](https://github.com/jaylamping/marengo/blob/main/hardware/electrical/pdb/design/opus-review-r5/5-layout.md)) and Joey's single-sided rule. They replace LAYOUT_NOTES.md, which still describes rev A. schematic/tools/place.py follows them.

## Board

- **100 × 170 mm** (option A, Joey 2026-11-07: the 100 × 150 placement packed the control blocks to 74–84 % and couldn't be
  routed). The extra 20 mm are at the bottom (Y 170–190): the watchdog and the power-fail warning moved there, beside J21
  (the 12 V distribution and its Micro-Fit outputs went to the buck board in split S1, 2026-11-09); the latch and soft start widened to the left edge. Power path, banks, heatsink and ports
  kept their coordinates. M3 holes at X ±46, Y 174 / 265 / 336.
- **Single-sided: every part on the front face.** The rear has 6 mm to the carrier, and a back-side part would need a second reflow pass (Joey, 2026-11-07).
- **6 layers, 1.6 mm, 2 oz outer / 0.5 oz inner, OSP** (Joey, 2026-11-09: JLC quoted $82.80 for 5, against $96.47 for
  4 layers with 2 oz outer and $44.00 for 6 layers with 1 oz; the thermal vias are filled and capped at no charge). 2 oz
  outer was chosen over 1 oz plus soldered copper bars: no bar parts or bar soldering, and the VBUS spine can stay on L6
  beside the heatsink pads. [schematic/tools/stack.py](schematic/tools/stack.py) holds the
  stack for the tools:
  - L1 (F.Cu): parts, positive pours, short escapes.
  - L2 (In1): solid GND, unbroken under the banks, the absorber, the bus caps and the port FETs.
  - L3, L4 (In2, In3): signals between the two GND planes (Kelvin pairs, gates, UVLO), GND fill elsewhere.
  - L5 (In4): solid GND, the second return plane.
  - L6 (B.Cu): positive mirrors, the bare heatsink pads, GND wherever the positive path isn't.
- Rating to lay out for: **60 A continuous, under 90 A peak.** A 2 oz outer pour carries about 30 A in 10.5 mm at 20 °C
  rise (IPC-2221B, external), and about 27.5 mm carries 60 A. So the 60 A path (BAT, SW_D, MID, VBUS) needs about 27.5 mm
  of outer copper in total (one layer, or L1 plus L6 stitched with vias), and each 30 A port leg about 10.5 mm in total.
  No bars. Measured on the routed board's filled pours (2026-11-10, [schematic/tools/pour_width.py](schematic/tools/pour_width.py):
  the rise at each cut line by IPC-2221B, I = 0.048 × ΔT^0.44 × A^0.725, all layers at the cut lumped into one external
  conductor, 2 oz outer = 70 µm in full, 0.5 oz inner = 17.5 µm counted at 0.384 of its cross-section so that an inner
  layer by itself sits on the internal curve):

  | Path | Current | Worst cut | Copper there | As one 2 oz outer layer | Rise |
  |---|---|---|---|---|---|
  | VBUS stem, bus-cap bar to the ports (Y 178–222) | 60 A | Y 213.0, a row of seven signal vias | L6 22.7 mm, In2 11.7 mm, In3 4.5 mm | 24.3 mm | 25.3 °C |
  | VBUS stem, every other cut | 60 A | | L6 23–38 mm plus In2/In3, L1 strips at the ports | 25–40 mm | under 24 °C |
  | VBUS stem below port 5's tap (Y 222–231.4) | 30 A | | | | under 6 °C |
  | VBUS at Q1's / Q2's source pins | 30 A each | Y 169 | L1 5.0 + L6 6.1 / 5.0 mm | 11.1 / 10.0 mm | 19.0 / 22.5 °C |
  | MID at Q8's / Q9's source pins | 30 A each | Y 149 | L1 5.0 + L6 6.1 / 5.0 mm | 11.1 / 10.0 mm | 19.0 / 22.5 °C |
  | MID band between the FET rows | 60 A | Y 150.25 | L1 35.2 + L6 13.7 mm | 48.9 mm | 8.0 °C |
  | BAT, pack pad to RS1 | 60 A | Y 121.75 | L1 26.6 + L6 11.2 mm | 37.8 mm | 12.2 °C |
  | GND return, ports to the pack's GND pad, every layer | 60 A | Y 173.25, under the bus-cap bar | L1 6.7, In1 56.5, In2 32.9, In3 32.8, In4 56.5, L6 5.5 mm | 29.3 mm | 18.5 °C |
  | Port output legs V_L1–6, source pins to the pigtail pad | 30 A each | | L1 5.0–5.2 + L6 5.2–5.5 mm | 10.4–10.7 mm | 20.2–21.2 °C |

  The stem was 25.6 mm of outline on L6 alone, 18.3 mm at its worst cut (Y 221.5) and about 40 °C there. It is now
  38.4 mm of outline on L6 (X 130.8–169.2: the strips beside it were GND fill cut up by the port blocks' vias) with
  VBUS pours on In2 and In3 over it, joined by the VBUS vias that already pass through
  ([schematic/tools/vbus_copper.py](schematic/tools/vbus_copper.py)). The inner pours add little (0.5 oz copper counts
  for about a tenth of its width); the widening does most of it. The four source-pin columns are separate 30 A
  conductors 13 mm apart: an earlier figure of "MID 21.1 mm" was two of them added together, measured on the pour's
  outline. pour_width.py fails the board above 26 °C on the stem and 25 °C elsewhere, and if the VBUS band
  (X 130–160, Y 180–190) holds more than its 18 vias of other nets. The stem's worst case assumes the last two ports
  loaded at 30 A each.
  BAT was 26.6 mm on L1 alone (21.7 °C); it now has a mirror on L6 from the pack pad to 17 staggered vias north of
  RS1's pad ([schematic/tools/bat_copper.py](schematic/tools/bat_copper.py)). The L6 share is limited by those vias
  (about 1 A each), so take the L1 pour as carrying about 43 A of the 60. The GND return was measured the same way for
  the first time: its worst cut was under the bus-cap bar, where the VBUS via rows at 1.3 and 1.0 mm pitch had merged
  their clearance holes into a slot 53 mm long through all four inner layers (31 mm of each plane left, 25.1 °C). The
  rows are now at 2.6 and 2.0 mm, staggered, and the planes keep 56 mm there. The port legs are at their 10.5 mm
  target and stay as they are: the strips are bounded by the pigtail pads and the neighbouring port. Each port's
  drain link from the shunt's pad to the FET tab is a 2.1 mm wide, 2.5 mm long neck on L1 between two large copper
  areas (0.29 mΩ, 0.26 W at 30 A, about 3 K by conduction into the pads); IPC's long-trace curve does not apply to it
  and pour_width.py does not measure it. Floors in pour_width.py: stem 26 °C, BAT 15 °C, GND return 21 °C, port
  legs 22 °C, the rest 25 °C. At layer changes, use about 1 A per 0.3 mm via, and never put vias of one net closer
  than 1.8 mm in a row across a return path: at 0.3 mm plane clearance their holes are 1.2 mm wide.

## Power path

- **Flow order down the board:** BAT pair (top edge) → absorber cluster and RS1 → bank A → bank B (under the upper fan) → bus caps → port breakers → limb pigtails. Remove the old B → A → B detour.
- **Pack entry:** the BAT and GND 8 AWG pair (4.5 mm holes, 8 mm pads, 14 mm pitch; to an XT90) sits side by side on the top edge, in the frame's pack cable path. **Keep-out: no components in X −5..25, Y 315–340** (the leads run up the face and bend over the top edge at R15 from about Y 330); the pads sit in that strip. Solid connections to every copper layer, no thermal reliefs. A cable-tie hole each side of the pair.
- **Absorber cluster:**
  - D7, D21 and the eight cans in one cluster at the BAT entry; R53 (the ABS_N to GND link) under the can stack.
  - ABS and ABS_N are pours directly over unbroken L2.
  - R53 is at least 5 mm wide, with 10 or more vias to the GND planes, L2 and L5 (In1, In4).
  - **Loop:** extracted from the 4-layer routed copper by `schematic/tools/absorber_loop.py`: **LABS 5.4 nH**, LBAR 2.0 nH.
    **Rerun on the 6-layer routed board, 2026-11-10: LABS 5.36 nH, LBAR 1.97 nH** at h 0.21 mm; 3.23 nH and 1.46 nH
    at 0.099 mm, the thin prepreg JLC may use (`MARENGO_H_L1_L2_MM=0.0994`). The tool takes the part positions from
    the board and the conductor widths from route_power.py's pours; it is not a field solve. Microstrip over In1
    (h 0.21 mm; tools/stack.py keeps it until JLC confirms the 2 oz 6-layer prepreg, since a thinner one only lowers the
    loop) per segment, weighted by its share of the current, plus assumed part ESLs: 1.5 nH per SMC diode, 3 nH per
    can, 1 nH for RS1. The ABS_N spine down to R53 is the largest term (about 2.4 nH), because R53 sits at the bottom of
    the stack. 2 nH isn't reachable with these parts; the ceramics below take the fast edge instead.
- **Pack-entry ceramics C89–C92** (4 × 4.7 µF 100 V 1210, BAT to GND, about 8.8 µF at 54 V bias): two between RS1 and D7,
  two in the BAT arm by D1, GND pads via-gridded to In1. **Bank A drain ceramics C87/C88** (2 × 4.7 µF 100 V): beside
  RS1's SW_D pad, GND vias to In1. absorber_sim (real turn-off, all corners): BAT 73.8–73.9 V, bank A drain 81–84 V,
  with a 3–5 nH absorber loop; **at the extracted 5.36 / 1.97 nH: BAT 73.8 V, bank A drain 84.4 V; at 3.23 / 1.46 nH
  (thin prepreg): BAT 73.4 V, bank A drain 80.2 V.** Against the parts: the FETs, C87–C92, U1 and U7 are 100 V parts;
  the absorber cans (80 V) sit behind D7/D21 and see no more than BAT's 73.8 V; the bus caps (80 V) are downstream of
  the opened bank. U8's VS and CS pins sit on RS1's pads and see the bank A drain's 80–84 V for under a microsecond:
  the TPS4810-Q1 datasheet (SLUSEW1C, June 2026) rates VS, CS+ and CS– at 100 V absolute maximum and recommends VS up
  to 95 V, so the worst case keeps 10 V to the recommended limit and 15 V to the absolute one. U1's SENSE pin is on the
  same node: 100 V absolute maximum, with the LM5069's operating range ending at 80 V, so it is 4 V over the operating
  range for that microsecond and 15 V under the limit. No clamp is needed.
- **FET copper and the heatsink (option D, [THERMAL_OPTION.md](THERMAL_OPTION.md)):**
  - 2.7 W per FET at 60 A goes down into a finned heatsink under the board (X −33..33, Y 200–305).
  - About 50 × 0.3 mm vias per tab, at the pad edge and under it, filled and capped (free at 6 layers) so they
    don't wick solder on the hot plate. **Order every via epoxy-filled and capped** (PRODUCTION_RUN section 8, step 3;
    the board setup says capping and filling yes). The other vias are tented on both sides. The rows of vias under
    each port eFuse and under U8 are not in pads: they sit 0.33 mm from the pin pads under mask, so they don't wick
    even unfilled, and filled they are closed anyway.
  - L6: bare copper (no mask, OSP) under each of the ten FETs, for the insulating gap pad
    ([schematic/tools/heatsink_pads.py](schematic/tools/heatsink_pads.py), on B.Mask since 2026-11-10; the board had
    no openings before). Each opening is the 15 × 15 mm square centred on the tab, cut down to that FET's own drain
    copper 0.3 mm inside its edge: 139 mm² at Q8/Q9 (SW_D), 145/143 mm² at Q1/Q2 (MID), 110–114 mm² at the ports (the
    drain mirrors are 12.2 × 10.5 mm). None reaches 225 mm²; against the thermal budget's 0.75 K/W per pad that is
    about 1.2–1.5 K/W, 1–2 K more at 2.7 W. An opening never uncovers another net's copper (KiCad's solder-mask
    bridge check and the 0.3 mm inset); verify_board.sh fails if the openings differ from the generated set.
  - **Masked copper is allowed on L6 inside the heatsink zone; bare copper only at the FET pads** (the rule as the
    board meets it; Joey to confirm): the VBUS stem, the signal vias through it and GND fill lie under the gap pad,
    under solder mask. **What the insulation rests on:** the ten bare pads are on eight nets (SW_D twice, MID twice,
    and the six port drains, each at VBUS behind its 2 mΩ shunt), and the heatsink floats. The
    0.5 mm gap pad is then the only insulation between a bare pad and the heatsink: one puncture makes the heatsink
    live at that pad's potential, and a second one under a pad of another net joins the two through the heatsink
    (SW_D to MID bridges bank A; SW_D to a port drain bridges both banks). The pad is therefore specified with a
    rated breakdown voltage: Henkel Bergquist GAP PAD TGP 3000, 0.020 in, over 3000 Vac, fiberglass-reinforced, cut in
    one piece ([THERMAL_OPTION.md](THERMAL_OPTION.md), "Insulation under the heatsink", with the thermal figures for
    the pads as built: Tj about 78 °C with fan air, 102 °C without). The heatsink is tied to GND through 100 kΩ
    (R139, 1206, 200 V) by a wire from J27 to a ring lug under a heatsink screw, with test point TP17: a puncture
    shows there as a voltage.
  - Heatsink holes HS1 (0, 286) and HS2 (0, 204), M3, no copper within 2 mm; the MID pour flows around HS1.
  - Keep all four bank FETs inside the upper fan footprint (|X| ≤ 20, Y 264–304).
  - Check with a coupon or quick FEM; a clip-on heatsink per bank is the fallback.
- **Bus caps:**
  - within 20 mm of bank B's source pins and of the port FET drains;
  - C38 and the other 12.6 mm cans stay out of the fan-zone height limit (Z 61.5 ceiling at |X| ≤ 20).
- **Port breakers:**
  - each TPS48111 within 10 mm of its FET;
  - PD → 22 Ω → gate at the gate pin (R5, 3.2 mm from the pin since 2026-11-10; the 100k pull-up resistor R4 sits
    above it, 5.9 mm from the pin);
  - the 2.2 µF drain cap at the drain;
  - the SK810L output clamp at the source;
  - the shunt Kelvin pair runs to both the TPS48111 (VS, CS+ through 100 Ω, CS−) and the INA237.
- **D2PAK-7 drain lead:** pin 4 (the centre lead) and the tab are the same drain but separate pads; a 0.5 mm track joins
  them under the package body (it keeps 0.6 mm to pins 3 and 5). Pin 4 splits the source pins, so pins 2–3 reach the
  source copper through vias at their outer ends into the L6 mirror. Pins 5–7 carry the source current on L1; three of
  the five source leads are plenty for 30 A.
- **Left limb ports** are the right ports' power row turned 180° (shunt, FET, output clamp, pigtail, meter), so every port
  FET has its gate pin on the inner side and its source pins facing the pigtail.
- **Brake headers J3/J25:** VBUS and CL_D run up the can column on L6 as 2 mm tracks (X 34.5 and 40.5).
- **Limb outputs:** each limb's + and return are on one pigtail pair at the board edge, twisted from the exit. Add a strain-relief tie hole beside each pair.
- **Brake headers J3/J25:** at the top edge. The −X pair runs above the board, not through the 6 mm gap behind it.

## Sensing and gates

- **RS1 and every shunt:**
  - Kelvin traces from the inner edge of the sense pads, as a tight pair over GND, branching only at the ICs.
  - Flare the current pours across the full pad width, with via arrays at the pad edge, not in the pad.
  - 1 mm of 5.6 mm-wide copper inside the sense loop costs 8.8 % of U1's limit.
- **Gate loops:**
  - each driver within 10 mm of its FETs;
  - the gate resistor at the gate pin (for the banks, only R1 and R31 so far: see Gate parts below);
  - the gate return taken as its own trace from the source pin nearest the gate, running beside the gate trace;
  - symmetric between the two FETs of a bank. Not met: R2 and R32 sit at their controllers while R1 and R31 sit at
    the gates (exception 13).
- **Controllers at their shunts (2026-11-08):** schematic/tools/place.py fixes each controller next to its shunt, sense pins facing
  the sense pads:
  - U1 in the GND gap left of RS1, GATE toward Q8; UVLO leaves through a via under the body;
  - U7 with its sense pins toward RS9;
  - each port controller (U19–U24) straight under its shunt, with the meter (U11–U16) under the controller.
  Routed controller legs (shunt pad to pin): U1 2.9/7.1 mm; port controllers 1.7–6.3 mm. Meter legs are 12–37 mm,
  each as a pair beside the controller's.
- **Critical nets are routed first by script and locked:**
  - the nets: every Kelvin pair, the gate drives (GATE, GATE_A, GA1/GA2, G1/G2, G_L*, GPU/GPD_L*, BRK_GATE, PRE_G, CL_G)
    and UVLO;
  - schematic/tools/grid_route.py with `ONLY=<regex>`; `FONLY` makes them try F.Cu alone first (no via, so the solid In1 GND
    plane lies under the whole run), falling back to all layers;
  - the autorouter takes the rest, and schematic/tools/ses_import.py `LOCK=<regex>` keeps the pre-routes locked for hand finishing.

## E-stop safety nets

- Net class **ESTOP_SAFE:** RUN, RUN_A, RUN_B, RUN_P, SP_ENR, UVLO, EN_A, FLT_A, FLT_D, LOOP_*, RST_*, L_B, L_E, L_PB, L_PC, MID_B, VB_B, INT_B, WDO_N, VWD.
- At least 1.5 mm (2 mm preferred) to any BAT, SW_D, MID, VBUS, ABS, CL_D, BRK_*, SH*, V_L*, VS_A, CSP_A or CSN_A copper, on all layers, with a GND guard trace or pour between them.
- Why: 0.44 MΩ of leakage from 54 V into UVLO enables bank B by itself.
- No 54 V copper on L2–L5 under the latch block.
- Wash off the flux. The whole board is conformal-coated after bring-up (Clearance below; PRODUCTION_RUN step 10).
- J20 (the loop connector) sits on the far side of the latch block from the converter soft start.

### Leakage from the latch supply

The latch's own supply (BAT → F1 → BAT_F → 22 Ω → BAT_R → ES1D → BAT_CTL → U2) is at 54 V and lies inside the latch
block, among the E-stop nets, so it is not on the 54 V list: 599 item pairs would break the 1.5 mm rule. What leakage
from it does, net by net (values from schematic/gen/gen.py; leakage pulls a net up; "run" means toward power on):

| Net | Impedance to ground or its driver | Leakage pushes it toward | Leakage resistance at which it matters | Spacing to the supply chain |
|---|---|---|---|---|
| RUN | 1.13 kΩ (1.2 k ∥ 20 k) | run | 48 kΩ sets the latch (RUN 1.25 V turns Q5 on, loop closed); 10 kΩ holds both banks on with the loop open | 0.2 mm |
| LOOP_RET | driven through 680 Ω while the loop is closed; open with the button pressed | run (it re-feeds Q4's emitter past the button) | 43 kΩ keeps the latch set through a press; 27 kΩ keeps bank A on, 9 kΩ both banks | 0.2 mm |
| L_PB (Q4 base) | 100 kΩ to LOOP_RET, 10 kΩ to Q5's collector | stop (lifts the PNP's base) | under 38 kΩ causes a false stop | 0.2 mm |
| L_E, L_PC (Q5 emitter, collector) | the watchdog switch; 10 kΩ | stop | none toward run | 0.2 mm |
| RUN_P | about 5.3 kΩ (six port dividers) | run, ports only (the banks stay off) | 67 kΩ | 0.2 mm |
| VB_B (Q14 base) | 220 kΩ | stop (holds RST_SRC low: no reset) | 20 MΩ blocks a reset | 0.2 mm |
| INT_B (Q10 base) | 100 kΩ to VCTL | stop (holds RST_SRC low) | none toward run | 0.2 mm |
| RST_SRC | 4.7 kΩ to VCTL, 1 µF; shorted by Q10/Q14 | run only against a saturated transistor | under 1 kΩ, and a reset still needs the button | 0.2 mm |
| RST_IN | 10 kΩ; reaches L_B only through 2.2 nF | none at DC | none | 0.2 mm |
| **L_B, RST_C** (Q5 base) | 5.3 kΩ | **run** | **0.47 MΩ** (0.56 MΩ at RST_C) turns Q5 on: with the loop closed the latch sets without a reset press. A pressed button still stops | **1.5 mm** |
| **MID_B** (Q11 base) | 220 kΩ | **run** (reports "MID healthy") | **20 MΩ** releases the reset interlock | **1.5 mm** |
| **RUN_A, EN_A** | 110 kΩ | **run** (bank A only) | **4.3 MΩ** | **1.5 mm** |
| **RUN_B, UVLO, FLT_D** | 55 kΩ / 33 kΩ | **run** (bank B only) | **0.44–0.7 MΩ** | **1.5 mm** |

No single leakage path keeps power on through a pressed E-stop: the PNP loses its supply, and the two banks take RUN
through separate diodes. The nets in bold are the ones where leakage in the megohm range removes one of those layers
or re-arms the latch, so they keep 1.5 mm to BAT_F, BAT_R and BAT_CTL on every layer
([schematic/tools/domains.py](schematic/tools/domains.py) LATCH_SUPPLY and LEAK_SENSITIVE; the .kicad_dru rule
`latch_supply_leak`; route_checks checks 1/2 and 10). As packed, 135 item pairs were closer: R59 and D8 stood
courtyard to courtyard with Q5, R48 and the RUN_B track, and L_B ran 17 mm south past U2's BAT_CTL pins. The supply
chain is now a designed block ([schematic/tools/latch_block.py](schematic/tools/latch_block.py), 2026-11-10):
- R59 and D8 sit south of the logic beside F1 (page Y 173.7–181.8), so BAT_F and BAT_R are 4 mm long and stay there;
- BAT_CTL runs north on F.Cu in one lane (X 114.6) to C39 and U2's pins 5 and 8, with no via: no supply copper is on
  an inner layer under the latch block (route_checks check 4 now tests the chain too);
- R16, R17 and C7 sit at Q5's base where R59 and D8 were, so L_B is a 5 mm net; R49 sits beside R48, so MID_B's two
  resistors are together;
- MID_B, and the copper of other nets that lay in the way, were re-routed by finish_route.py to the same rule.
The fail-safe nets of the table keep 0.2 mm to the chain; that is the documented exception, not an open item.

## Clearance

IPC-2221B Table 6-1, 51–100 V row (the values used here, from the standard's table; check against your copy): B1
internal 0.1 mm; B2 external bare, up to 3050 m, 0.6 mm; B3 above 3050 m 1.5 mm; B4 external with permanent polymer
coating 0.13 mm; A5 external with conformal coating over the assembly 0.13 mm; A6 external component lead or termination,
uncoated, 0.5 mm; A7 the same, coated, 0.13 mm. So uncoated, the package-set pad pairs at 0.3–0.5 mm fail A6 as well as
B2; coated, everything at 0.13 mm or more passes.

**Coating: the board is conformal-coated (Joey, 2026-11-09).** The coat is acrylic (MG Chemicals 419D), applied after
bring-up passes, with the connectors, test points, holes and heatsink pad masked (PRODUCTION_RUN step 10). The 54 V domain
rule below is therefore the 0.2 mm default (IPC-2221B A5/A7, 0.13 mm); the tools run with `MARENGO_COATED=1`. The 1.5 mm
E-stop rule and the hole keep-outs don't change. Without the coat it would be 0.6 mm on the outer layers, so a board
that is never coated must not go on the pack.

- **One rule table** ([schematic/tools/domains.py](schematic/tools/domains.py)), used by the router, the
  placement spacing pass, the GND fanout and the checks (2026-11-08):
  - E-stop nets (the ESTOP_SAFE list above) keep **1.5 mm** to the 54 V list (BAT, SW_D, MID, VBUS, ABS, ABS_N, CL_D,
    BRK_*, SH*, V_L*, D_L*, and since 2026-11-10 U8's VS_A, CSP_A and CSN_A) on every layer.
  - Copper on 54 V, or riding on a 54 V node (a gate or bootstrap on its source, a sense tap on VBUS), keeps **0.6 mm**
    on the outer layers (0.2 mm inner) to every net of another voltage domain uncoated; the board is coated, so 0.2 mm
    on all layers. Nets in one domain (a port's V_L, G_L,
    GPD/GPU, BST, GC; bank B's MID with GA1/GA2 and BST_A; the VBUS taps) are tens of volts apart at most, so 0.2 mm.
  - Everything else 0.2 mm.
- **Inner GND planes and fills (In1–In4): 0.3 mm zone clearance** (2026-11-09; `PLANE_CLEAR` in
  [schematic/tools/stack.py](schematic/tools/stack.py)). The zones were built with 0.6 mm, the old uncoated outer-layer
  value, and a row of vias at 0.85 mm pitch under a fine-pitch IC then cut the planes away completely. IPC-2221B B1
  (internal conductors, 51–100 V) asks 0.1 mm. Measured on the routed board (2026-11-10): every via and all 40 plated
  pads keep their inner lands; a 0.6/0.3 mm via's drill is 0.45 mm from the GND planes (0.40 mm from the VBUS pours on
  In2/In3, whose clearance is 0.25 mm), and the 12 unplated holes (connector pegs) are 0.25 mm from the planes, the
  board's hole clearance. JLCPCB's capability page (read 2026-11-10) asks 0.2 mm from an inner-layer via hole to
  copper and 0.3 mm from a plated pad hole to copper; the plated pads' holes are further than that behind their lands.
  The
  outer GND fills keep 0.6 mm. schematic/tools/route_power.py builds the zones with it, schematic/tools/plane_clearance.py sets it
  on a routed board, and route_checks.py check 6 tests it.
- **DRC rules** (layout/marengo_pdu_revb.kicad_dru; a later rule wins in KiCad):
  - `estop_to_54v`: 1.5 mm from net class ESTOP to net class HV54 on every layer (classes set by
    schematic/tools/handfinish_prep.py from schematic/tools/domains.py).
  - **No fine-pitch rule; nothing on the board is closer than 0.2 mm** (2026-11-10). JLCPCB's capability page gives
    0.2 mm track and space for 2 oz outer copper, and KiCad's library footprints for U1 and U7 (LM5069, MSOP-10) and
    U2 (TPS7A4001, HVSSOP-8) leave 0.15 mm between pads (0.35 mm pads at 0.5 mm pitch, 0.5 mm at 0.65 mm). TI's land
    patterns for these packages (DGS and DGN) draw the pads 0.30 and 0.45 mm wide, so the project library now holds
    copies at those widths (`marengo_revb:MSOP-10_3x3mm_P0.5mm_TI`, `...HVSSOP-8-..._TI`, written by
    schematic/gen/genfp.py and named in the schematic); schematic/tools/fine_pitch_pads.py brought the routed board to
    them. The 23 gaps of 0.15 mm are gone: 17 by the narrower pads, 6 by re-laying U7's BRK_P and U2's FB_CTL escapes.
    The three courtyard rules at 0.15 mm are removed, as U8's was when its block was turned
    (schematic/tools/u8_block.py).
  - **One package-set rule remains, `estop_at_U1`:** U1's UVLO pin (E-stop) is 0.2 mm from its SH_P pin and 0.7 mm
    from SH_N (54 V). Between F.Cu pads, tracks and vias inside U1's courtyard the 1.5 mm rule gives way to the 0.2 mm
    default; never for a pour, never on another layer. schematic/tools/route_checks.py tests the same scope on the
    real shapes.
  - U1's UVLO pin sits between SH_P and the GND pins. schematic/tools/route_u1.py therefore draws U1's escapes as single straight
    segments: SH_P and SH_N straight out to RS1, and UVLO inward to a via under the body.
- **Holes:** no copper within 2 mm of the heatsink screw holes HS1/HS2 (the screw and the heatsink aren't insulated from
  it), 0.6 mm round the tie holes and the M3 mounting pads (rule areas from schematic/tools/place.py).

## Routing state (2026-11-10, 6 layers, after the review's fix round)

Every connection is routed (0 open). `schematic/tools/verify_board.sh` passes: DRC with no violation of any type but the
three cosmetic silkscreen ones on its allow-list, schematic parity 0, route_checks checks 1 to 10, every joint with
0.1 mm of real overlap, the designed blocks and the hand-laid copper equal to their scripts, the pours' rise within
limits, the heatsink pads as generated, check.py at 0 fails, the BOM files equal to the netlists. It runs next to a
copy of the schematic, so the parity check really runs (in layout/ KiCad only prints "Failed to fetch schematic
netlist" and checks nothing). `schematic/tools/verify_selftest.sh` shows each of these checks failing on a
deliberately broken copy.

How the board got there:
- **Staged scripts** (schematic/tools/route_stages.sh, then the finish_* tools) for the general routing. Generic routers
  stalled at the port taps and at U8, so those two are designed:
- **Port block template** (schematic/tools/port_template.py for placement and rip-up, port_copper.py for the copper,
  port 1's page mm mapped to the other five; the left ports are the right ports turned 180 degrees, part for part):
  - logic row of the eFuse (EN, INP, PORT_FLT_N, GND): inward to one row of vias under the body, In3 from there;
  - 54 V row: V_L (pin 13) and BST inward to a via each; GPU and GPD outward through the two-track channel under the
    shunt into the corridor east of the eFuse, where R4 (100k, GPU) stands above R5 (22 Ω, GPD). R5's gate pad is
    3.2 mm from the gate pin (3.8 mm of F.Cu track, the zener on the same line); R4's gate pad is 5.9 mm away. One
    In3 link goes to the slew diode right of the FET;
  - Kelvin pair on In2 down the west side of the eFuse, P outside and N inside at 0.6 mm, feeding R0/C2 and R1 through one
    via each and ending at the meter's pins 10/9: 56 % of both legs' length paired on all six ports (72 % of P, 46 %
    of N, centre to centre within 1.0 mm; the earlier "76 %" counted P only, edge to edge);
  - the sense resistors, the bootstrap and the timer/limit parts keep one In2/In3 lane each across the FET's pin row.
  - Port 2's meter reads D_L2 on pin 8 (deliberate: schematic/gen/gen.py and check.py), so its tap is laid by hand on B.Cu
    to the L6 drain mirror instead of the template's V_L tap.
  - `MODE=check` fails when the board's copper on the ports' own nets differs from port_copper.py; `MODE=sync` brings
    the board to the template without ripping the routing between the blocks.
- **U8 block** (schematic/tools/u8_block.py, with the same `MODE=check` / `MODE=sync`): U8 sits between bank A/B's tabs
  (54 V) and the ABS spine (54 V), 7 mm apart, so its E-stop pins could not leave sideways at 1.5 mm. U8 is turned so
  the logic row faces north and the 54 V row south; R27, R28, TP13, R36, C29 and R37 sit north of it, every 54 V part
  south. EN_A and FLT_A run from the pins on F.Cu with no via. The SH pair runs on In2 down the middle of the column
  to R61/R62 (62 % of both legs paired).
- **Latch supply block** (schematic/tools/latch_block.py, `MODE=check` / `MODE=sync`): "Leakage from the latch supply"
  above. tools/place.py takes the whole latch group's positions from it.
- **VBUS stem copper** (schematic/tools/vbus_copper.py), the **BAT mirror** (bat_copper.py), the **bare heatsink pads** (heatsink_pads.py) and the **E-stop
  guard areas** (estop_guards.py; none is needed at the present placement) are generated from the board and rebuilt
  by their scripts.
- **J24** pads 6-12 follow the schematic (6 +3V3_PI, 7-8 GND, 9 SP_EN, 10 GND, 11 SCL, 12 SDA, as on the buck board's
  J1). schematic/tools/sync_netlist.py brings an existing board to the netlist; bom_check.py holds the BOM and kit
  files to it.
- **C81** (the watchdog's CWD cap) sits beside U25's pin 2 (place.py MOVED); the packer had put it 20 mm away.
- **Joints:** KiCad's connectivity accepts two shapes that touch at a tangent point. The gate stubs of ports 2, 4 and 6
  met their resistors that way, and 48 other joints (router tracks ending 0.01 to 0.09 mm inside a pad's edge, among
  them VCTL, +3V3_PI, UVLO, SH9_P and GATE_A's via at R31) had under 0.1 mm of overlap. All were bridged
  (schematic/tools/joint_fix.py); joint_check.py fails on any such joint that holds a net together.

**G2** (Q2's gate to R2) stays under exceptions 1 and 2. Q2's gate pin lies in a 1.7 mm slot between Q1's tab and Q2's
own pins, under the MID band on L1 and over the MID mirror on L6, so G2 can only leave through a via in the L6 MID
mirror. It takes that via at (149.9, 160.19), In3 west under Q1, a second via at (130.2, 167.0) outside the pours, In2
north and a third via at R2: 55.8 mm, 3 vias. **R2 beside R1 at the GATE tee was tried on 2026-11-10 and does not fit as
it stands:** the free site west of R1 (X 128.8–130.4, Y 158.7–162.0) is crossed by a MID track on F.Cu, with BRK_IN
and ABS_N under it on the inner layers, and G2's In3 run cannot reach the tee because two 54 V tracks on In3 lie
between. Moving R2 there would need the MID tap, R34 and TP14 moved first; the result would be about 30 mm with the
same 3 vias (the In3 run still has to change to In2 south of the tee), so it is shorter but takes no fewer vias.

Kelvin pairs still poorly paired: **SH9 (9 %)**. RS9's N sense pad is on the far side of its BAT pad from U7, so N has to
pass under that pad on In2 while P stays on F.Cu; a better pair needs RS9 or U7 moved.

## Exceptions and hand-laid copper

Rule exceptions and open items on this board, each tested or bounded by a check:

| # | Exception | Where | Status | Held by |
|---|---|---|---|---|
| 1 | G2 has a via through the L6 MID mirror | (149.9, 160.19), at Q2's gate | accepted in the project thread, 2026-11-10; the review asked to try R2 at the tee, which did not fit (above) | route_checks 7: the via is pinned to its coordinates (domains.MID_VIA_OK) |
| 2 | G2 has 3 vias (gate nets: 2) and is 55.8 mm long | (149.9, 160.19), (130.2, 167.0), (125.6, 139.8) | as 1 | route_checks 8: exactly these three (domains.GATE_VIA_OK) |
| 3 | GATE_A has 3 vias, one inside the MID outline at Q8's gate | (132.0, 141.46), (168.55, 158.85), (168.55, 164.75) | from the staged routing; not changed | route_checks 7, 8: pinned |
| 4 | GA2 has a via inside the MID outline, in the pour's dead tip beside U8 beyond the tabs | (167.95, 157.0) | not changed | route_checks 7: pinned |
| 5 | U1's UVLO pin (E-stop) is 0.2 mm from its SH_P pin: inside U1's courtyard, F.Cu pads, tracks and vias keep 0.2 mm instead of 1.5 mm. No clearance under 0.2 mm is left anywhere (the fine-pitch rules are removed, pads at TI's land-pattern widths) | .kicad_dru `estop_at_U1` | package-set; in force | DRC, route_checks 1/2 |
| 6 | Inner GND planes and fills at 0.3 mm zone clearance (outer fills 0.6 mm); the VBUS pours on In2/In3 at 0.25 mm | In1-In4 | accepted in the project thread, 2026-11-10 | route_checks 6 |
| 7 | Signal and GND vias pass through the L6 VBUS stem, 18 of them in the band X 130-160, Y 180-190 | under the meter blocks and the port blocks | band rule: no new ones | pour_width.py (18 at most; the stem's rise) |
| 8 | Masked copper (the VBUS stem, the vias through it, GND fill) inside the heatsink zone on L6; bare copper only at the ten FET pads, under an insulating pad that is the only insulation there | X -33..33, Y 200-305 | the rule as the board meets it; the pad is specified (GAP PAD TGP 3000, 0.020 in, over 3000 Vac) and the heatsink is tied to GND through 100 kΩ with a test point (R139, TP17, J27) | heatsink_pads.py MODE=check, DRC's solder-mask bridge check |
| 9 | SH9 Kelvin pair 9 % paired | RS9 to U7 | open: needs RS9 or U7 moved | route_checks 3 (floor 9 %) |
| 10 | VBUS stem 25.3 °C at its worst cut (target 20 °C, about 25 accepted); port legs 20.2–21.2 °C (at their 10.5 mm target, bounded by the pads) | Board, above | accepted as measured; BAT (12.2 °C) and the GND return (18.5 °C) are no longer open | pour_width.py floors for every path |
| 11 | The fail-safe E-stop nets (RUN, LOOP_RET, L_PB, L_E, L_PC, RUN_P, VB_B, INT_B, RST_SRC, RST_IN) keep 0.2 mm, not 1.5 mm, to the latch supply chain, which is at 54 V but not on the 54 V list | latch block | by the leakage table ("Leakage from the latch supply"); the leakage-sensitive nets keep 1.5 mm (0 pairs closer) | route_checks 1/2 and 10, DRC `latch_supply_leak` |
| 12 | The 100k gate pull-up resistor R4 is 5.9 mm from the gate pin (rule: gate resistor at the gate pin); the 22 Ω R5 is at 3.2 mm | each port | kept: the corridor holds one 0603 column, and 100 kΩ swamps the track | port_template.py MODE=check |
| 13 | R2 and R32 sit at their controllers, not at Q2's and Q9's gates | bank A and B | kept: no room at the gates (Gate parts, below; R2 at the tee tried, above) | none |

Copper laid from hand-specified coordinates rather than found by a router. All of it is in scripts and checked against
the board by verify_board.sh:

| What | Where it is defined |
|---|---|
| Port template, six ports | schematic/tools/port_copper.py ITEMS, mapped by port_template.T() |
| U8 block | schematic/tools/u8_block.py ITEMS |
| D_L2 tap to U12 pin 8 (port 2), G2, the I2C_SCL exit under port 2's meter, the L_E / CWD / VWD escapes at U25, one GND island link | [schematic/tools/hand_laid.specs](schematic/tools/hand_laid.specs), one lay_path.py SPEC per line |
| VBUS stem pours, heatsink pad openings | schematic/tools/vbus_copper.py, heatsink_pads.py |

Everything else between the templates (the buses between the blocks, EN/INP/PORT_FLT_N runs, the J24 nets, the GND
vias) was found by schematic/tools/finish_route.py, whose result depends on the order of the runs: a rebuild from the placement
gives the same blocks but not the same copper in between. schematic/tools/build_board.sh runs the whole sequence
(placement, power stage, staged routing, blocks, hand-laid copper, finishing router, joint_fix, BAT mirror, guards,
heatsink pads, verify_board.sh).

**A full rebuild was run on 2026-11-10** (scratch copy, about 70 minutes) and does not reproduce the committed board:
- What it reproduces: the placement (that run had one 0.14 mm courtyard overlap, TP7 against C39, because
  latch_block.py's table lost a test point's rotation; the table now carries each part's rotation and place.py
  reports 0 overlaps), the pours and via arrays, the three designed blocks and the nine
  hand-laid specs (the port, U8, latch and hand-laid checks all pass on it), the heatsink pads, the BAT mirror, every
  pour floor.
- What it does not: the routers' copper between the blocks. The finishing rounds stop at **68 open connections on
  27 nets** (GND 14, I2C_SDA 7, PORT_FLT_N 6, VCTL 5, I2C_SCL 4, the port EN and INP runs, the clamp's comparator
  nets), with 5 clearance violations, 68 dangling ends, FLT_A on In2 within 1.5 mm of the SH pair, a MID via under the
  latch block, the SH pair 24 % paired against its 61 % floor, and 19 vias in the VBUS band against 18. The committed
  board closed these by rip-up and re-route passes run by hand (rrr.sh, rip_window.py, lay_path.py) that are not in
  the script. So the committed board file is the source of the routing; the build script is the source of everything
  designed. verify_board.sh says which is which on any rebuild.

Gate parts (schematic/tools/place.py, 2026-11-09):
- Each port's gate-source zener (D24, D27, D30, D33, D36, D39) sits at its FET's gate pin, between the meter and the FET.
  Its G_L pad faces the gate and its V_L pad lines up with the source-pin via row. The series diode of each pair (D23 and
  the rest) stays in the port block.
- R1 (G1) and R31 (GA1) sit at Q1's and Q8's gate pins. R2 and R32 stay with their controllers: Q2's and Q9's gates have
  no room, because the MID band, the SW_D strip and the 1.3 mm gap to Q1/Q8 fill it.
- U1 stays at RS1 because the Kelvin rule needs it there, so GATE runs about 35 mm to Q1/Q2. GATE carries the
  LM5069's slow charge current and its fault pull-down; keep it on F.Cu over In1, with a GND return beside it.

## Air

- Leave an air lane from each fan zone out to an edge (top or bottom). Keep the terminal-free edges clear.
- RS1 and the busiest port shunts sit under or beside a fan.
- At bring-up, measure case temperatures at 60 A for 10 min with the shell on.

## Test

- 3 GND test points, one per quadrant.
- Scope-ground pad pairs (signal plus GND within 3 mm) at BAT, SW_D, MID, VBUS and ABS–ABS_N.
- Pads on GATE, GATE_A, UVLO and FLT_A for the close-order test.
