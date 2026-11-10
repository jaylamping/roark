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
  **"Epoxy Filled & Capped" vias.** 27 of its 132 vias sit in SMD pads:
  - the input ceramics' GND pads, which lie inside the VIN pour;
  - C24's and D3's GND pads, inside the +12V pour;
  - the six VIN vias in Q1's drain tab, the heat path to the B.Cu VIN mirror;
  - the Kelvin taps in RS1's and RS2's sense pads;
  - TPV6.

  U1's stock TI footprint also has four 0.2 mm thermal vias in its exposed pad. They are the only drills under 0.3 mm,
  JLC's 6-layer minimum is 0.15 mm, and the project allows 0.2 mm for them.
- Four M3 holes, 3.5 mm in from the corners. The pigtail from the main board's J24 plugs into J1 on the top edge; the
  12 V outputs are on the bottom edge (J2 Jetson, J3 Pi buck, J4 fans, J6 SPARE_ON), and J5 (SPARE_SW) is on the right edge.
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
    order puts HO above LO, while the FET gates put Q1's gate left of Q2's, so one gate trace has to cross the other on a
    single-sided board. LO is the one that crosses: its return, PGND, is the In1 plane directly above In3.
  - BST runs on In2 under HO and SW to C17. R5 (2.2 Ω) takes the bootstrap back to the SW track.
  - VCC goes to C16 at the pin; PGND has its own via.
  - ILIM runs on In2, shielded by In1, to R6 at the SW track, with C18 at the pin.
- **Pours:** VIN_P from J1's pins to the filter (F.Cu and B.Cu), VIN (F.Cu and a B.Cu mirror), VOUT (F.Cu and B.Cu),
  +12V, and the three fused outputs. GND: solid planes on In1 and In4, fills on F.Cu, In2, In3 and B.Cu.
- **Meters:** Kelvin taps from the shunts' sense pads. RS1's P runs on In2 and N on In3 to U2. RS2's N runs under U4's
  body and its P on In2 up the right edge.
