+++
link = "forearm"
region = "forearm"
sides = ["left", "right"]
status = "draft"
agreed = ""
interfaces = ["RS02 elbow output", "RS00 housing", "RS00 output", "6808-2RS", "Ruthex M3 inserts", "wrist flange", "elbow back loop", "clock spring"]

# Governing case, Joey 2026-11-07 19:55-19:59Z: arm straight, 5 kg at the outer end, from rest, slow sweep through the
# full shoulder pitch range. Absolute worst-case sustained load; must not fail.
[[load_case]]
id = "P0"
what = "Hanging: 5 kg at the hand point (49 N + 6 N self-weight, 90 mm past the wrist face), tension"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "P45"
what = "Sweep 45 deg"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "P90"
what = "Arm horizontal, bending"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "P135"
what = "Sweep 135 deg"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "P180"
what = "Overhead, compression"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "LATERAL"
what = "Gravity across the elbow plane, 5 kg at the hand point"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "STOP"
what = "P90 back-driven onto the 0 deg elbow stop"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "WORKING"
what = "Working case: 500 g hand placeholder plus test weights, arm horizontal"
bulk_sf = 2.0
layer_sf = 1.5

[[load_case]]
id = "RS00-PEAK"
what = "RS00 14 N.m peak torque through the RS00 ring screws and the coupling dogs"
bulk_sf = 1.5
layer_sf = 1.25

[print]
material = "PETG"
colour = "white"
plate = "Cool Plate Super Tack"
visible_support_mm2 = 0
settings = { layer_height = "0.2", support_type = "tree(auto)" }

# [[part]] tables are added when the clamshell split of the fork is set (draft 4 recommends it); the turned parts
# (sleeve, RS00 ring, tube, coupling, wrist cap, wrist flange) are added with their print directions at the same time.
+++

# Forearm: requirements

**Status: draft, for Joey to agree.** Seeded 2026-11-09 from decisions already made on the left forearm; every line says
where it came from. How this file is used: [conventions/part-lifecycle.md](../../conventions/part-lifecycle.md).

The link from the elbow RS02 output down to the wrist flange, including the RS00 forearm-yaw stage, both arms.

## Load cases

The `[[load_case]]` table above is the list the gate checks. In words:

- **Governing case** (Joey 2026-11-07 19:55–19:59Z): arm straight, 5 kg at the outer end, from rest, slow sweep through the
  full shoulder pitch range. Absolute worst-case **sustained** load; must not fail. About 9.6 N·m at the elbow over 195 mm.
  Strength wins over interior space.
- **Pass marks:** 1.5 bulk / 1.25 layer for the worst case and the stop; 2.0 / 1.5 for the working case (500 g hand plus
  test weights) (left-arm thread, 11-07).
- **Material model:** PETG, E 1.9 GPa, yield 45 MPa, layer strength 0.5 × yield (left-arm thread, 11-07).
- **Elbow stop contact:** pressure under 55 / 1.5 = 36.7 MPa at the RS02 peak and at 34 N·m shoulder-driven (draft 4).
- **Not a structural spec for the motors:** bent-elbow 5 kg (about 14 N·m) is past the RS02's continuous rating; behaviours
  prefer straight-arm and two-arm carries (Joey 19:57Z). The structure must still survive it.
- **Not a load case yet:** tip-over (see the upper arm spec).

## Motion

- Elbow: 0–124°, folds forward. 0° extension stop is printed and carries gravity-driven extension.
- Forearm yaw (RS00): hard stop ±170° in draft 4, clock spring sized for ±190°. **TBD:** the repo disagrees on the yaw limit
  (left URDF ±1.05 rad, kinematics ±1.6 rad, right arm ±3.24 hard / ±1.55 soft, control.yaml [−0.367, 3.217]); one number to
  pick with the controls side, then written here.

## Mass and CoM

- Draft 4 whole forearm with the RS00: 779 g, CoM 102.3 mm below the elbow axis (100% infill CAD estimate). Budget **TBD**,
  Joey to set.
- Hand placeholder (Joey 2026-11-06 10:31Z): 500 g = 300 g pack inside the forearm, CoM about 140 mm from the elbow axis,
  plus 200 g hand, CoM about 90 mm past the wrist flange, about 190 mm long. Use it in every load case.
- Length 195 mm, a skeleton variable. Don't lengthen it.

## Interfaces

- **Top:** elbow RS02 output face; fork cheeks. RS02 shoulder-to-output length open (31.5–32.0 drawing vs 33.9 model); if it
  measures about 33.9, the outboard cheek moves out about 2 mm.
- **RS00 support:** option A (Joey 2026-11-07 23:17Z): static sleeve on two 6808-2RS about 57 mm apart, Ø40 inner tube turns,
  printed torque-only dog coupling on the RS00 output (6 × M3 on Ø27). The RS00 output bearing carries torque only.
- **RS00 housing:** 6 × M3 on Ø50, through a separate ring bolted on the bench (driver access).
- **Wrist flange (hand interface):** 6 Ruthex M3 inserts on Ø50, Ø35 pilot.
- **Bearing seat:** Ø52.2 bore for the Ø52 6808 race; print a seat ring coupon first (faces needed only).

## Harness

- Elbow back loop, as on the upper arm (Joey 2026-11-08), with a forearm saddle on the cheek rim at 140°.
- Cable from the elbow loop to the RS00 ring slot, captured in the clamshell seam.
- Yaw: reverse-wound FFC clock spring, about 400 mm, in the r 21.5–26.1 gap; anchors and part number open.
- **Reserve** one spare fused trunk drop and one CAN drop at the forearm end for the hand (hand research, 11-06).

## Print rules

As in [upper_arm_requirements.md](../upper-arm/upper_arm_requirements.md#print-rules), plus:

- Fork as a **clamshell** split on the forearm axis plane, halves cut-face down: 0 mm² of support on outer skin, against
  5800–7300 mm² for any one-piece orientation (draft 4). The cheek discs (RS02 mating face, bearing face) print as separate
  flat parts, so precision faces don't print over support.
- Turned parts print axis-up.

## Room to leave

- **Hand actuator bay** (Joey 2026-11-07): the hand's actuators will live in the forearm. Not a constraint while iterating,
  but don't block it. The Ø34 tube bore (option A) costs bay space; the sleeve stays swappable for that reason.
- **Right arm:** mirror, re-checking actuator-specific features.

## Open

- Clamshell split and its seam FEA (yaw torque 14 N·m crosses a new bolted seam).
- Forearm yaw limit; mass budget; RS02 length measurement; clock spring parts.
- `[[part]]` tables and the evidence file, once the split is set.
