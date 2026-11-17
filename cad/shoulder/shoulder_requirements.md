+++
link = "shoulder"
region = "shoulder"
sides = ["left", "right"]
status = "draft"
agreed = ""
evidence = "reviews/shoulder/20261115_hub-rev-e1/evidence.json"
interfaces = ["RS03 pitch output", "RS03 roll output", "RS03 roll housing", "RS02 yaw body", "RS02 yaw output", "6808-2RS",
              "Ruthex M4 inserts", "Ruthex M3 inserts", "upper arm spigot and lugs"]

# Pass marks: the shoulder record uses 1.5 on von Mises and 1.5 on layer tension (FORK_FRONT_FE.md), and 1.2 on the
# elbow stop. OPEN for Joey: the upper arm's spec uses 1.5 / 1.25 with 2.0 at 90 deg for creep.
# Shear across the layers (13 MPa) is an assumed allowable and is reported beside these; the gate has no key for it.

[[load_case]]
id = "HUB_TOP"
what = "Hub bolted to the RS02 output (six M4, snug, contact on the seat): arm horizontal with 5 kg at the hand, 372 N down, 22.9 N.m about X, 17 N.m yaw (arm thread's case A with yaw)"
bulk_sf = 1.5
layer_sf = 1.5
parts = ["shoulder_hub_left"]

[[load_case]]
id = "HUB_LUG"
what = "Hub lugs: arm horizontal with 5 kg (G90) plus 17 N.m yaw, either sign, at the arm's face totals"
bulk_sf = 1.5
layer_sf = 1.5
parts = ["shoulder_hub_left"]

[[load_case]]
id = "HUB_ESTOP"
what = "Elbow stop reaction into the hub: 515 N on the stop, 62 N down, 7.0 / 8.6 / 14.7 N.m about X / Y / Z"
bulk_sf = 1.2
layer_sf = 1.2
parts = ["shoulder_hub_left"]

[[load_case]]
id = "FORK_MX"
what = "Fork, design load through the RS02 seat about the hub point: 310 N down, 23 N.m about X (forward), 17 N.m about Y, yaw either sign"
bulk_sf = 1.5
layer_sf = 1.5
parts = ["shoulder_fork_front_left", "shoulder_fork_rear_left"]

[[load_case]]
id = "FORK_MZ"
what = "Fork, design load sideways: 310 N down, 23 N.m about Z, 17 N.m about Y"
bulk_sf = 1.5
layer_sf = 1.5
parts = ["shoulder_fork_front_left", "shoulder_fork_rear_left"]

[[load_case]]
id = "ROLL_STOP17"
what = "Roll hard stop at 17 N.m (the controller's limit near the stops), either stop"
bulk_sf = 1.5
layer_sf = 1.5
parts = ["shoulder_fork_front_left", "shoulder_fork_rear_left", "shoulder_roll_cap_left"]

[print]
material = "PETG"
colour = "black"
plate = "Supertack Plate"
visible_support_mm2 = 0
settings = { layer_height = "0.2", support_type = "tree(auto)", enable_support = "1" }
preset = ["layer_height"]

[[part]]
name = "shoulder_hub_left"
export = "exports/shoulder/shoulder_hub_left.STL"
up = [0, -1, 0]
settings = { sparse_infill_density = "100%", wall_loops = "6", brim_type = "no_brim" }
# The motor-side face is hidden by the RS02 and the fork's skirt, so its support does not count as visible: OPEN,
# the gate needs a `hidden_by` mesh (the RS02 and the fork front in assembly coordinates) or an allowance with a reason.

# [[part]] tables for the drum, fork front, fork rear, rear cap, flange ring and cover ring are added when each gets a
# print file. None has print settings on record yet.
+++

# Shoulder: requirements

**Status: draft, for Joey to agree.** Seeded 2026-11-15 from decisions already on record for the left shoulder; every line
says where it came from. Nothing here is new design. **OPEN** marks a value that is an assumption or that Joey has not been
asked; the list is repeated at the end. How this file is used: [conventions/part-lifecycle.md](../../conventions/part-lifecycle.md).

The link from the torso's pitch RS03 to the upper arm's hub: the roll drum on the pitch output, the roll RS03 in the drum,
the fork (front and rear) on the roll output, the yaw RS02 in the fork, and the hub on the RS02 output. Records are in
`hardware/shoulder/study-20261111/`: `cad-pass1/CAD_NOTES.md` (CN), `cad-pass1/PRINT_NOTES.md` (PN),
`checks/OPEN_ASSUMPTIONS.md` (OA), `checks/FORK_FRONT_FE.md` (FFE), `checks/A_HUB_LUGS.md` (AHL), `checks/B_ROLL_STOPS.md`
(BRS), `checks/CABLE_TRAVEL.md` (CT), `checks/WIRING_CONSEQUENCES.md` (WC), `checks/D_6808_FITS.md` (D68) and
`hardware/shoulder/SOFTWARE_HANDOFF.md` (SWH).

