### The study: what was modelled

One multi-body part, `pair_fea.SLDPRT`, eight bodies, every one in its place in the housing frame:

- **Lower half**, PETG, its face Y -32 fixed (as the task says).
- **Upper half**, PETG, in its as-modelled place: 0.075 mm clear of the ring all round, split faces 0.8 mm apart.
- **Ring**, steel, dia 52 / dia 48 x 7: the outer ring.
- **Four screws**, steel: dia 5.5 x 3 head sitting on the counterbore floor, dia 3.0 shank with 0.2 mm clearance in its
  hole, and a dia 4.0 x 6 end standing for the thread in its brass insert, line to line in the insert hole. Head and
  end touch plastic, so they bond; the shank touches nothing. **This is how I judged the screws:** as tie rods that
  carry tension and shear between the halves, snug but **with no preload**. Preload is treated by hand below, and it
  is the larger load.
- **A soft plug** (0.2 MPa, 2 mm thick, bonded in the ring's bore) with its dia 6 hub hole fixed: it holds the ring
  while the ring is not yet touching a seat. It touches neither half.
- **Contact:** no penetration between the ring's outside and both seats (0.075 mm apart), and between the split
  faces of the two halves (0.8 mm apart; they never close under these loads, so that set is there and idle).
- **Load:** 300 N at the bearing centre (0, 0, 3.5) on the ring's bore, rigid. The bore of a steel ring carried on
  balls is close to rigid against PETG; the rigid load does not touch plastic.
- The shoulders are not in a contact set: no axial load is applied and they stand 0.1 mm off the ring.

### Predicted, then solved

| | Predicted (written in the log before the solve) | Got (mesh m) |
| --- | --- | --- |
| Nodes | 100,000 | 145,831 (1.46 times: the 0.7 mm screws took 38,680) |
| +Y: ring movement | 0.075 + about 0.5 mm | 0.159 mm: 0.075 clearance + 0.085 elastic |
| +Y: where the peak is | upper half at the crown, 18 to 38 MPa | **not there:** 2.5 MPa on the crown's outer face; the peak is beside the screw heads, about 4 MPa |
| +Y: screw tension | 75 N each | 74.2 to 74.9 N each, 298.3 N in all |
| +X: screw load | 24 N tension and 37.5 N shear each | 14.2 to 19.0 N tension; shear -2.2 N on the +X pair, +15.4 N on the -X pair |
| +X: ring movement | 0.075 + about 0.1 mm | 0.192 mm along X and 0.112 mm along Y |

The displacement was 3.6 times under my figure and the peak was not where I said, so by 07-done.md I stopped and
found out why before reading any stress as a result.

**Why the cap is not a beam with a load at its crown.** My hand model was the upper half as a 62 mm beam between the
screws with the bearing load at mid span (4,650 N.mm at the crown, 38 MPa) or spread as a cosine (1,900 N.mm,
17 MPa), on the crown section alone (I = 414 mm4). The study shows something else: as the screws pull the ends of the
cap down it wraps the ring, and the ring bears on **two bands 30 to 65 degrees either side of the crown** (pressure
1.9 MPa at 50 degrees, 0.1 MPa at the crown itself). Putting that measured pressure into the same hand formula, the
moment of the pressure on one side about the crown is 3,995 N.mm against 4,650 from the screws: the crown is left
with about 260 N.mm, 2.1 MPa, plus hoop tension; the study has 2.5 MPa there. So the hand model and the study agree
once the load is put where it really is. The pressure summed over the seat gives 273 N of the 300 (nodal stress is
not a force: 05-fea.md warns of this); the screws' section force gives 298.3. The cap is also far stiffer than a
beam of its crown section, because it deepens from 6 mm to 15 mm within 20 mm of the crown.

**Why the +X screw loads are not the cosine share.** I assumed the ring pressed on both halves alike. With 0.075 mm
clearance and no friction it does not: it settles into the **lower** seat's +X flank (bearing from -30 to -1
degrees, 7.8 MPa peak) and rides up 0.11 mm until it wedges under the upper seat at about 77 degrees. Statics with
those two angles: 292 N on the lower seat, 78 N on the upper, which loads the upper half with 17.5 N along X and
75.7 N upward. The study's screws carry 26.4 N of shear and 67.4 N of tension in all. Per screw that is 14 to 19 N of
tension against my first 24 (21 to 41 % under), explained by where the ring sits.

### Is the result valid (the playbook's list for contact)

1. **Reaction equals load:** 299.87 N on the face + 0.12 N on the plug along Y for the +Y case; 299.85 + 0.15 N along
   X for the +X case; other components under 0.1 N.
2. **How each body is held without the contact:** above. Nothing depends on the contact to be held.
3. **The pads' share:** the plug's hub carried 0.124 N of 300 (+Y) and 0.173 N of 300 (+X): 0.04 % and 0.06 %, read
   from the per-node reactions at the hub.
4. **Proof that the set is contact, not a bond** (ring with clearance all round: a small load in the working
   direction, not a reversal). At 1 N along +Y the ring moved **0.0773 mm**, and 0.0759 mm at 1 N along +X: it crossed
   the 0.075 mm clearance as a rigid body and stopped on the seat (0.93 N of screw tension appears in the +Y run). At
   300 N it moved 0.159 and 0.192 mm. Bonded, 1 N would move it a three-hundredth of the 300 N figure, 0.0005 mm:
   the response is 146 times out of proportion.
5. **Contact force against applied load:** the four screw sections carry 298.3 N for 300 N applied along +Y (99.4 %);
   in three slices along each shank the fit gives the same value within 0.1 N.
6. **Bodies split by geometry**, with a margin at every interface, and the script stops if a node fits no body:
   51,839 upper, 35,204 lower, 15,197 ring, 4,911 plug, 38,680 screws (mesh m).
7. **No solver question** came up (no "excessive displacement", no failure of equilibrium); the solver macro log
   shows `before 0, set err 0, after 7` (direct sparse) for every study.
