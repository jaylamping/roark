+++
link = "upper_arm"
region = "upper-arm"
sides = ["left", "right"]
status = "draft"
agreed = ""
evidence = "reviews/upper-arm/20261108_clamshell-draft3/evidence.json"
interfaces = ["RS02 upper-arm yaw output", "RS02 elbow housing", "spring carrier", "6808-2RS", "Ruthex M3 inserts", "elbow back loop"]

# Governing case, Joey 2026-11-07 19:59Z: arm straight, 5 kg at the hand (about 0.5 m from the shoulder pitch axis),
# from rest, slow sweep through the full shoulder pitch range. Absolute worst-case sustained load; must not fail.
# Bulk 1.5 / layer 1.25 everywhere, 2.0 bulk at 90 deg for creep while the motor holds.
[[load_case]]
id = "G0"
what = "Sweep 0 deg: hanging, 5 kg at the hand plus self-weight"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "G45"
what = "Sweep 45 deg"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "G90"
what = "Sweep 90 deg: arm horizontal, motor holding (creep)"
bulk_sf = 2.0
layer_sf = 1.25

[[load_case]]
id = "G135"
what = "Sweep 135 deg"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "G180"
what = "Sweep 180 deg: overhead, compression"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "LATERAL+X"
what = "Gravity along +X, 5 kg at the hand, moment about Z"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "LATERAL-X"
what = "Gravity along -X, 5 kg at the hand, moment about Z"
bulk_sf = 1.5
layer_sf = 1.25

[[load_case]]
id = "LC2"
what = "17 N.m twist about Y, the link's long axis (p3_fea.py)"
bulk_sf = 1.5
layer_sf = 1.25

[print]
material = "PETG"
colour = "white"
plate = "Cool Plate Super Tack"
visible_support_mm2 = 0
settings = { layer_height = "0.2", support_type = "tree(auto)" }

[[part]]
name = "upper_arm_shell_front_left"
export = "exports/upper-arm/upper_arm_shell_front_left.stl"
up = [0, 0, 1]
hidden_by = ["exports/upper-arm/upper_arm_shell_back_left.stl", "exports/upper-arm/upper_arm_elbow_ring_left.stl", "exports/upper-arm/upper_arm_hub_left.stl", "exports/upper-arm/upper_arm_spring_carrier_left.stl"]
settings = { sparse_infill_density = "50%", wall_loops = "4" }
visible_support_mm2 = 84.5
visible_support_reason = "84.0 mm2 of insert-hole ceilings and fuse-pocket faces inside the closed shell, reachable by a ray only through the seam (support check on the rebuilt halves, 2026-11-09)"

[[part]]
name = "upper_arm_shell_back_left"
export = "exports/upper-arm/upper_arm_shell_back_left.stl"
up = [0, 0, -1]
hidden_by = ["exports/upper-arm/upper_arm_shell_front_left.stl", "exports/upper-arm/upper_arm_elbow_ring_left.stl", "exports/upper-arm/upper_arm_hub_left.stl", "exports/upper-arm/upper_arm_spring_carrier_left.stl"]
settings = { sparse_infill_density = "50%", wall_loops = "4" }
visible_support_mm2 = 0.5
visible_support_reason = "0.4 mm2 at the seam edge, Y 254.8 (support check on the rebuilt halves, 2026-11-09)"

[[part]]
name = "upper_arm_elbow_ring_left"
export = "exports/upper-arm/upper_arm_elbow_ring_left.stl"
up = [1, 0, 0]
hidden_by = ["exports/upper-arm/upper_arm_shell_front_left.stl", "exports/upper-arm/upper_arm_shell_back_left.stl", "exports/upper-arm/upper_arm_hub_left.stl", "exports/upper-arm/upper_arm_spring_carrier_left.stl"]
settings = { sparse_infill_density = "100%", wall_loops = "6" }

[[part]]
name = "upper_arm_hub_left"
export = "exports/upper-arm/upper_arm_hub_left.stl"
up = [0, -1, 0]
hidden_by = ["exports/upper-arm/upper_arm_shell_front_left.stl", "exports/upper-arm/upper_arm_shell_back_left.stl", "exports/upper-arm/upper_arm_elbow_ring_left.stl", "exports/upper-arm/upper_arm_spring_carrier_left.stl"]
settings = { sparse_infill_density = "50%" }
visible_support_mm2 = 183
visible_support_reason = "182.5 mm2 of lug faces under the spigot, inside the closed arm (support check, 2026-11-09)"

[[part]]
name = "upper_arm_loop_clip_left"
export = "exports/upper-arm/upper_arm_loop_clip_left.stl"
up = [0, -0.70710678, -0.70710678]
settings = { sparse_infill_density = "100%", enable_support = "0" }
+++

# Upper arm: requirements

**Status: draft, for Joey to agree.** Seeded 2026-11-09 from decisions already made on the left upper arm; every line says
where it came from. Nothing here is new design. How this file is used: [conventions/part-lifecycle.md](../../conventions/part-lifecycle.md).