## Load cases

The `[[load_case]]` table above is the list the gate checks. In words:

- **Where the load comes from:** the arm's governing case, arm straight and horizontal with 5 kg at the hand (Joey
  2026-11-07, [upper arm spec](../upper-arm/upper_arm_requirements.md)), plus the yaw RS02's own peak of 17 N·m (RobStride
  manual; not a software cap, FFE).
- **Two statements of it are on record and are not reconciled. OPEN:** the fork runs use 310 N, 23 N·m and 17 N·m through
  the RS02 seat (FFE); the hub-top runs use the arm thread's 372 N, 22.9 N·m and 17 N·m (AHL). The table keeps each with
  the part it was run on.
- **Hub lugs:** about 245 N per lug at 17 N·m, alone and with G90, both yaw signs; read at the arm's face totals (AHL,
  2026-11-13 and 11-14). **Elbow stop:** 515 N on the stop (AHL), pass mark 1.2.
- **Roll stop:** the RS03 is rated 20 N·m and peaks at 60 N·m. Joey 2026-11-13: software limits near the stops; the parts
  stay as built and the printed stop is not sized for a 60 N·m stall (BRS, SWH). The case is the stop at 17 N·m.
  **OPEN:** whether a 60 N·m stall is ever a design case for the fork (at stall the record reads 0.47).
- **Pass marks:** 1.5 on von Mises and on layer tension; 1.2 on the elbow stop (FFE, AHL). **OPEN:** the upper arm uses
  1.5 bulk, 1.25 layer and 2.0 at 90° for creep; the shoulder has no creep mark.
- **Allowables:** PETG yield 45 MPa, layer tension 22.5 MPa (AHL, BRS). Shear across the layers 13 MPa is **assumed**; the
  coupon has not been made (OA item 8). **OPEN.**
- **How SF is read:** the worst 0.5 mm ball among each region's highest nodes, the part's own nodes only, with the 1 mm
  ball beside it (AHL, FFE, 2026-11-15). Bolted seats are run as bolted joints with contact and preload.
- **Not covered by any run. OPEN:** the drum and the flange ring (never analysed, OA item 24); the rear cap beyond the
  stop slot. The fork's RS02 seat, 6808 seat and joint screw seats are below 1.5 in the present parts and are being
  revised (OA item 49); the fork is not printed for load before that.
- **Not a load case:** falls and tip-over, as for the arm (Joey 2026-11-07).

## Motion

- **Roll:** hard stops at −11° (inward) and +110° (outward) (CN; −11 chosen by Joey, BRS). Software limits −9° to +108°,
  and within 5° of a stop at most 17 N·m and 1 rad/s (SWH; Joey 2026-11-13).
- **Yaw:** ±90° is the travel the cable work is sized for (CT). No hard stop. **OPEN:** SWH carries soft limits of ±85°
  as an assumption, and Joey has not fixed the yaw travel or said whether a hard stop is wanted (OA item 2).
- **Pitch:** no stop. **OPEN:** no range agreed; the checks swept −90° to +180° and the trunk plan says −50° to +180° (CN, CT).
- **Running gap:** 2.0 mm or more between moving pairs over the travel (CN).

## Mass and CoM

- As modelled, solid PETG at 1.27 g/cm³ (CN): drum 227.1 g, fork front 152.3, rear cap 85.4, fork rear 68.2, flange ring
  38.1, port cap 1.4, hub rev E1 117.3 (rev D3c7 was 80.2). Total about **690 g** (689.8; hub rev E1, the fork revision of 2026-11-15 and the fork rear of 2026-11-17). Cover ring 13.1 g
  (optional), pitch loop cover 102.3 g (torso side).
- Sliced: hub rev E1 115.8 g. Nothing has been weighed.
- **OPEN: budget.** None from Joey. The concept note's target was 520 g and the working number about 600 g (CN, OA item 32).
  No CoM figure exists.

## Interfaces

- **Pitch RS03 output** to the drum: 6 × M4 × 18 with one washer (or M4 × 16). **Roll RS03 housing** to the drum:
  8 × M4 × 10 on Ø98. **Roll RS03 output** to the fork front: 6 × M4 × 18 and 3 × Ø4 pins, at most 7 mm into the motor (PN).
- **Yaw RS02 body** to the fork front: 5 × M3 × 14, each with one standard washer, on PCD 73 at −96, −56, −16, 104 and
  144°, snug only (PN; seats revised 2026-11-15, FFE). RS02 clocked +40°, one socket in use at 228° (Joey 2026-11-13, CN).
- **Yaw RS02 output** to the hub: 6 × M4 × 30, each with one standard flat washer, 5.2 mm into the motor, whose holes
  bottom out at 6.5 to 7 mm (Joey, decided and measured 2026-11-15); two of the six holes reamed to 4.00 (PN).
