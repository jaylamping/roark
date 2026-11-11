# Check (a): hub lugs and hub under the arm-horizontal load (2026-11-11)

**Model:** `shoulder_hub_left.SLDPRT` (the frozen hub with the dished top), linear static FEA in SolidWorks Simulation.
`cad/scripts/shoulder/fea_shoulder.py`, cases `HUB_*` and `HUBS_*`.

**Material and method:** as the arm thread (`left-arm-organic` `p3_fea.py`): PETG E 1.9 GPa, ν 0.38, yield 45 MPa, layer
strength 22.5 MPa. The hub prints with the yaw axis vertical, so the layers are normal to Y and the layer stress is σy.
Mesh 1.5 mm, 0.5 mm at the seam-bolt holes, 214,634 nodes. Peaks are reported with nothing excluded.

**Fixed:** the six hub-screw holes (Ø4.3, PCD 24) and the step-ring face on the RS02 output.

**Load:** a remote load at the arm's hub point (X 170.49, Y 292, Z 5.99), **rigidly connected**:

- 310 N down (155 N per lug)
- 23 N·m bending
- 17 N·m yaw torque (the RS02 peak, as the arm thread rates it)

## Results

| Case | Where the load goes in | Bending axis | Bulk SF | Layer SF (σy) | Where |
|---|---|---|---|---|---|
| HUB_MX | Lugs only (seam-bolt holes) | X (arm forward) | **0.14** | **0.07** (337 MPa) | Lug edges at the root, Z 11 |
| HUB_MZ | Lugs only | Z (arm sideways) | 0.45 | 0.22 (103 MPa) | Lug A at the bolt hole, Z 11 |
| HUBS_MX | Lugs and spigot, rigid: the whole r 35.8 cylinder tied in every direction, axial included (a bonded or fixed surface, not radial-only) | X | 1.01 | **0.54** (42 MPa) | Dish floor / step ring, Y 315.8, r 23-30 |
| HUBS_MZ | Lugs and spigot | Z | 0.83 | **0.52** (43 MPa) | Dish floor / step ring, Y 315.8-316.5 |

![sigma_y](A_hub_sigma_y.png)

The two lines bound the real joint.

- **Through the lugs alone, they fail by a wide margin.**
  - They sit on the seam (yaw 0 / 180 deg).
  - A fore-aft moment (about X) bends them out of plane: SF 0.07 across the layers.
  - A sideways moment (about Z) is a couple between them: SF 0.22.
  - **A second lug pair at 90 deg to the seam** turns the fore-aft case into a couple as well. That is the case it helps.
  - With the two pairs together, each direction is carried as a couple at r 23. That is about 0.5 kN per lug at 23 N·m,
    still about twice what these lug sections take.
- **With the spigot clamped by the arm's hub seat, the lugs are nearly unloaded.** The weak point moves up into the hub:
  - it is the dished floor and step ring under the RS02 output (Y 312.8-319.9, r 19.5-38.6), which CONCEPT.md section 7
    already flagged as the new weakest section
  - layer SF about 0.5, bulk SF 0.8-1.0, at 23 N·m.

## What it means

- The hub-to-arm joint needs the spigot clamp to work, and the hub's dished top is too thin for 23 N·m bending across its
  layers.
- Options, for the arm thread and the next hub pass:
  1. Thicken the dish floor and step ring. The floor is 3 mm today (Y 312.8-315.8). The dish depth comes from the yaw cable
     loop (7.5 mm axial gap under the RS02), so it has to be re-balanced.
  2. A longer or conical spigot (the prepared `SPIGOT_EXT` feature) to spread the bending into the arm seat.
  3. A second lug pair at 90 deg (`LUG2`): it helps the lugs-only fore-aft case, but not the dish floor.
  4. Print the hub on its side, so the bending stress runs in the layer plane. That costs the RS02-face flatness.
- **Not modelled:**
  - contact and friction at the spigot seat (the real split between lugs and spigot)
  - bolt preload
  - the hub screws' own strength.


## Revision B (2026-11-11): thicker hub top, then the groove

### B1. Thicker top, spigot rigid as above

**Change:** the dish floor top is raised from Y 315.8 to Y 318.36, so the floor is 5.56 mm thick (was 3.0), with an R1.5
fillet into the step ring.

- **Yaw-loop gap:** under the RS02, 8.06 → 5.5 mm. The arm bundle (3.5 x 13 laid flat) keeps 2 mm over it.
- **Cuff:** follows the hub; its bottom moves to Y 320.36 to keep 2 mm over the higher rim.
- **Hub mass:** 60.2 → 69.9 g.

The arm thread's cases, with the spigot held rigidly as in case (2) above:

| Case | Load | Bulk SF | Layer SF (σy) away from the load faces | Layer SF, nothing excluded |
|---|---|---|---|---|
| A, arm horizontal, 5 kg payload | 372 N down, 22.9 N·m about X, 17 N·m yaw | 1.05 | 1.17 | 0.41 |
| B, elbow end stop 515 N | 62 N down, 7.0 / 8.6 / 14.7 N·m about X / Y / Z | 1.85 | 1.93 | 0.70 |

