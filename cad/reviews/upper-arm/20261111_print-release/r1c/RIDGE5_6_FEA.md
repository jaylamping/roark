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