- **Fork joint:** 6 × ISO 7380 M4 into M4 inserts. **Flange ring:** 5 × M3 × 5 into M3 inserts. **Rear cap:** 3 × M2.5 × 14
  thread-forming (PN).
- **Bearing:** 6808-2RS, 40 × 52 × 7; stub Ø40.0; housing Ø52.1 (the adopted fork rear since 2026-11-17), from the printed seat test rings (P2S, PETG; a hand
  push with light pressure, Joey 2026-11-15). The race must not rock in the seat: the fork's strength depends on it (D68).
- **Hub to arm:** spigot Ø71.6, two lugs with Ø3.8 holes; the hub's centre sits 3 mm taller from rev E1, so the arm hangs
  3 mm lower: motor face to the arm's seat 20.86 mm (Joey 2026-11-15, AHL).
- **Screws:** snug by hand for the first iterations, no torque procedure, no threadlocker in testing (Joey 2026-11-15, PN).
- **Shell:** opening r 80 (Joey, CN). His later question about a 150 mm opening is a study only. **OPEN.**
- **Not measured. OPEN:** a real RS02's flange face, the RS03 connector bays and screw ear, the
  XT30(2+2) plug (OA items 4, 7, 16, 45).

## Harness

- **Power:** 16 AWG to both shoulder RS03s and through the pitch and roll crossings; 18 AWG from the yaw RS02 on (Joey
  2026-11-15, WC). **Signal:** two twisted pairs of 28 AWG, a third pair reserved (Joey 2026-11-11, CT).
- **Bend rules** (trunk plan): static 5 × OD, flexing 10 × OD (CT).
- **Channels:** trunk 16 × 6 mm in the drum and the fork rear; yaw dish under the RS02 with an 8.5 mm gap from rev E1;
  hub tunnel 4.5 × 11 mm (CN, CT, AHL).
- **Sleeve** on fixed runs; bare separate wires through the three crossings, tied at both ends; no plug or joint inside
  any channel (WC, OA).
- **OPEN:** none of the three crossings is proven; the cable rigs have not been run (OA items 14, 15, 37). Fuse places
  are not settled (OA item 44).

## Print rules

The rules in the [upper arm spec](../upper-arm/upper_arm_requirements.md) apply. For the shoulder:

- **Material:** PETG throughout (PN).
- **Colour** (Joey 2026-11-15, PN): black for the structure under the shell, the hub included; white for the shell; the
  fixed cable cover band black. **OPEN:** the fork, the drum and the flange ring are not decided.
- **Outline:** nothing may stand proud of the skin (Joey 2026-11-11, CN). The outside of the adopted parts changes only
  with Joey's yes; decided so far: the fork's skirt 3 mm longer with the taller hub (Joey 2026-11-15).
- **Hub print** (PN): P2S, 0.4 nozzle, Cool Plate SuperTack, no glue, 0.20 mm, 6 walls, 100% infill, no brim, tree supports
  with blockers at the groove and the lugs, the motor-side face down.
- **Orientation of the others** (PN): drum with the roll axis vertical, front lip down; fork front and fork rear upright;
  rear cap front face down; flange ring flat; cover ring flat, skirt up.
- **OPEN:** walls, infill and supports for every part but the hub; only a first-look slice exists (OA).

## Room to leave

- **Right shoulder:** a mirror, later; motors, screws, the socket, the offset sign and the cable tunnel are handed and are
  checked again (CN, OA item 33). No right-side part exists.
- **Hub:** a longer spigot and a second lug pair are prepared and switched off (CN).
- **Optional, Joey's call:** a bottom ring under the fork's sleeve (OA item 50); a fuse door in the cuff (WC).

## Open

For Joey:

1. Mass budget and CoM (none on record; about 690 g as modelled).
2. Pass marks: keep 1.5 / 1.5 with 1.2 on the elbow stop, or take the arm's 1.5 / 1.25 with 2.0 for creep at 90°.
3. Which statement of the arm's load governs: 310 N and 23 N·m, or 372 N and 22.9 N·m.
4. Whether a 60 N·m roll stall is a design case.
5. Yaw travel (±90° or ±85°) and whether a yaw hard stop is wanted. Pitch range.
6. Colour of the fork, the drum and the flange ring.
7. Walls and infill for the parts other than the hub (solid like the hub, or the arm's 50% with solid zones).
8. Shell opening: r 80 stays, or 150 mm.

For the design thread:

9. Shear across the layers: 13 MPa is assumed until the coupon is printed and pulled.
10. The drum, the flange ring and the rear cap have no strength record.
11. The fork's three bearing zones (OA item 49).
12. `hidden_by` and `mates` meshes for the gate (the RS02 and the neighbouring parts in assembly coordinates), and which
    `[print]` settings are the system preset's values.
13. The measurements never taken (above), the cable rigs, and motor heat into PETG (OA item 3).