The thicker top lifts case A's layer SF from 0.54 to 1.17. That is still short of 1.5, even with the spigot rigidly held.

### B2. The groove (arm thread's section, roark 3d23f91 `r1c/ridge_groove_profile.png`)

**The groove in the hub**, as the arm thread drew it:

- opens Y 297.0-301.0 at r 35.8; bottom r 34.3 (1.5 deep) from Y 297.87 to 299.50
- load flank (low Y) 30 deg from the radial plane; the other flank 45 deg
- full depth over θ 50-130 and 230-310 (θ from +X toward +Z about the yaw axis; the seam and lugs at 0/180, as in the
  arm's model), with run-outs to full wall by 40/140 and 220/320

**Build notes:**

- **Run-outs:** in this pass they are 3 steps each (depth ×0.25 / 0.5 / 0.75 over 3.3 deg). That makes small notches,
  and their local peaks are on the high side.
- **Parameters:** the section, arcs and Y position are in `dims.py` (`HUB['groove']`); `GROOVE_ON` is a global variable.
- **Cable window and wall:**
  - The groove clears the cable window (7.9 deg, r ≤ 31) by 32 deg of arc.
  - It leaves **6.3 mm** of spigot wall (r 28-34.3).
  - Nothing else in the wall at Y 297-301: the hub screws and their counterbores are inside r 16.5.

**FEA model:**

- The spigot is held **radially only** on its r 35.8 cylinder.
- It is held **axially only** on the groove's two 30 deg load flanks (Y-only restraint).
- The lugs are bolted (fixed holes).
- The arm loads go in as their reaction at the RS02 side: hub screws and step-ring face, -F and -M about the same point.
- No contact on the shoulder above (Y 302 face). The groove carries the whole axial couple, which is conservative for the
  groove.
- Mesh 1.5 mm, 0.4 mm on the flanks, 290,285 nodes. Peaks are unexcluded. Layer stress σy, hub printed with the yaw axis
  vertical.

| Region | Case A bulk SF | Case A layer SF | Case B bulk SF | Case B layer SF |
|---|---|---|---|---|
| Load flank, θ 90 side | 1.76 | **0.73** (30.7 MPa) | 2.56 | 1.11 |
| Load flank, θ 270 side | 2.91 | 1.81 | 2.24 | 1.71 |
| 1 mm land below the groove (Y 296-297) | 1.54 | **0.96** | 1.79 | 1.19 |
| Spigot ring (r 28-35.8) | 0.96 | **0.36** (63 MPa) | 1.12 | 0.42 |
| Lug A root | 1.27 | 0.51 | 2.01 | 0.82 |
| Lug B root | 1.10 | 0.44 | 2.01 | 1.12 |
| Hub top (Y 311.5-320) | 1.02 | **0.40** (56 MPa) | 1.50 | 0.69 |

![groove](A_hub_groove_sigma_y.png)

**Where the peaks sit:**

- **Spigot ring peak:** at θ ≈ 137 deg, Y 297.2. That is at the end of a run-out, where my stepped run-out leaves a notch.
  The real smooth run-out will be lower there.
- **Hub top peak:** at Y 319.5, next to where the load goes in at the step ring. It is partly the rigid load application.
- **Load flank and land:** the clean part of the model. There the layer stress is under 1.5 in case A:
  - flank 0.73: across the layers, the 30 deg flank's own bearing
  - land 0.96: the 1 mm land below the groove, loaded across the layers

**Answers for the arm thread:**

1. **Print orientation:**
   - **Their assumption is ours:** the RS02 side (Y 319.86) on the bed, with the spigot and lugs growing up (the layers
     normal to Y).
   - **The dished top:** that face is the bed side. The bed contact is the step ring and centre (r < 23.5). The dish
     annulus (floor at Y 318.36, 1.5 mm above the bed) needs support, which pulls out radially at the open rim.
   - **The groove:** the 30 deg load flank becomes a 60 deg overhang, 1.5 mm tall, over 1.5 mm of reach. That is
     printable with slight droop (about 0.2 mm) on a face that bears load.
   - **Recommendation:** keep the orientation. If the droop matters, either print the flank at 45 deg and accept a
     bigger radial push, or measure the printed flank and fit the ridge to it.
   - **On its side:** the spigot loses roundness (layer lines along the cylinder), so no.
2. **Clearance:** yes. 6.3 mm of wall is left, and the cable window and screw counterbores are clear (above).
3. **Hub stresses:** the table above.
   - The groove and land are below 1.5 across the layers in case A.
   - **What governs is layer shear and bending of the land and spigot ring, not flank bearing.** The flank's bulk SF is
     1.76, but its layer SF is 0.73.
   - So 1.5 mm depth is not the limit; the hub's layer direction is.

**What would fix it**, still to try:

- smooth run-outs instead of steps (removes the notch peak)
- a longer spigot land: move the groove up so the land below is 2 mm
- a shoulder contact at Y 302 to share the compression side
- a hub printed with the spigot's layers running along the load. That is the side-print, which costs roundness.

**Hub mass with the groove:** 69.3 g.
