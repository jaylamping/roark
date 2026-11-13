# DESIGN: sonnet-c, link_organic

**Idea:** one tapering bone: a domed elbow boss that the shaft grows out of, a waisted rounded-rectangle shaft that flares
into a cuff, and a cuff that splits into two cheeks; the Ø6 cable runs straight inside it.

**Tried and dropped**
- Loft of 18 superellipse sections: pinched to a point near Z -150 whatever I changed (spacing, shape, number of lofts).
  Dropped after about 10 minutes, cause unknown. It gave the best looking round section.
- Idea B, a flat leaf (one outline, 12 mm thick): plate-like (flat_share 0.70), and by hand too weak in +Y bending.
- First two-silhouette version without the dome: +Y gave 115 MPa at the narrow pad on the disc (SF 0.39). The six
  screw heads sit in Ø7 pockets in a 12 mm dome now, which spreads the moment into the disc.

**With another hour**
- Round, not rounded-rectangle, sections (a loft with guide curves, or a variable-radius fillet); R6 is what built.
- Fillet the seam where the shaft leaves the dome rim (R4 built on three of four edges, so I left all of them sharp).
- Run the bearing load as an even force on the half-holes, and the screw-hole support on the final model.
- Print-orient and slice it; I only argued the orientation from the layer table.

**Least happy with:** the form. It is a smooth flat strap, "less boxy" more than "grown". The shaft reads as a bar with a
fork on it, the dome/neck seam is a visible crease, and the stress numbers there moved between my iterations
(17 to 8 MPa from a change I did not expect to matter), so I do not fully trust the margin at the seam.
