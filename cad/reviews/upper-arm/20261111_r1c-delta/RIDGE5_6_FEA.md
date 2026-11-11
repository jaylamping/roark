# R1c ridge5 / ridge6 hub-seat FEA (2026-11-11)

Same model as RIDGE4_FEA.md. Post-processing: `cad/scripts/fea/r1c/hub_r1c.py` (JSONs in this folder).

- **ridge5**: arm + seat collar (r 35.9-37.4, Y 296-302, +185.9 mm3), 0.25 bore-floor corner ring (+7.5 mm3), 0.2 ridge tip
  chamfer. Hub: 0.4 rounds on the groove bottom and the spigot bottom edge, 1.0 lug-root fillet on the X faces. The groove
  cut still undercut the disc (Y 302-302.7). G90 passes. STOP_0 fails at the disc undercut (hub 0.21 at 0.5 mm) and at
  the 45-side groove corner (hub layer 1.07 / 1.00).
- **ridge6**: arm + 0.5 bore end chamfer, 45 flank moved -0.1 Y, top tip chamfer (34.5, 299.85)-(34.9, 300.70). Hub rev C+
  (no undercut, taper run-outs, r 25-28 fill). **But the R1.0 round on the 45-side corner did not build** (wrong edge
  filter), so that corner is sharp: a bound, not the design.
  - STOP_0 (sharp corner): the hub 45 corner layer is 0.68 | 1.17 / 1.52 (fails 1.2 at 0.5 mm). Lug root layer 1.26.
    Load flank 1.52. Arm >= 1.44. Bolts 100 MPa.
  - G90: **suspect**. The lugs carry 416 / 472 N axial (6 N in ridge5), the bolts 938 MPa, and the hub lug 1,484 MPa,
    though nothing on the lug side changed. To be checked by the ridge6b duplicate solves; not to be relied on.

WIP model hashes (SHA-256): UA_HUBSEAT_v31_ridge6_bolted.SLDPRT 2f2328c6c9dcb36718eb0a99b56e5f3ee7ab8f52bff99a08698ef9137991ae88

## ridge6b (ridge6 with the hub's R1.0 45-side corner built), each case solved twice

The two runs agree exactly (0.00 % on every region peak and average, the bolts and the lug forces). The ridge6 G90
outlier was a bad solve.

- **G90** passes 1.5 everywhere at 0.5 mm. Lowest: arm collar-corner layer 0.73 | 2.05; hub groove layer 1.52 | 1.95;
  hub load-flank layer 1.33 | 2.59. Bolts 81 MPa. Lugs 4-6 N axial.
- **STOP_0** passes 1.2 at 0.5 mm everywhere except one spot. **The hub groove bottom, 45-side, on the R1.0 round (r 34.38,
  Y 300.4, theta 139) has layer 0.87 | 1.16 / 1.41 / 1.81.** Next lowest: hub lug root layer 0.68 | 1.22; core 1.29; ring above
  the groove 1.37; load flank 1.52 / 1.55; ridge vm 1.47; arm collar-corner layer 1.53. Bolts 105 MPa. Lug -X: 15 N axial,
  260 N shear.

## ridge6c (the arm geometry released as R1c; one solve per case, hub as ridge6b)

Arm changes since ridge6b: the bore-floor corner ring now runs only where there is a floor (theta 72-108, front half), and
the ridge top is flat at Y 301.5 (both from the mesh gate). The released halves (ridge6e) also close a 0.01 mm lip where
that flat cut met the end chamfer. That is too small to change the FEA.

- **G90:** arm at 0.5 mm: lowest 2.42 (layer), 2.79 vm at the ridge root. Hub as ridge6b. Bolts 81 MPa.
- **STOP_0:** arm at 0.5 mm: lowest layer 0.51 | 1.29 / 1.98, at the collar's foot beside the hub post (theta 130, Y 295.9;
  1.53 in ridge6b with the full corner ring). vm 0.97 | 2.01 at the end of the corner ring (theta 72). Ridge 1.51, ridge
  root 1.80. Hub: groove corner layer 1.13 (the r 25 fill), load flank 1.52-1.55, lug root as ridge6b. Bolts 105 MPa.