- **Thermal relief:** pads in the current paths and the hot loop are joined in full (the FETs, both inductors, C1–C13,
  C24, D1, D3–D5, F1–F3, the shunts' current pads). Every other pad on a pour has thermal relief, so it hand-solders.

## Current paths ([tools/pour_buck.py](tools/pour_buck.py), IPC-2221B at the narrowest cut, the main board's method)

| Path | Current | Narrowest cut (as one 2 oz outer layer) | Rise | Limit |
| --- | --- | --- | --- | --- |
| VOUT, L2 to RS1 | 12 A | 4.6 mm | 10.1 °C | 20 °C |
| +12V, RS1 into the distribution pour | 12 A | 4.0 mm | 12.7 °C | 20 °C |
| SW node, Q2 to L2 | 12 A | 6.2 mm | 6.1 °C | 20 °C |
| VIN, L1 to the caps and Q1 | 3.5 A | 23.5 mm | under 1 °C | 10 °C |
| VIN_P, J1 to the filter | 3.5 A | 4.3 mm | 0.7 °C | 10 °C |
| Jetson / Pi outputs | 5 A each | 1.6 mm | 7.6 °C | 20 °C |
| fan output | 2 A | 1.6 mm | 0.9 °C | 20 °C |

The eFuse supplies and outputs (4 A class) are hand-laid tracks 0.6–1.2 mm wide.

## The one cross-board rule

No E-stop or latch net crosses to this board, except SP_EN, which carries SPARE_SW's enable from the main board's RUN
(J1 pin 9). SP_EN is in the main board's E-stop class: about 3 MΩ of leakage from 54 V into it would turn SPARE_SW on
during an E-stop.

So here too it keeps **1.5 mm on every layer** to the copper at or switching up to 54 V: VIN_P, VIN, VIN_C, SW, HO, BST,
BST_R, ILIM, EN and ON_N. The routers run with those nets on the 54 V list (`MARENGO_HV_EXTRA` in build_buck.sh), the
B.Cu VIN_P pour stops at X 15.7 to clear J1's pin 9, and [tools/spacing_buck.py](tools/spacing_buck.py) counts the pairs:
0.

## Checks ([tools/verify_buck.sh](tools/verify_buck.sh), self-test [tools/verify_selftest_buck.sh](tools/verify_selftest_buck.sh))

- DRC with schematic parity: every violation type is a hard error except the three cosmetic silkscreen types; any parity
  issue or open connection fails.
- spacing_buck, joint_check, the designed copper against copper_buck.py, pour_buck.
- The order package against the board file: fab_check, the main board's script, with the buck's stem, outline and no
  B.Mask openings.
- bom_check: the BOM files and the kit against both netlists.

The self-test breaks a copy of the board in five ways (a dangling track, a parity change, SP_EN near VIN, the designed gate
copper moved, a slot across the 12 A paths), feeds verify a kicad-cli that fails or reports nothing, and breaks the order
package three ways. Every case must fail, and the real board must pass.

## Exceptions

1. LO on In3 with two vias (gate drive, above).
2. Via in pad at the 27 places listed under Board, plus U1's 0.2 mm footprint vias.
3. The test points are bare pads, not parts.
4. The main board's E-stop and latch rules don't apply here; only SP_EN's 1.5 mm does.

## Bring-up (bench supply, current-limited, before the main board or the pack)

Wash and dry the board first. Use no load until step 6; scope ground at the GND test pads.
1. **Ohmmeter, unpowered:** VIN_P–GND (TPV13–TPV5) and VOUT–GND (TPV3–TPV5) are not shorts. TPV1 (VIN) to TPV2 (SW) is
   not a short: that would be Q1.
2. **5 V, limit 50 mA, into J1 pins 1–2:** under 1 mA, and nothing warms. A reversed supply makes D1 conduct: that is
   the crowbar working.
3. **24 V, limit 100 mA, ON_N (J1 pin 5) open:** EN (TPV7) is held low by Q3, and the converter is off. VCC (TPV8) is low.
4. **36 V, J1 pin 5 to GND (on):**
   - EN rises above 1.2 V, SS (TPV9) ramps, VCC is about 7.5 V and VOUT (TPV3) is 12.0 V ± 2 %.
   - Input current is about 10–20 mA with no load.
   - Scope SW (TPV2): clean 400 kHz edges, and the ringing peak under 80 V at 54.6 V in (step 5).
5. **Raise to 54.6 V:** VOUT stays at 12.0 V. Lower slowly: the converter turns off at about 27.2 V and back on at about
   30.2 V (UVLO).
6. **Load steps on +12V with an electronic load:** 1 A → 10 A at 36 V and at 54.6 V. VOUT stays within ± 5 %.
   - **Measure the loop:** replace R7 (0R) with an injection resistor. The crossover should be near 40 kHz with at least
     45° of phase margin. This is with the 330 µF on +12V, which TI's compensation does not include.
   - **12 A for 10 minutes:** Q1, Q2 and L2 stay under 100 °C, and the pours near RS1 stay warm, not hot.
7. **Outputs:**
   - F1–F3 pass to J2–J4.
   - SPARE_ON (J6) is on with +12V.
   - SPARE_SW (J5) follows SP_EN: pull J1 pin 9 to 3.3 V through 100 kΩ and it is on; open it and it drops (the 68 kΩ
     pull-down).
   - Short each eFuse output to GND briefly: it limits and retries.
8. **I²C:** with the Pi's 3.3 V and pull-ups on J1 pins 6, 11 and 12, the meters answer at 0x4D (U2) and 0x47 (U4),
   and the bus voltage and current read right against the bench supply.
9. **Then on the main board's J24:** U7 must reach PGD inside its timer into this board's input (main board bring-up,
   REV_B_PARTS step 6).

Conformal coat after bring-up, as on the main board, with J1–J6, the test pads and the holes masked.
