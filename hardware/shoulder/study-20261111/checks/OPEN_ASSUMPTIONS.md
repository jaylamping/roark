# Left shoulder: what was assumed and never checked (2026-11-13)

A first pass over CONCEPT.md, MEASUREMENTS.md, TORSO_INTERFACE.md, CAD_NOTES.md, PRINT_NOTES.md, the checks and the
look-option notes, plus a walk through the assembly: every cable through every joint, every screw with its neighbours in
place, every fit that rests on a bought part's dimension, heat, loads not run.

- **Ranked by risk to the first print and the first power-up.** 1 is worst.
- **Who settles it:** *here* = analysis in this thread; *run* = a job on holly-pc; *Joey* = a measurement or bench test;
  *other* = another thread.
- Results are filled in as items are settled.

## Ranked table

| # | Item | Where it is stated | What could go wrong | How bad | How to settle | Cost | Result so far |
|---|---|---|---|---|---|---|---|
| 1 | **Yaw dish loop has no slack storage** | CONCEPT.md "Wire passages" ("loop length for ±90 yaw is not checked") | The bundle fills the dish (13.5 mm radial, 5.5 mm axial). The exit-to-window distance changes by up to 97 mm over yaw ±90. The slack has nowhere to go but through the window or back up the exit | Stops the arm, or chafes the trunk through at 48 V | **Joey:** print and run the rig ([CABLE_LOOP_RIG.md](CABLE_LOOP_RIG.md)) | 25 g PLA, 1 h, 20 min test | Found 2026-11-13. Window at 248° passes under the exit at yaw -14°; moved to 68° (one-way loop). Slack still open |
| 2 | **Yaw has no stop and no limit** | MEASUREMENTS.md "Yaw: unlimited by geometry"; SOFTWARE_HANDOFF.md has no yaw position limit; ±90 appears only as a sweep range and in the trunk plan | A runaway or a wrong zero at first power-up winds the bundle round the dish until it tears | Trunk damage, short at 48 V | **Joey / coordinator:** fix the yaw travel. Then a soft limit in SOFTWARE_HANDOFF.md, and decide whether a printed hard stop is wanted | Decision; a stop is a hub and fork change | Open |
| 3 | **Motor heat into PETG** | Not stated anywhere | The RobStride ratings assume an aluminium heat sink (RS02: 6 N·m on 260 × 280 mm; RS03: 20 N·m on 215 × 220 mm; manuals section 1.2). Our mounts are PETG. The drives only fault at a thermistor reading of 135 °C (RS02) and 145 °C (RS03). PETG seats creep from about 60 °C | Seats and bosses relax; the 0.3 N·m joints loosen; continuous torque is well under the rating | **Other (software):** a temperature limit from the drive's reported temperature, well under 60 °C at the housing. **Joey:** a bench run logging temperature at a held torque | A config value; a 30 min bench run | Manual figures read 2026-11-13. Limit value open |
| 4 | **Hub screws too long for the RS02's thread** | A_HUB_LUGS.md "close-fit screw holes": M4 × 30, "about 8 mm of thread engages" | The RS02 drawing gives **6 × M4, depth 7 min** (manual section 1.1), and warns not to exceed the thread depth. The head seats at Y 298.1 (boss 21.76), so M4 × 30 goes in 8.24 mm. It can bottom before it clamps | Hub loose at "tight", or a damaged output | **Here**, done. **Joey:** probe one hole | 5 min | **Settled on paper:** use M4 × 30 with 1.6-2 mm under the head (two washers) for 6.2-6.6 mm, or M4 × 28. Not M4 × 30 bare unless the probe shows 9 mm or more |
| 5 | **Fork front to RS03 output: screw and pin lengths** | PRINT_NOTES.md: "6 × M4 (existing counterbores)", pins "about 8 mm" | The RS03 drawing gives **6 × M4, depth 6, blind** and **3 × Ø4, depth 7, blind**. The boss is 12.36 thick (seat Z 43.0, face Z 30.64). M4 × 20 would bottom | Fork loose on the roll output, the joint that carries the whole arm | **Here**, done | - | **Settled on paper:** M4 × 18 (5.6 mm engaged). Pins: at most 7 mm in the motor. The three Ø3.8 pin holes are in the real fork front (0 / 120 / 240°) |
| 6 | **Roll limits must exist before the first enable** | SOFTWARE_HANDOFF.md; B_ROLL_STOPS.md (layer SF 0.55-0.66 at a 60 N·m stall) | The printed stops break at a stall if the controller's 17 N·m / 1 rad/s / -9…+108° limits are missing | Broken fork rear on day one | **Other (software):** confirm the limits are in the controller, and test them on `vcan` | Software thread | Open |
| 7 | **XT30(2+2) plug's real size** | PRINT_NOTES.md; plug_pocket README ("height assumed", fold read from photos) | The plug or its folded lead does not fit the channel (r 36-50, 16.5 wide, Y 353.9-361.1) | Fork front reprint, 155 g | **Joey:** measure a real plug with its lead; try it in a printed slot | 10 min | Open |
| 8 | **Across-layer shear allowable, 13 MPa** | A_HUB_LUGS.md ("assumed"); B_ROLL_STOPS.md uses 22.5 MPa for layers | The hub's 1.60 / 1.31 rests on it. If the real figure is lower, the lugs' inner roots fail in yaw | Hub lug cracks at peak yaw torque | **Joey / arm thread:** a printed shear coupon, or the arm thread's data | A coupon and a pull test | Open |
| 9 | **The committed hub export is two revisions old** | cad/exports/shoulder (rev C+, 2026-11-11) | Someone prints it: no locating holes, short lugs | Wasted print; wrong joint | **Here:** replaced when D3c5 is released | - | Flagged in PRINT_NOTES.md |
| 10 | **Nothing has been sliced** | CONCEPT.md section 10; CAD_NOTES.md "Still open" | Supports that can't be removed; the RS02 seat is a supported face; drum skin 0.97 mm at one spot, cuff 1.48 | Reprints | **Run:** slice each part with the Bambu CLI and read supports, thin walls, time | About 1 h | Open; next on my list |
| 11 | **Re-torque after 24 h against access** | PRINT_NOTES.md; CAD_NOTES.md "Driver reach" | Assembled, only the 104° RS02 screw can be reached; the hub screws are behind the arm halves. The re-torque needs a strip-down | The low-preload joints never get their re-torque | **Here:** list which screws are reachable assembled. Then a procedure | 1 h | Open |
| 12 | **Bundles against the RS02 in the fork** | CAD_NOTES.md "Side centre r 47" lays the bundles first; "RS02 re-clocked" fits the RS02 first | The two orders conflict. With the RS02 in, the 16 × 6 bundle may not go into the back cavity | Assembly stalls; forced cable | **Here:** section the back cavity with the RS02 in place | 1 h | Open |
| 13 | **Plugs through the channels** | CONCEPT.md assembly steps | An XT30(2+2)-F body is 16 × 6.5 × 15. It does not pass a 16 × 6 channel or the 7 × 6 tap | Wires must be threaded before they are terminated | **Here / electrical plan:** write the order (thread, then solder) into the assembly notes | - | Open |
| 14 | **Pitch loop over 270°** | CONCEPT.md, TORSO_INTERFACE.md ("flex life not checked") | Length change of about 300 mm at r 65; bend radius of a 4 mm band in a 16 mm channel | Trunk fatigue at the first joint | **Here:** length and bend radius on paper. **Joey:** a loop rig if the paper says tight | 1 h; a second rig | Open |
| 15 | **Roll crossing as twist in the Ø25 stub bore** | CONCEPT.md ("125° as twist", bend radii not checked) | Power above the axis, signal below: off-axis, so twist plus a swing | Chafe in the stub bore | **Here:** free length and twist per mm | 1 h | Open |
| 16 | **RS03 connector bays** | CONCEPT.md, MEASUREMENTS.md ("vendor bays are empty") | The top-bay window and branch are sized from the bay, not a plug | Drum reprint, 227 g | **Joey:** photo and size of the plugs seated in an RS03 | 10 min | Open |
| 17 | **RS03 output bearing rating** | C_LOAD_SHARE.md ("not published"; up to 28.6 N·m of tilt) | The roll output bearing is overloaded | Motor damage over time | **Other / vendor:** ask RobStride; the 6808 already shares the load | An email | Open |
| 18 | **Preload, creep and friction values** | A_HUB_LUGS.md (0.35 kN per screw, half after creep, μ 0.25, hook scale ±15%) | The hub-top SF falls from 1.64 to 1.41 if over-tightened; slip if under | Loose or cracked hub top | **Joey:** bench: torque, wait 24 h, re-check | Part of the first bench session | Open |
| 19 | **Fork front to RS02 body, 5 × M3** | PRINT_NOTES.md (no torque, no slip check, no length) | Carries the 17 N·m yaw reaction. The RS02 drawing gives 9 × M3, depth 8 | Yaw backlash at the motor seat | **Here:** slip check and screw length | 1 h | Open |
| 20 | **Stop impact estimates** | B_ROLL_STOPS.md (inertia about 0.06 kg·m², stiffness "a rough estimate") | The 1 rad/s cap rests on them | Stop damage on a fast arrival | **Joey:** first stop contacts at low speed, inspect | Bench | Open |
| 21 | **Clearances are nominal CAD** | CAD_NOTES.md (2.0 mm gaps, ±0.4 sampling; deflection about 0.45) | Print tolerance and deflection eat a 2.0 mm running gap | Rub marks; not a failure | **Joey:** measure the first prints | - | Open |
| 22 | **Press fits** | CAD_NOTES.md (plugs Ø6.9 in Ø7; port cap hooks 0.8; RS02 in its bore with 0.45-0.50) | Too tight or loose as printed | Small reprints | **Joey:** try on the first prints | - | Open |
| 23 | **Insert and joint screw lengths** | PRINT_NOTES.md (six ISO 7380 M4, recess "about 3.1", no lengths) | Wrong screws on the bench; a screw into the plug channel (1.5 mm from an insert bore) | Delay; a pierced channel | **Here:** a length for each screw from the CAD | 1 h | Open |
| 24 | **Loads never run** | CAD_NOTES.md "Not analysed"; C_LOAD_SHARE.md (the fork as two bodies fails to solve) | Pitch stall (60 N·m) into the drum's pitch pad; the flange ring carrying the trunk mouth | Unknown margins on the drum | **Run:** drum pitch-pad case; fork as bonded bodies | 2-3 h of solves | Open |
| 25 | **Wire gauge and crossing in the trunk plan** | Trunk plan (16 AWG to the elbow, yaw as a twist); upper-arm README (18 AWG) | The bundle tested is not the bundle built | Rig result doesn't transfer | **Other (electrical):** one definition | - | Flagged to the coordinator |
| 26 | **6808 seat changes built?** | D_6808_FITS.md says "not rebuilt yet"; CAD_NOTES.md mass table implies built | If not built, the lip preloads the RS03 bearing | Bearing drag | **Here:** read the Ø52.2 bore and lip off the built parts | 15 min | Git says built (f93957c, 2026-11-11). To confirm on the STL |
| 27 | **Pitch output hole clock** | MEASUREMENTS.md (pattern 7.83 mm off at the exported clock; left side unconfirmed) | The drum doesn't bolt on | Drum reprint | **Here:** check the drum's pad holes against the placed pitch RS03 | 30 min | Open |
| 28 | **Cover fixing and feed** | CAD_NOTES.md "Still open" (M5 pads are placeholders; T-nuts not checked; feed waits for the shell) | Cover can't be mounted | Cover reprint, 102 g | **Other (torso / shell)** | - | Open; the cover waits |
| 29 | **Shell and spine pads** | CAD_NOTES.md (arm 0.01 mm from the lower spine pad at -11) | Contact with the shell | Shell change | **Other (shell)** | - | On the shell change list |
| 30 | **Yaw zero offset** | SOFTWARE_HANDOFF.md (+40°, "the hardware has no other reference") | A wrong zero points the arm 40° or 60° off | Wrong pose; see 2 | **Other (software):** a zeroing step with a printed reference mark | - | Open |
| 31 | **FEA simplifications** | A_HUB_LUGS.md (lug bolt preload not modelled; peaks under 1.0 read as fixture artefacts) | A real peak is dismissed | Local cracking | **Run:** one case with bolt preload, if item 8 comes back low | 1 solve | Open |
| 32 | **Mass against the target** | CONCEPT.md (520 g target); CAD_NOTES.md (638.5 g, before hub D3c) | Heavier than planned. Static arm moments are 1-2.3 N·m, far under the RS03's 20 | Low | **Here:** note only | - | Shoulder is about 642 g with hub D3c |
| 33 | **Right shoulder** | CAD_NOTES.md ("a mirror, later") | Handed parts mirrored wrongly (motors, screws, socket, offset sign, window) | Low for now | **Here:** plan first | - | Plan in work |

