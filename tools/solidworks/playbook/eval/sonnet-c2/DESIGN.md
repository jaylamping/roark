# DESIGN, C2 organic forearm link (run sonnet-c2)

**The idea, one sentence:** one tapering oval "bone" lofted from eight changing oval sections, swelling at the wrist into the two cheeks and growing out of a round, lipped elbow flange, with the 6 mm cable passage bored straight down it.

**Tried and dropped**
- Idea B, two slim struts side by side (`pictures/idea_b.png`): open cable path, and the struts need a separate joint at each end; the wrist ended as a box. Dropped for A, which has one skin, an enclosed passage and no joints.
- Filleting the stem into the flange rim (`fillet` on the 22 intersection edges): no round built at 5, 4, 3 or 2 mm. Left as a loft that starts inside the flange.
- Rounding the flange rim with `fillet` on circle edges: `edges_where` found none (full circles never matched). Replaced by a revolved profile with rounded corners (polyline arcs, so the rim is faceted on the STL).
- A root section that moves in Y (to stay flush with the mounting face and grow only on the back): the loft failed on every pair I tried that changed the Y centre (2 mm step), for a cause I did not find.
- A first-draft root only 4 mm thick: 44 MPa at the flange, factor 1.0 for +Y. A thicker root alone gave 24 to 29 MPa. What worked was a raised lip round the back of the flange plus a ridge along the cable passage, 21 MPa.
- A 0.0 mm-offset cable passage: left 1 mm skins in the 8 mm flange and was the source of the 29 MPa peak. Moved to Y +2.

**With another hour**
- Round the stem-to-flange junction and the cheek tips with real fillets (they are sharp where the loft meets the flange).
- Smooth the back of the flange: the lip and the ridge into the bore read as added parts, not as grown.
- Run the load on the half-hole that really bears, not a rigid load on the whole pin hole, and a mesh finer than 2.5 mm at the stem root.
- Add one more section at the wrist so the silhouette has no step at the slot ceiling.

**Least happy with:** the back of the elbow flange. The dished back with a raised lip and the ridge that runs into the bore is the part a reader sees as bolted on rather than grown; I added it for strength after the first FEA, not for the look. The step in the front-view silhouette at the slot ceiling (Z -183) is second.
