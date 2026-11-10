# Power board rev B: layout rules

2026-11-07, rev B5. These rules come from the Opus round 5 layout review ([opus-review-r5/5-layout.md](https://github.com/jaylamping/marengo/blob/main/hardware/electrical/pdb/design/opus-review-r5/5-layout.md)) and Joey's single-sided rule. They replace LAYOUT_NOTES.md, which still describes rev A. schematic/tools/place.py follows them.

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
  No bars. Pour widths on the routed board (2026-11-09): BAT 27 mm on L1; VBUS 24 mm on L6 where no via passes; under the meter block signal vias pass through it (each clears a 1.1 mm hole at 0.25 mm clearance, an E-stop via 3.6 mm at 1.5 mm), and at the RUN_P via the L6 pour is down to about 22 mm with no L1 copper alongside, so VBUS is under its 27.5 mm target there; elsewhere L1 adds about 3–7 mm;
  MID 23 mm on L6 plus up to 27 mm on L1; SW_D 22 mm on L6 plus 13 mm on L1; port legs about 5 mm on each outer layer. **Open before fab:** BAT (27 mm, L1 only) and the port legs (about 10 mm
  in total) sit just under their targets: widen them or mirror BAT on L6. The two 0.5 oz GND planes return 60 A across
  about 90 mm (about 0.8 mOhm, about 3 W spread over the board). By IPC-2221B's internal curve the two planes alone rise
  about 44 °C at 60 A (about 7,900 mil² for 20 °C, about 4,900 mil² there); the GND fill on L1 and L6 carries part of
  the return, but its width along the path isn't measured yet. **Open before fab:** measure the outer GND return and
  show the rise, or add outer GND copper. At layer changes, use about 1 A per 0.3 mm via.

## Power path

- **Flow order down the board:** BAT pair (top edge) → absorber cluster and RS1 → bank A → bank B (under the upper fan) → bus caps → port breakers → limb pigtails. Remove the old B → A → B detour.
- **Pack entry:** the BAT and GND 8 AWG pair (4.5 mm holes, 8 mm pads, 14 mm pitch; to an XT90) sits side by side on the top edge, in the frame's pack cable path. **Keep-out: no components in X −5..25, Y 315–340** (the leads run up the face and bend over the top edge at R15 from about Y 330); the pads sit in that strip. Solid connections to every copper layer, no thermal reliefs. A cable-tie hole each side of the pair.
- **Absorber cluster:**
  - D7, D21 and the eight cans in one cluster at the BAT entry; R53 (the ABS_N to GND link) under the can stack.
  - ABS and ABS_N are pours directly over unbroken L2.
  - R53 is at least 5 mm wide, with 10 or more vias to the GND planes, L2 and L5 (In1, In4).
  - **Loop:** extracted from the 4-layer routed copper by `schematic/tools/absorber_loop.py`: **LABS 5.4 nH**, LBAR 2.0 nH.
    **Rerun absorber_loop.py and absorber_sim on the 6-layer board before fab.** Microstrip over In1
    (h 0.21 mm; tools/stack.py keeps it until JLC confirms the 2 oz 6-layer prepreg, since a thinner one only lowers the
    loop) per segment, weighted by its share of the current, plus assumed part ESLs: 1.5 nH per SMC diode, 3 nH per
    can, 1 nH for RS1. The ABS_N spine down to R53 is the largest term (about 2.4 nH), because R53 sits at the bottom of
    the stack. 2 nH isn't reachable with these parts; the ceramics below take the fast edge instead.
- **Pack-entry ceramics C89–C92** (4 × 4.7 µF 100 V 1210, BAT to GND, about 8.8 µF at 54 V bias): two between RS1 and D7,
  two in the BAT arm by D1, GND pads via-gridded to In1. **Bank A drain ceramics C87/C88** (2 × 4.7 µF 100 V): beside
  RS1's SW_D pad, GND vias to In1. absorber_sim (real turn-off, all corners): BAT 73.8–73.9 V, bank A drain 81–84 V,
  with a 3–5 nH absorber loop; **at the extracted 5.4 / 2.0 nH: BAT 73.8 V, bank A drain 84.5 V** (100 V FETs).
- **FET copper and the heatsink (option D, [THERMAL_OPTION.md](THERMAL_OPTION.md)):**
  - 2.7 W per FET at 60 A goes down into a finned heatsink under the board (X −33..33, Y 200–305).
  - About 50 × 0.3 mm vias per tab, at the pad edge and under it, filled and capped (free at 6 layers) so they
    don't wick solder on the hot plate.
  - L6: bare copper (no mask, OSP) 15 × 15 mm under each FET, for the insulating gap pad. Nothing else on L6 inside
    the heatsink zone except those pads and GND fill. **Open (Joey's call):** the routed board breaks this rule: the
    VBUS spine and the signal vias through it sit on L6 inside the heatsink zone. Under the gap pad they are insulated
    from the heatsink by the pad and the mask, so either the rule becomes "masked copper allowed, bare copper only at the
    FET pads", or the spine and the vias move out of the zone.
  - Heatsink holes HS1 (0, 286) and HS2 (0, 204), M3, no copper within 2 mm; the MID pour flows around HS1.
  - Keep all four bank FETs inside the upper fan footprint (|X| ≤ 20, Y 264–304).
  - Check with a coupon or quick FEM; a clip-on heatsink per bank is the fallback.
- **Bus caps:**
  - within 20 mm of bank B's source pins and of the port FET drains;
  - C38 and the other 12.6 mm cans stay out of the fan-zone height limit (Z 61.5 ceiling at |X| ≤ 20).
- **Port breakers:**
  - each TPS48111 within 10 mm of its FET;
  - PD → 22 Ω → gate at the gate pin;
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
  - symmetric between the two FETs of a bank. Not met yet: R2 and R32 sit at their controllers while R1 and R31 sit at
    the gates (Gate parts below), an open item for the layout review.
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
- At least 1.5 mm (2 mm preferred) to any BAT, SW_D, MID, VBUS, ABS, CL_D, BRK_*, SH* or V_L* copper, on all layers, with a GND guard trace or pour between them.
- Why: 0.44 MΩ of leakage from 54 V into UVLO enables bank B by itself.
- No 54 V copper on L2–L5 under the latch block.
- Wash off the flux. The whole board is conformal-coated after bring-up (Clearance below; PRODUCTION_RUN step 10).
- J20 (the loop connector) sits on the far side of the latch block from the converter soft start.

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
    BRK_*, SH*, V_L*, D_L*) on every layer.
  - Copper on 54 V, or riding on a 54 V node (a gate or bootstrap on its source, a sense tap on VBUS), keeps **0.6 mm**
    on the outer layers (0.2 mm inner) to every net of another voltage domain uncoated; the board is coated, so 0.2 mm
    on all layers. Nets in one domain (a port's V_L, G_L,
    GPD/GPU, BST, GC; bank B's MID with GA1/GA2 and BST_A; the VBUS taps) are tens of volts apart at most, so 0.2 mm.
  - Everything else 0.2 mm.
- **Inner GND planes and fills (In1–In4): 0.3 mm zone clearance** (2026-11-09; `PLANE_CLEAR` in
  [schematic/tools/stack.py](schematic/tools/stack.py)). The zones were built with 0.6 mm, the old uncoated outer-layer
  value, and a row of vias at 0.85 mm pitch under a fine-pitch IC then cut the planes away completely. IPC-2221B B1
  (internal conductors, 51–100 V) asks 0.1 mm. With 0.3 mm a 0.6/0.3 mm via keeps 0.45 mm from its drill to the plane
  and a pad without an inner land 0.3 mm. JLCPCB's capability page (read 2026-11-10) asks 0.2 mm from an inner-layer via
  hole to copper and 0.3 mm from a PTH pad hole; all 40 PTH pads here keep their inner lands, so their holes are
  further than 0.3 mm from the planes. The
  outer GND fills keep 0.6 mm. schematic/tools/route_power.py builds the zones with it, schematic/tools/plane_clearance.py sets it
  on a routed board, and route_checks.py check 6 tests it.
- **DRC rules** (layout/marengo_pdu_revb.kicad_dru; a later rule wins in KiCad):
  - `estop_to_54v`: 1.5 mm from net class ESTOP to net class HV54 on every layer (classes set by
    schematic/tools/handfinish_prep.py from schematic/tools/domains.py).
  - **Fine-pitch footprints:** U1 and U7 (LM5069, MSOP-10 0.5 mm) and U2 (TPS7A4001, HVSSOP-8) put their own pads
    0.15 mm apart, so **only clearances between F.Cu pads, tracks and vias that enter that IC's courtyard** (its own
    pads, and each pin's first escape segment) drop to 0.15 mm:
    `(rule fine_pitch_U1 (layer "F.Cu") (constraint clearance (min 0.15mm)) (condition "A.Type != 'Zone' && B.Type != 'Zone' && ((A.memberOfFootprint('U1') && B.intersectsCourtyard('U1')) || (B.memberOfFootprint('U1') && A.intersectsCourtyard('U1')) || (A.intersectsCourtyard('U1') && B.intersectsCourtyard('U1')))"))`,
    and the same for U2 and U7. The rule is limited to F.Cu and never applies to a pour (2026-11-10): KiCad's courtyard
    test is true for copper under the courtyard on any layer and for a whole pour that touches it, so before that
    limit the inner planes and the GND fill came within 0.15 mm of tracks passing under or leaving these courtyards.
  - **U8 has no fine-pitch rule** (removed 2026-11-10). It had one from 2026-11-09, which also let E-stop copper come
    within 0.15 mm of 54 V copper inside its courtyard. Since U8 was turned (E-stop row north, 54 V row south,
    schematic/tools/u8_block.py) nothing needs it: its pads are 0.2 mm apart, and DRC is clean with the 1.5 mm
    E-stop rule and the 0.2 mm default inside U8's courtyard.
  - Outside the courtyards, E-stop copper stays at 1.5 mm from 54 V, and 54 V domains at 0.2 mm (coated).
    schematic/tools/route_checks.py tests the same scope, on the real shapes.
  - U1's UVLO pin sits between SH_P and the GND pins. schematic/tools/route_u1.py therefore draws U1's escapes as single straight
    segments: SH_P and SH_N straight out to RS1, and UVLO inward to a via under the body.
- **Holes:** no copper within 2 mm of the heatsink screw holes HS1/HS2 (the screw and the heatsink aren't insulated from
  it), 0.6 mm round the tie holes and the M3 mounting pads (rule areas from schematic/tools/place.py).

## Routing state (2026-11-10, 6 layers)

Every connection is routed (0 open), with DRC clean (0 clearance, 0 shorts,
schematic parity 0), route_checks clean and check.py at 0 fails. `schematic/tools/verify_board.sh` runs the whole set next to a
copy of the schematic, so the parity check really runs (in layout/ KiCad only prints "Failed to fetch schematic netlist"
and checks nothing; the earlier "parity 0" reports came from that).

How the board got there:
- **Staged scripts** (schematic/tools/route_stages.sh, then the finish_* tools) for the general routing. Generic routers
  stalled at the port taps and at U8, so those two are now designed:
- **Port block template** (schematic/tools/port_template.py for placement and rip-up, port_copper.py for the copper,
  port 1's page mm mapped to the other five; the left ports are the right ports turned 180 degrees, part for part):
  - logic row of the eFuse (EN, INP, PORT_FLT_N, GND): inward to one row of vias under the body, In3 from there;
  - 54 V row: V_L (pin 13) and BST inward to a via each; GPU/GPD outward through the two-track channel under the shunt
    to R4/R5 beside the eFuse; the gate node runs 9 mm on F.Cu to the zener and the gate pin, with one In3 link to the
    slew diode right of the FET (the old gate node looped 30 to 130 mm round the FET);
  - Kelvin pair on In2 down the west side of the eFuse, P outside and N inside at 0.6 mm, feeding R0/C2 and R1 through one
    via each and ending at the meter's pins 10/9: **76 % paired on all six ports**;
  - the sense resistors, the bootstrap and the timer/limit parts keep one In2/In3 lane each across the FET's pin row.
  - Port 2's meter reads D_L2 on pin 8 (deliberate: schematic/gen/gen.py and check.py), so its tap is laid by hand on B.Cu
    to the L6 drain mirror instead of the template's V_L tap.
- **U8 block** (schematic/tools/u8_block.py): U8 sits between bank A/B's tabs (54 V) and the ABS spine (54 V), 7 mm apart,
  so its E-stop pins could not leave sideways at 1.5 mm. U8 is turned so the logic row faces north and the 54 V row
  south; R27, R28, TP13, R36, C29 and R37 sit north of it, every 54 V part south. EN_A and FLT_A run from the pins on
  F.Cu with no via. The SH pair runs on In2 down the middle of the column to R61/R62 (50 % paired, was 48 %).
- **J24** pads 6-12 were on the pinout from before split S1's review fixes; they now follow the schematic (6 +3V3_PI,
  7-8 GND, 9 SP_EN, 10 GND, 11 SCL, 12 SDA, as on the buck board's J1) and their nets are re-routed.
  schematic/tools/sync_netlist.py does this on an existing board, with the values, datasheets and attributes.
- **C81** (the watchdog's CWD cap) sits beside U25's pin 2 (place.py MOVED); the packer had put it 20 mm away.

Measured on the filled zones (schematic/tools/pour_width.py), unchanged from the board before: VBUS neck (Y 178-190)
18.9 mm on L6, MID band (Y 150-158) 21.1 mm (10.0 mm L1 + 11.1 mm L6). Signal vias in the VBUS band (X 130-160,
Y 180-190): 18 (were 24).

**G2** (Q2's gate to R2) is routed under an exception (listed below; to be confirmed at the review). Q2's gate pin lies
in a 1.7 mm slot between Q1's tab and Q2's own pins, under the MID band on L1 and over the MID mirror on L6, so G2 can
only leave through a via in the L6 MID mirror or on F.Cu across the L1 MID band. R2 at the gate (as R1 is at Q1's) was
looked at first: it fits in the slot, but GATE would then need the same via through the mirror to reach it, so it removes
nothing. G2 takes one via at (149.9, 160.19), In3 west under Q1, a second via at (130.2, 167.0) outside the pours, In2
north and a third via at R2: 55.8 mm, 3 vias. Both measured widths are unchanged, since the via is south of the MID neck.

Kelvin pairs still poorly paired: **SH9 (8 %)**. RS9's N sense pad is on the far side of its BAT pad from U7, so N has to
pass under that pad on In2 while P stays on F.Cu; a better pair needs RS9 or U7 moved.

## Exceptions and hand-laid copper (for the review)

Rule exceptions on this board, each tested or bounded by a check:

| # | Exception | Where | Status | Held by |
|---|---|---|---|---|
| 1 | G2 has a via through the L6 MID mirror | (149.9, 160.19), at Q2's gate | accepted in the project thread, 2026-11-10; to confirm at the review | route_checks 7 (domains.MID_VIA_OK) |
| 2 | G2 has 3 vias (gate nets: 2) | (149.9, 160.19), (130.2, 167.0), (125.6, 139.8) | accepted in the project thread, 2026-11-10; to confirm at the review | route_checks 8 (domains.GATE_VIA_OK) |
| 3 | GATE_A has 3 vias, one inside the MID outline at Q8's gate (132.0, 141.46) | from the staged routing, unchanged | not yet reviewed | route_checks 7, 8 |
| 4 | GA2 has a via inside the MID outline, in the pour's dead tip beside U8 beyond the tabs | (167.95, 157.0); the old board had TMR_A's via in the same tip | not yet reviewed | route_checks 7 |
| 5 | Fine-pitch courtyards: 0.15 mm between F.Cu pads, tracks and vias inside U1's, U2's and U7's courtyards (not pours, not inner layers). U8's rule is removed | .kicad_dru | in force; U8's removed 2026-11-10 | DRC, route_checks 1/2 |
| 6 | Inner GND planes and fills at 0.3 mm zone clearance (outer fills 0.6 mm) | In1-In4 | accepted in the project thread, 2026-11-10; to confirm at the review | route_checks 6 |
| 7 | Signal and GND vias pass through the L6 VBUS sheet: 142 inside VBUS pour outlines (126 before this routing), 18 of them in the band X 130-160, Y 180-190 (24 before) | under the meter blocks | band rule: no new ones | pour_width.py (neck 18.9 mm, unchanged) |
| 8 | Masked copper (the VBUS sheet and those vias) inside the heatsink zone on L6 | X -33..33, Y 200-305 | open, Joey's call (FET copper, above) | none |
| 9 | SH9 Kelvin pair 8 % paired | RS9 to U7 | open: needs RS9 or U7 moved | route_checks 3 (report only) |
| 10 | VBUS under its 27.5 mm target at the neck (18.9 mm, L6 only); BAT and the port legs just under theirs | Board, above | open before fab | pour_width.py |

Copper laid from hand-specified coordinates rather than found by a router. The two templates are scripts and re-run; the
rest was laid once with schematic/tools/lay_path.py (checked against the same clearances as the finishing router) and exists only
in the board file:

| What | Path (page mm) |
|---|---|
| Port template, six ports | schematic/tools/port_copper.py ITEMS, mapped by port_template.T() |
| U8 block | schematic/tools/u8_block.py ITEMS |
| D_L2 tap to U12 pin 8 (port 2) | F.Cu (134.0, 190.6) to a via at (134.8, 190.05), B.Cu by (133.6, 191.3), (130.8, 191.3), (130.0, 193.5) to (129.4, 194.3) on the L6 drain mirror |
| G2 | F.Cu (150.95, 160.19) to the via at (149.9, 160.19); In3 by (149.9, 159.2), (140.2, 159.2), (132.4, 165.6) to the via at (130.2, 167.0); In2 by (130.2, 162.6), (131.8, 161.0), (131.8, 147.0) to the via at (125.6, 139.8); F.Cu to R2 pin 2 |
| I2C_SCL exits under the meters | port 2: In2 (135.5, 189.4) to (140.8, 189.1); port 5: In3 (164.5, 236.1) to (159.2, 236.4) |
| At U25 (watchdog), to free its CWD pin | L_E on F.Cu (102.95, 247.75), (102.95, 249.2), (103.5, 249.75), (104.65, 249.75); CWD stub to a via at (104.5, 248.35); VWD link (103.65, 247.75), (103.65, 248.3), (104.0, 249.05), (105.0, 249.05), (105.75, 248.15) |
| GND island link | F.Cu (161.0, 236.8) to (161.4, 237.0) |

Everything else between the templates (the buses between the blocks, EN/INP/PORT_FLT_N runs, the J24 nets, the GND
vias) was found by schematic/tools/finish_route.py, whose result depends on the order of the runs: a rebuild from the placement
gives the same blocks but not the same copper in between. The port template's gate stub start was corrected in
port_copper.py after the six ports were stamped ((168.8, 193.77) to (169.0, 193.77)); on the board the router bridged it.

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