## Settled so far

### 4. Hub screws (2026-11-13)
- **RS02 output, from the manual's outline drawing** (RS02 user manual 260713, section 1.1): 6 × M4, depth **7 min**, on Ø24;
  three Ø4 (+0.1 / 0) plain holes; 9 × M3, depth 8, on Ø73. "The screw depth should not exceed the depth of the casing thread."
- **Hub, measured on the built part:** the head bears on the boss tube's end at Y 298.1 (ring r 2.15-4.4, 46.3 mm²). The
  output face is Y 319.86. Boss 21.76.
- **M4 × 30:** 8.24 mm into the motor. That is 1.24 mm more than the depth the drawing guarantees.
- **Fix:** 1.6-2.0 mm under the head (two M4 washers, 7 mm outside diameter or less to sit on the Ø8.8 tube end), or
  M4 × 28. Engagement 6.2-6.6 mm.
- **The plain shank still locates:** the reamed length in the hub is 7.3 mm (Y 305.3-312.6), not the 10 mm the note assumed,
  so bearing at 17 N·m is 708 N / (4 × 7.3) = 24 MPa, not 17.7. Bulk SF 1.9.
- **For Joey:** probe one RS02 output hole. If it is 9 mm or deeper, M4 × 30 is fine without washers.

### 5. Fork front on the RS03 output (2026-11-13)
- **RS03 output, from the manual's outline drawing** (RS03 user manual 261013, section 1.1): 6 × M4, depth **6, blind**, on
  Ø30.36; three Ø4 (+0.1 / 0), depth **7, blind**; housing 8 × M4, depth 8, on Ø98.
- **Fork front, measured on the built part:** screw seats at Z 43.0, output face Z 30.64, boss 12.36.
- **Screws:** M4 × 18 engages 5.64 mm. M4 × 16 is short (3.6 mm); M4 × 20 bottoms.
- **Pins:** Ø4, at most 7 mm into the motor. The fork front has its three Ø3.8 (ream to 4.00) holes at 0 / 120 / 240° on
  r 15.2.

### 3. Heat (figures only, 2026-11-13)
- Rated torque is stated with a heat sink: RS02 6 N·m on 260 × 280 mm, RS03 20 N·m on 215 × 220 mm.
- Ambient range -20 to 50 °C. Winding limit 145 °C. Over-temperature fault at a thermistor reading of 135 °C (RS02) and
  145 °C (RS03).
- So the drive protects itself, not the plastic round it. The limit has to come from the controller.
