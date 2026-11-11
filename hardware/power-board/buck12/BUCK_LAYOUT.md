# 12 V buck board: layout rules, exceptions, bring-up

The board in [layout/marengo_buck12.kicad_pcb](layout/marengo_buck12.kicad_pcb) is built from the schematic by
[tools/build_buck.sh](tools/build_buck.sh) and checked by [tools/verify_buck.sh](tools/verify_buck.sh). Its order package
is in [fab/](fab/) ([tools/fab_package_buck.sh](tools/fab_package_buck.sh), checked by
[tools/fab_check_buck.sh](tools/fab_check_buck.sh)). The circuit is LM5146, 36–54.6 V in, 12 V at 12 A, 400 kHz
([gen_buck.py](gen_buck.py)).

## Board

- **60 × 85 mm**, six layers, the main board's stack and rules: 2 oz outer, 0.5 oz inner, OSP, 0.2 mm track and space,
  0.6/0.3 mm vias, 0.5 mm to the edge, conformal-coated after bring-up as the main board is
  ([tools/project_buck.py](tools/project_buck.py) copies the main board's settings).
- **One order with the main board:** a second design in the same order, same options. The buck board also needs
  **"Epoxy Filled & Capped" vias** (JLC's default on 6 layers and up). 28 of its 139 vias sit in SMD pads:
  - the input ceramics' GND pads (C3–C8), which lie inside the VIN pour, and C1's and C2's;
  - C24's and D3's GND pads, inside the +12V pour;
  - the six VIN vias in Q1's drain tab, the heat path to the B.Cu VIN mirror;
  - the Kelvin taps in RS1's and RS2's four sense pads;
  - TPV6.

  U1's stock TI footprint also has four 0.2 mm thermal vias in its exposed pad. They are the only drills under 0.3 mm;
  JLC fills and caps via-in-pad holes from 0.15 to 0.55 mm and its multilayer minimum is 0.15 mm (below), so they stay.
- **Four M3 holes**, 3.5 mm in from the corners, **not bonded to the frame**: a copper keep-out of 3.8 mm radius on every
  layer round each one (as the main board's M3 holes), so the screw head, washer or standoff touches no copper.
  The pigtail from the main board's J24 plugs into J1 on the top edge; the 12 V outputs are on the bottom edge (J2 Jetson,
  J3 Pi buck, J4 fans, J6 SPARE_ON), and J5 (SPARE_SW) is on the right edge.
- **Thirteen bare test pads (TPV1–TPV13):** VIN_P, VIN, SW, VOUT, +12V, 2 × GND, EN, VCC, SS, COMP, SPARE_SW and SPARE_ON.
  They are copper only, not in the schematic or the BOM, so they don't change either.

## Placement ([tools/place_buck.py](tools/place_buck.py))

Every part is at a listed position.
- **Left column:** the input filter. D1 (crowbar), C1, L1 (2.2 µH) and C2 (47 µF Chemi-Con MVH, 12.5 mm).
- **Power stage:** six input ceramics in a column on Q1's drain tab. Q1 and Q2 sit side by side (rotated 180°), so Q1's
  sources face Q2's drain tab. L2 is directly below, and the five output caps are under L2.
- **Controller:** U1 sits above Q1's gate with its gate-drive pins (12–19) facing the FETs. The analog parts (RT, SS,
  compensation, feedback) are in the quiet top corner above U1, away from SW. The enable parts are on the right.
- **Distribution:** in the lower half. RS1 and its INA237 (U2) are at the output; the +12V pour feeds C24, D3, F1–F3 and
  the two eFuses; RS2 and U4 sit with the SPARE_SW eFuse.

## Power stage copper ([tools/copper_buck.py](tools/copper_buck.py): locked, `MODE=check` in verify)

- **Hot loop** (input caps → Q1 → Q2 → back): Q1's drain and the caps' VIN pads share one F.Cu pour. The return runs
  from Q2's sources through vias into the solid In1 GND plane, about 0.2 mm below L1, and up through the vias in the caps'
  GND pads. The loop area is the plane's dielectric thickness times about 18 mm. This is TI's EVM arrangement (LM5146
  datasheet, 11.1–11.2).
- **SW node:** Q1's source pins, Q2's drain tab and L2's pad in one F.Cu pour of about 80 mm², with nothing else on
  other layers. A 0.5 mm track carries it to the bootstrap resistor and the ILIM resistor.
- **Gate drive (LM5146 11.1.2):**
  - HO runs straight down 7.5 mm from pin 18 to Q1's gate on F.Cu, 0.5 mm wide. The SW pin's track runs beside it,
    0.95 mm centre to centre, as the HO/SW pair.
  - **Exception: LO crosses on In3** (0.65 mm wide, two 0.6/0.3 mm vias; TI allows vias of 0.5 mm or more). U1's pin
    order puts HO above LO, while the FET gates put Q1's gate left of Q2's, so one gate trace has to cross the other.
    LO is the one that crosses: its adjacent return is the solid In4 GND plane directly below In3 (In1 is above
    In2, with the In2 GND fill between).
  - BST runs on In2 under HO and SW to C17. R5 (2.2 Ω) takes the bootstrap back to the SW track.
  - VCC goes to C16 at the pin; PGND has its own via.
  - ILIM runs on In2 at Y 18.3, between BST (In2) and LO (In3), to R6 at the SW track, with C18 (18 pF 100 V C0G) at
    the pin. It crosses LO once and never runs over it.
- **Pours:** VIN_P from J1's pins to the filter (F.Cu and B.Cu), VIN (F.Cu and a B.Cu mirror), VOUT (F.Cu and B.Cu,
  both carried past RS1's sense cut-out), +12V, and the three fused outputs. GND: solid planes on In1 and In4, fills on
  F.Cu, In2, In3 and B.Cu.
- **Meters:** Kelvin pairs from the shunts' sense pads (a via in each sense pad), **both legs on In2**, between the In1
  GND plane and the In3 GND fill, 0.6 mm centre to centre from where they meet to the vias at the meter's pins.
  The sense pads sit at opposite corners of the 2512 four-terminal footprint, so each pair has an unpaired run as long
  as the shunt; [tools/kelvin_buck.py](tools/kelvin_buck.py) measures the rest: RS1 → U2 59.0 % paired (floor 55 %),
  RS2 → U4 45.6 % (floor 40 %).
- **Thermal relief:** pads in the current paths and the hot loop are joined in full: the FETs, both inductors, C1–C13,
  C24, D1, D3–D5, F1–F3, the shunts' current pads, and the GND pads of C15, C22, C23 and R3 (small pads that the fill
  reaches from one side only). Every other pad on a pour has thermal relief, so it hand-solders.