The link from the upper-arm yaw RS02 output down to the elbow RS02, both arms. The design of record is in
[README.md](README.md) (draft 3 clamshell).

## Load cases

The `[[load_case]]` table above is the list the gate checks. In words:

- **Governing case** (Joey 2026-11-07 19:59Z): arm straight, 5 kg at the hand, from rest, slow sweep through the full
  shoulder pitch range. It is the absolute worst-case **sustained** load and must not fail (19:56Z). At the elbow point
  this is 62 N along gravity plus 17.2 N·m, about 24 N·m at the hub face (draft 3 README).
- **Pass marks:** 1.5 bulk, 1.25 layer; 2.0 bulk at 90° for creep while the shoulder holds (design decision, 11-07).
- **Lateral:** the same load with gravity along ±X (design decision, 11-08).
- **Twist (LC2):** 17 N·m about Y, the link's long axis (left-arm FEA, p3_fea.py).
- **How SF is taken:** per part with each part's own layer normal; points within 4.5 mm of the load and fixture patches are
  excluded. A result counts only when it held on a finer mesh.
- **Not a load case yet:** ground-level tip-over. The robot is stationary and supported until legs exist (Joey 2026-11-07
  07:36Z); fall design waits, but nothing here may make adding it later a full redesign. When it comes, the printed links are
  the designed weak point so the actuators and the frame survive (Joey 2026-11-06).

## Motion

- Upper-arm yaw (RS02 at the hub): range **TBD**, to agree with the controls side (the arm thread owns the number).
- Elbow (RS02 at the ring): 0–124°, folds forward (Joey, left-arm thread). Printed stop carries 17 N·m.

## Mass and CoM

- One-piece upper arm db71b23b weighed **202 g** and Joey called it too heavy (2026-11-08). Draft 3 expects about 180 g
  plus the 7.7 g clip (sliced 204.7 g; slicer read 13% high on db71b23b). Budget: **TBD**, Joey to set.
- Length 215 mm shoulder to elbow, a skeleton variable. Don't lengthen it (Joey 2026-11-06: the built right arm already
  feels long).

## Interfaces

- **Top:** upper-arm yaw RS02 output face, clamped by the hub. Vendor model and drawing disagree on the RS02 shoulder-to-output
  length (31.5–32.0 vs 33.9 mm); Joey to caliper a real RS02 (open since 11-07).
- **Bottom:** elbow RS02 housing in the ring; spring carrier; 6808-2RS elbow bearing.
- **Inserts:** Ruthex M3 heat-sets; M3 seam screws from the back half only.
- **Check against the vendor RS02 model** including its housing tab (print log lesson `rs02-housing-tab`). For the gate's
  interference check, export the two RS02 models in arm coordinates to `exports/upper-arm/` and list them under `mates`.

## Harness

- One trunk segment per link, inside the closed section (left-arm brief, 11-06).
- Trunk entry Ø10 in the back wall below the hub; RS00 branch Ø6.8 out to the loop clip (draft 3).
- Elbow: round cable in braided loom as a free **back loop** outside the bend, about 190 mm free, bend radius at least
  27.9 mm; no printed guard (Joey 2026-11-08 05:24Z).

## Print rules

These apply to every printed structural part of the robot; links repeat only what differs.

- **Orientation:** outer faces print clean. No support on any visible outer face; print vertical where possible
  (Joey 2026-11-08 02:13Z).
- **Enclosed hollow parts** are fastened clamshells, never trap doors (Joey 2026-11-08 02:13Z, 02:27Z).
- **Material:** structural parts PETG; internal non-structural parts regular PLA (Joey 2026-11-07 10:49Z). Visible arm parts
  white PETG (11-07).
- **Plate:** Cool Plate Super Tack, no glue. **Supports:** tree by default; normal only where a face needs it (Joey 11-07).
- **Infill:** 50% with 100% modifiers on clamped blocks and seats, rather than solid, is Joey's preference (11-07). The
  one-piece used 6 walls; the draft 3 halves use 4 walls outside the 100% / 6-wall zones (ua_slice.py), for Joey to confirm.
- **3MF:** every overridden setting flagged so Bambu Studio keeps it (11-07).
- **Bearings or bushings** on all moving surfaces; tap threads; no threadlocker during testing (Joey 11-07).

## Room to leave

- **Right arm:** mirror of the left, except actuator-specific features (connector reliefs, bolt-circle clocking, cable exits),
  which are checked again (Joey 2026-11-06).
- **Fall retention:** see Load cases.

## Open

- Upper-arm yaw range and the mass budget (above).
- Lateral case does not pass in the draft 3 one-body model (1.17 bulk at the ring/skirt corner); contact model and corner fix
  next (draft 3 README).
- RS02 meshes in arm coordinates for `mates`; the evidence file for draft 3.
