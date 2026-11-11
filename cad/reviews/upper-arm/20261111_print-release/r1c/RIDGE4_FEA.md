# R1c ridge4: bolted hub-seat FEA (2026-11-11)

Model: arm (R1c master, ridge as two partial revolves, hub-post fins) and the grooved hub as separate bodies. The seat is in
no-penetration contact, the lugs are in frictionless contact, there are two steel M3 bodies in the post bores, and there is no
preload. The hub is fixed at its top face (Y 319.86). G90 has 442k nodes; STOP_0 (515 N at the stop pad) has 549k.
Post-processing: `cad/_wip/organic-arm/cad/hub_r1c.py`, which classifies nodes against the grooved hub mesh. SF is against
45 MPa (vm) and 22.5 MPa (across layers: arm sigma z, hub sigma y). Format: unexcluded peak | 0.5/1/2 mm averages.

| Case | Region | vm SF | layer SF |
| --- | --- | --- | --- |
| G90 | arm, whole | 1.21, at the ridge-end notch \| 4.18/7.73/13.6 | 2.02 |
| G90 | hub, whole | 2.09 | 1.75 \| 2.69/2.91/5.82 |
| G90 | bolts | 81 MPa | |
| G90 | lug forces | axial 3 / 2 N, shear about 15 N | |
| STOP_0 | arm, ridge end at the arm's hollow inside (r 36.3, theta 145/215, Y 299) | 0.38 \| 0.95/1.48/2.67 | 1.44 |
| STOP_0 | arm, bore floor edge (theta 66, Y 296) | 0.45 \| 0.94/1.88/3.29 | 1.03 \| 3.49 |
| STOP_0 | hub land, the same contact edge | 0.37 \| 0.37/1.04/2.25 | 2.03 |
| STOP_0 | hub groove bottom (r 34.3, theta 136) | 2.59 | 1.09-1.10 \| 1.10/1.70/2.84 |
| STOP_0 | hub lug root (Y 296) | 1.01 \| 1.30/2.08/4.22 | 1.08 \| 1.08/1.71/3.14 |
| STOP_0 | bolts | 110 MPa (SF 5.8) | |
| STOP_0 | lug forces | -X: axial 27 N, shear Fz 148 N; +X: -5 N, -93 N | |

For comparison, the same model without the ridge (today's hub, r1c_c/r1c_d) gives the following at STOP_0: hub lug-root
layer 0.26 \| 0.45/0.83, bolts 770 MPa, and lug -X 453 N axial. At G90 it gives lug-root layer 0.46 and lugs 225/239 N axial.

Finding: at theta about 20-50 and 130-165 (and their mirrors) the arm has no seat wall below Y 299. The arm's hollow inside
reaches up to Y 299 there, with its inner surface at r 36.2-36.26. R1 has the same step. Near the ridge ends, the ridge's
root band (out to r 36.3) overlaps that surface by only about 0.06 mm, which leaves a knife-edge notch.
Proposed: (a) a solid seat collar behind the ridge arcs; (b) a 0.5 mm chamfer on the bore floor edge; (c) 0.4 mm rounds at
the groove bottom corners, with ridge tip chamfers to match. Waiting for a decision.

Closing path (`close_path_r1c.py`): the halves close along Z onto the grooved hub, the vendor RS02 and the ring with no path
collision. No point travels more than 0.05 mm before contact; the only hits are the faces that touch at the final position.