## Current paths ([tools/pour_buck.py](tools/pour_buck.py), IPC-2221B at the narrowest cut, the main board's method)

Each cut is the net's copper on each layer counted once (zone fills and tracks merged). The VOUT and +12V windows run
to RS1's pads.

| Path | Current | Narrowest cut (as one 2 oz outer layer) | Rise | Limit |
| --- | --- | --- | --- | --- |
| VOUT, L2 to RS1 | 12 A | 11.6 mm at X 50.25 (F.Cu 4.7 + B.Cu 6.9) | 2.2 °C | 20 °C |
| +12V, RS1 into the distribution pour | 12 A | 3.6 mm at X 49.75 | 15.1 °C | 20 °C |
| SW node, Q2 to L2 | 12 A | 6.2 mm | 6.1 °C | 20 °C |
| VIN, L1 to the caps and Q1 | 4.3 A | 23.5 mm | 0.1 °C | 10 °C |
| VIN_P, J1 to the filter | 4.3 A | 4.3 mm | 1.1 °C | 10 °C |
| Jetson / Pi outputs | 5 A each | 1.6 mm | 7.6 °C | 20 °C |
| fan output | 2 A | 1.6 mm | 0.9 °C | 20 °C |

Input current at full load: 144 W out at about 94 % is 153 W in, **4.3 A at 36 V** (2.8 A at 54.6 V). The eFuse
supplies and outputs (4 A class) are hand-laid tracks 0.6–1.2 mm wide.

## The one cross-board rule

No E-stop or latch net crosses to this board, except SP_EN, which carries SPARE_SW's enable from the main board's RUN
(J1 pin 9). SP_EN is in the main board's E-stop class: about 3 MΩ of leakage from 54 V into it would turn SPARE_SW on
during an E-stop.

