# C2 restatement (written 04:45, before any C2 modelling)

1. **What it is for:** the forearm link of a humanoid arm: bolted by six M3 to a motor output at the elbow, a Ø8 pin and a
   swinging part (Ø30 sweep) between two cheeks at the wrist; carries 60 N at the pin in +X, -X, +Y; carries a Ø6 cable.
2. **Fixed:** elbow face (flat ring Y -4, Ø30..Ø62, six Ø3.4 holes on Ø50, Ø30 bore, six Ø7 x 10 clear cylinders on the +Y
   side); wrist (pin Ø8 at X0 Z-200 along Y, inner cheek faces Y ±16 flat over >= Ø16, >= 5 mm round the pin hole, slot clear
   for |Y|<16 from Z -183 down); one straight clear Ø6 line elbow-to-wrist.
3. **Good means:** one flowing, tapering, restrained form that reads as one grown piece; mass <= the boxy link (261 g);
   SF >= 2.0 on von Mises, layer tension and layer shear in the three load cases; printable in PETG on 256 mm bed, one piece, no
   closed cavity.
4. **Mine to choose:** section shapes, taper, how disc and wrist grow out of the shaft, where the Ø6 line runs, print direction,
   the outer cheek faces, disc outer diameter (>= 62), pads/ribs.
5. **Ask if unclear:** none, I am working alone; decisions go in DESIGN.md. Assumption: no material at Y < -4 within R 36 of the
   elbow axis (the motor body sits there); beyond that material may go below Y=-4.

**Organic, in my words:** one continuous skin whose section changes smoothly from end to end, with every transition a
blend and no flat plate or sharp inside corner except the mating faces themselves; material is where load goes and the
outline reads like a bone: wide and thin at the elbow, a slim oval shaft, swelling into a cuff that splits into two
cheeks at the wrist.

**Three things I will not do:** (1) no box, plate or rectangular rib as a way to carry load, and no step in section;
(2) nothing that sticks out of the silhouette (no bosses, lugs, cable clips); (3) no unrounded outer corner and no
decorative cutout that does not take load or save mass.

Time budget (100 min set, 04:40 start): C1 done by 04:47; C2 shape 05:00-05:35 (checkpoint_01 by 05:04), detail and fixed-item
check 05:35-05:50, FEA 05:50-06:10, report 06:10-06:20.