The rule is 1.5 mm on every layer to the copper at or switching up to 54 V; this board keeps **1.7 mm**, the rule plus
0.2 mm for etch and registration tolerance. The 54 V nets are listed once, in [tools/hv_buck.py](tools/hv_buck.py), with
the 1.7 mm. SP_EN itself is laid by hand on In2 (copper_buck.py): from J1 pin 9 below J1's row, down the corridor
between the VIN via column and Q1's drain vias, and under the output caps to U3's enable. The VIN_P pours step back from
J1 pin 9; the routers keep 1.7 mm (build_buck.sh passes hv_buck.py's list and distance to them).
[tools/spacing_buck.py](tools/spacing_buck.py) measures every pair: the closest is **1.92 mm** (J1 pin 9 to the F.Cu
VIN_P pour).

## Checks ([tools/verify_buck.sh](tools/verify_buck.sh), self-test [tools/verify_selftest_buck.sh](tools/verify_selftest_buck.sh))

- DRC with schematic parity: every violation type is a hard error except the three cosmetic silkscreen types; any parity
  issue or open connection fails; the report must be this run's (its date is checked against the run's start).
- spacing_buck (SP_EN 1.7 mm; fails when it compared nothing), kelvin_buck (both pairs traced pad to pin, one inner layer,
  over the floor), holes_buck (the keep-outs and no copper inside them), joint_check.
- The designed copper against copper_buck.py: tracks and vias, and every zone by net, layer, priority, clearance and
  outline (not by name).
- pour_buck.
- The order package against the board file: fab_check, the main board's script, with the buck's stem, outline and no
  B.Mask openings.
- bom_check: the BOM files and the kit against both netlists.

The self-test feeds verify 17 broken inputs and expects each one's failure lines (it prints the counts):
- 10 broken boards (tools/mutate_buck.py):
  - a dangling track and a parity change;
  - SP_EN 1 mm from VIN, and SP_EN moved off the E-stop class (an empty spacing check);
  - the designed gate copper moved, and the hot-loop GND plane moved 100 mm with its name kept;
  - a slot across the 12 A paths, and the VOUT neck at RS1 narrowed;
  - an unpaired Kelvin leg;
  - an M3 hole without its keep-out.
- 4 kicad-cli stand-ins: one exits non-zero, one omits the parity key, one writes nothing, and one writes a report dated
  before the run.
- 3 broken order packages: a moved part, a missing Gerber, no gerbers/.

The real board must pass.

## Exceptions

1. LO on In3 with two vias (gate drive, above).
2. Via in pad at the 28 places listed under Board, plus U1's 0.2 mm footprint vias.
3. The test points are bare pads, not parts.
4. The main board's E-stop and latch rules don't apply here; only SP_EN's distance does (1.7 mm kept, 1.5 mm rule).

## Ratings and datasheet answers (review of 2026-11-10; D3, R6 and C18 changed after it)

- **U3 EN against the TPS259541 threshold.** EN/UVLO rises at 1.13–1.27 V and falls at 1.03–1.17 V (datasheet 7.5).
  SP_EN comes from the main board's RUN through 100 kΩ and a BAV19W, into the 68 kΩ pull-down here. latch_sim.py puts
  RUN at 6.8 V when the latch is closed (every hFE case), so EN = (6.8 − 0.6) × 68 / 168 = **2.5 V** (2.3 V with 5 %
  resistors at their worst), twice the 1.27 V maximum. 1.34 V at EN would need RUN at about 3.9 V; RUN is either 6.8 V
  or 0 V. SPARE_SW turns off when RUN falls through 3.1–3.5 V. No change.
- **SP_EN's closest point against etch tolerance.** It was 1.55 mm (the B.Cu VIN_P pour's edge), 0.05 mm over the rule:
  inside what over-etch, under-etch and layer registration can take away. The pours now step back, SP_EN is laid by
  hand, the routers keep 1.7 mm, and spacing_buck fails under 1.7 mm. Closest pair now 1.92 mm.
- **Does JLC fill 0.2 mm via-in-pad holes on 2 oz copper?** Yes. JLC's capabilities page: via-in-pad (epoxy or copper
  paste filled, plated over) is "the default for 6-layer and above multilayer boards" and is "compatible with via
  diameters from 0.15 to 0.55 mm"; the multilayer minimum via hole is 0.15 mm, with no separate minimum for 2 oz outer
  copper (2 oz sets the track/space minimum, 0.15 mm, and the PTH annular ring). U1's 0.2 mm thermal vias stay.
- **C24 (EEH-ZA1E331V, 25 V) and the eFuses against the +12V back-feed clamp.**
  - **Change.** D3 is now **SMBJ12A** (Diodes Incorporated SMBJ12A-13-F, DigiKey SMBJ12A-FDICT-ND, same SMB footprint).
    It was SMBJ15A, which clamps at up to 24.4 V. That is over the TPS259541 eFuses' (U3, U5) **20 V absolute maximum**
    (TPS2595 datasheet, 7.1).
  - **SMBJ12A** (Bourns/JEDEC SMBJ table): VRWM 12 V; breakdown 13.3–14.7 V at 1 mA; I_R 1 µA max at 12 V; clamp 19.9 V at
    its 30.2 A (10/1000 µs) rating.
  - **No conduction in regulation.** The highest regulated output is FB 0.808 V × (1 + 21.21 k / 1.485 k) = **12.35 V**
    (±1 % reference, 1 % divider). A 5 % load-release overshoot (the bring-up limit) gives 12.96 V. Both are under the
    13.3 V minimum breakdown, so D3 draws well under 1 mA.
  - **Leakage at 12.3 V.** That is 2.5 % over VRWM, where the spec is 1 µA; between VRWM and VBR the current rises
    exponentially but stays under the 1 mA that defines VBR. Typically microamps, at most 12 mW: acceptable.
  - **Clamp at the largest realistic back-feed.**
    - Where back-feed comes from: the buck runs in diode emulation (SYNCIN to GND), so it cannot sink, and back-feed goes
      into D3. The source is the neck and jaw servos, back-driven by hand through SPARE_SW. U3 does not block reverse
      current.
    - Size: they draw at most U3's 4.42 A forward limit, so take **5 A**.
    - Clamp at 5 A: dynamic resistance (19.9 − 14.7) / 30.2 = 0.17 Ω, so 14.7 + 0.86 = **15.6 V**, or about 16.5 V with
      the breakdown voltage's temperature rise at 85 °C.
    - Even at its full 30.2 A rating it clamps at 19.9 V (25 °C), under 20 V.
  - **C24** (25 V, surge 28.75 V) sees at most 19.9 V.
- **C18 and the current limit.**
  - **Change.** R6 is now **330 Ω** (Stackpole RMCF0603FT330R) and C18 is **18 pF 100 V C0G** (KEMET C0603C180J1GACTU,
    DigiKey 399-C0603C180J1GACTUCT-ND). 330 Ω × 18 pF = **5.9 ns** against TI's "approximately 6 ns"; 15 pF would give
    4.95 ns. ILIM swings with SW up to VIN, hence 100 V. (It was 402 Ω and 15 pF, 6.0 ns; before that 100 pF 50 V.)
  - **Valley limit** (LM5146 eq. 6): I_valley = I_RDSON × R_ILIM / R_DS(on)Q2, with I_RDSON 180–220 µA at 25 °C and
    +4500 ppm/°C. Q2 (BSC040N10NS5) gets VGS = VCC, about 11.6 V once VOUT is up (D2): 3.5 mΩ typ, 4.0 mΩ max at 10 V and 25 °C.
  - **Hot corner** (T_J 125 °C; I_RDSON 180 µA × 1.44 = 259 µA; R_DS(on) 4.0 mΩ × 1.7 = 6.8 mΩ):
    - valley limit **12.6 A**;
    - output limit with the smallest ripple, 13.7 A.
  - **Margin.** The highest valley at a 12 A load comes with the smallest ripple: 36 V in, L +20 % (8.16 µH),
    f +5 %, ΔI_L 2.33 A, so the valley is 12 − 1.17 = 10.8 A. The hot limit is **16 % over** it. (The 15 % asked for is
    met; at T_J 100 °C it is 17 %.) Through soft start VCC is the internal 7.5 V, and R_DS(on) is about 10 % higher.
  - **Soft start.**
    - Time: SS 47 nF × 0.8 V / 12 µA max = 3.1 ms.
    - Load: the output capacitance, 330 µF + 20 % plus 5 × 22 µF (506 µF without DC-bias derating), draws
      506 µF × 12 V / 3.1 ms = 1.9 A, plus the loads that start during the ramp (U5 enables at about 4.8 V).
    - Even with 5 A of start-up load, under 7 A against the 11.4 A hot limit at VCC 7.5 V: it does not trip.
  - **Cold corner** (25 °C, 220 µA, 3.5 mΩ; colder is lower, as I_RDSON's tempco outruns R_DS(on)'s):
    - valley limit **20.7 A**, typical (200 µA) 18.9 A;
    - output limit 22.4 A worst, 20.5 A typical.
  - **L2 in a cold hard short.**
    - Peak: with VOUT near 0 the ripple is only the minimum on-time ramp, 54.6 V × 50 ns / 5.44 µH = 0.5 A. So the peak
      is about **21.2 A** worst (19.4 A typical), under the XAL1010-682's **21.8 A I_sat** (30 % inductance drop, Coilcraft).
      With 402 Ω it was about 26 A.
    - In an overload with VOUT still up, the peak adds the full ripple: 25 A worst at 54.6 V with L −20 %, 22 A typical.
      That is past the 30 % point, until hiccup stops it. Valley sensing on R_DS(on) spans 1.75× between the corners, so
      no R_ILIM holds both the hot margin and the cold peak in overload.

## Bring-up (bench supply, current-limited, before the main board or the pack)

Wash and dry the board first. Scope ground at the GND test pads. Every step names the bench supply's current limit.
1. **Ohmmeter, unpowered:** VIN_P–GND (TPV13–TPV5) and VOUT–GND (TPV3–TPV5) are not shorts. TPV1 (VIN) to TPV2 (SW) is
   not a short: that would be Q1.
2. **5 V, limit 100 mA, into J1 pins 1–2:** under 1 mA, and nothing warms. A reversed supply makes D1 conduct (the
   limit holds it at 100 mA): that is the crowbar working.
3. **24 V, limit 100 mA, ON_N (J1 pin 5) open:** EN (TPV7) is held low by Q3, and the converter is off. VCC (TPV8) is low.
4. **36 V, limit 1 A (soft start charges about 0.44 mF of output capacitance to 12 V in about 4 ms: about 0.5 A in),
   no load, J1 pin 5 to GND (on):**
   - EN rises above 1.2 V, SS (TPV9) ramps, and VOUT (TPV3) is 12.0 V ± 2 %.
   - VCC (TPV8) reads about **11.6 V** once VOUT is up: it is fed from VOUT through D2. **7.5 V means D2 is open**
     (U1 is running from its internal regulator).
   - Input current settles at about 10–20 mA.
   - Scope SW (TPV2): clean 400 kHz edges.
5. **Raise to 54.6 V, limit 1 A, no load:** VOUT stays at 12.0 V; the SW ringing peak is under 80 V. Lower slowly: the
   converter turns off at about 27.2 V and back on at about 30.2 V (UVLO).
6. **Measure the loop, on its own, before any load step: 36 V, limit 1 A, light load (0.5–1 A on +12V).** Replace R7
   (0R) with an injection resistor. Target crossover **10–12 kHz** with at least 45° of phase margin: the 330 µF on
   +12V, which TI's compensation does not include, holds the crossover far below 40 kHz. Outside that, stop
   and recompute the compensation before loading.
7. **Load steps on +12V with an electronic load, limit 5 A:** 1 A → 10 A at 36 V (about 3.6 A in) and at 54.6 V.
   VOUT stays within ± 5 %.
8. **12 A for 10 minutes, 36 V, limit at least 5 A** (4.3 A in): Q1, Q2 and L2 stay under 100 °C, and the pours near RS1
   stay warm, not hot.
9. **Outputs, limit 5 A:**
   - F1–F3 pass to J2–J4.
   - SPARE_ON (J6) is on with +12V.
   - SPARE_SW (J5) follows SP_EN: pull J1 pin 9 to 3.3 V through 100 kΩ and it is on; open it and it drops (the 68 kΩ
     pull-down).
   - Short each eFuse output to GND briefly: it limits and retries.
10. **I²C, limit 1 A:** with the Pi's 3.3 V and pull-ups on J1 pins 6, 11 and 12, the meters answer at 0x4D (U2) and
    0x47 (U4), and the bus voltage and current read right against the bench supply.
11. **Then on the main board's J24:** U7 must reach PGD inside its timer into this board's input (main board bring-up,
    REV_B_PARTS step 6).

Conformal coat after bring-up, as on the main board, with J1–J6, the test pads and the holes masked.
