# Upper arm bench article: assembly, inspection and bench tests

These printed halves are a **bench test article, not for robot use**. Use them to check the fit, then the strength, before a
robot release. They apply to the R1 halves (`prints/upper-arm`, commit 70cf634) and to any later revision unless that
revision's notes say otherwise. The ring is the 2.2 mm-chamfer, no-brim ring.

Tools: calipers, a torque driver with 0.35 N·m, a bright torch, a fine paint pen, a luggage or hanging scale (at least
60 kg), a lever bar of known length, a vise or bench clamp for the hub, and a thermometer (IR is fine).

Before any test, mark witness lines with the paint pen:
- across the ring and each half, at every key;
- across the hub and the arm at the seat;
- on the inside of the back half at the neck-opening edge, φ about 41° (where the rib meets the drum wall at the top edge of
  the neck opening, X about 154). Look at it through the open seam with the torch before closing.

A witness line that breaks or shifts means something slipped or yielded.

## 1. Inspect the printed parts (before assembly)

1. **Support off fit faces:** remove all support, then check each fit face with the torch. If anything is still stuck to
   one, scrape it flat with a blade; don't sand.
   - **Halves:** the RS02 bore, the rib face the ring sits on, the key flanks and ends, the stub, the hub seat bore, the
     hub-lug posts.
   - **Ring:** the slot flanks, the bore, both flat faces.
2. **Measure and write down:**
   - stub Ø (target 40.0, on each half, seam closed);
   - key thickness across the crush ribs (rib height target 0.25 above the key face);
   - ring thickness (target 11.8);
   - hub seat bore Ø (target 71.8).
3. **Look for print faults:** layer gaps, and under-extrusion in the 100% zones (drum inboard end, keys, rib, hub band). In
   particular look at the rib-to-wall corner at the neck opening on both halves.

## 2. Assemble (order matters)

1. **Inserts:** clear the front half's insert holes with a Ø4.0 drill by hand, then press in the Ruthex M3 × 5.7 inserts.
2. **Ring to RS02, on the bench:** six M3 × 16 button heads, each with an M3 washer under the head (the ring is PETG). Torque
   0.35 N·m in a star pattern. Retorque after 24 h.
3. **Plug in the RS02:** plug in its cable through the ring's window while it is still on the bench.
4. **Back half:** drop the RS02 + ring into the back half. The keys' crush ribs need a firm push the first time. **Stop**
   if it drops in loose or needs a hammer, and tell me.
5. **Route the RS02 cable and the trunk** into the back half, up the neck, **before** closing. The straight plug-cable
   envelope hits the hub; the real cable has to turn earlier.
6. **Front half:** close it, then fit the two seam screws.
7. **Hub:**
   - the spigot goes into the seat;
   - each hub lug sits between its two posts;
   - fit the two seam bolts through the lugs and the two hub screws.
   - Check the arm turns freely on the RS02 over its range. Check the witness lines line up.

### R1c / R1d halves: hub and assembly order (2026-11-12)

R1c and R1d halves have a ridge inside the hub seat that closes around a groove in the hub spigot. R1d also has 12 small crush
ribs on the ridge's low-Y flank (6 per half, about 1 × 1 mm, 0.25 proud). The ribs are meant to be squashed when the halves
close: that is how the flank seats without play. Don't file them off.
- **They need the grooved hub, rev C+** (shoulder thread, `shoulder_hub_left.SLDPRT`, fd0cef8 or later).
- **They will not close around today's hub.** The ridge sits 1.3 mm into its plain spigot, about 220 mm³ of overlap per half.
  Don't force it.
- **Once assembled, the hub is captive.** It can only come out by splitting the arm (seam screws and lug bolts out, front half
  off).

The hub can't go in from the end once the halves are closed. It goes on **before** the front half, so steps 5 to 7 above
become:

5. **Inspect each half's hub end** before anything else, with the torch:
   - **Ridge:** it prints on tree support, hanging from the bore's ceiling with the seam face down. Pick the support off the
     tip and the high-Y flank, and scrape any stub flat. Keep the low-Y flank and its ribs clean, but don't sand them.
   - **Fin undersides and post faces:** they face the hub's lugs with 0.1 clearance and also print on support. Clean them
     and check the lug faces will sit flat.
   - **Seat floor (Y 295.7) and the end face:** the end face bears on the hub disc, so it must be clean and flat.
6. **Cable before the hub:** route the RS02 cable and the trunk up the neck. Then hold them clear of the spigot and the lugs'
   path while the hub goes in. The hub drops in along Z and would pinch a cable left across the seat.
7. **Dry test fit, with no screws and before any load:**
   - Lay the hub into the back half: its groove takes the back ridge, and its lugs sit between the back posts.
   - Close the front half over it slowly. Seat it on the RS02 ring's keys first, then press it down over the hub: the
     ribs crush in the last 0.1-0.2 mm.
   - The seam faces must meet all round, with no gap a 0.1 mm feeler enters.
   - With the halves held closed, try to push the hub in and out along its axis. **R1d: no play you can feel or measure**
     (under 0.05 mm with a dial gauge). The ribs should take it all up.
   - **Stop and tell me** if the seam won't close, or if there is play. Play means the ribs didn't print proud enough, and
     the load would go to the lug bolts first. Don't force or sand anything.
   - Take it apart and look at the ridge flanks and the ribs for marks. Crushed rib tips are expected; marks along the whole
     flank are not.
8. **Assemble:** the RS02 + ring and the cable in the back half as above. Then the hub into the back half (ridge into groove,
   lugs between the posts). Then the front half closed over both.
   - Then the two seam screws (M3 × 18 into the inserts) and the two hub lug bolts (M3 × 25, Ø5.5 socket or Ø5.7 button
     head, no washer) into the front-half inserts.
   - Torque all four to **0.5 N·m**. That is my figure for M3 into these inserts in PETG, not a datasheet value. Retorque
     after 24 h.
   - Check the arm turns freely on the RS02, and that the witness lines line up.

## 3. Key coupon test (before the whole-arm test)

`prints/upper-arm/upper_arm_organic_key_coupon.3mf` (33 min) is the back half's key 0, with its rib and a patch of wall.
For its ring, use your **first ring** (the 1.2 mm-chamfer one): its slots are identical, so the new ring stays in the arm.

1. Bolt the ring flat to a plate through its six holes.
2. Engage the coupon's key in slot 0, then load the key face through a lever.
3. Hold **453 N for 10 s**. That is 17 N·m on key 0 alone, the single-key rating. Look for whitening and cracks, and check
   the witness line.
4. Then take it to failure. Record the load, where it broke (key, ring, or rib), and a photo.

The model says key 0 alone is SF 1.62 bulk at 17 N·m on the halves and 1.50 on the ring. A failure below about 680 N
(1.5 × 453) means the printed strength is below what we assumed, so stop and tell me before the whole-arm test.

## 4. Stop proof load (on the article: proof only, not to failure)

The stop lug is part of the back half, so a break means a reprint. On this article it gets a proof load only.

**Safety:** wear eye protection. Stand to the side of the load line, never in line with the lever or the block, and keep
hands and faces clear of the arm while it is loaded. PETG can let go without warning, and a lever under load springs.

1. Clamp the hub.
2. Push on one lug end face square to it, at r 33 from the elbow axis (the middle of the pad), with a block and the scale.
3. **Load in stages:** 130, 260, 390, then 515 N (13, 26, 40 and 52.5 kgf). Hold each for 10 s and unload fully between
   stages.
   - After each stage, look at the lug root, the lug backing inside the drum, and the hub seat and lugs, and check the
     witness lines.
   - Stop at the first whitening, crack, creak or shifted line.
   - Do one end of travel completely first, then the other.
4. **R1c / R1d, after the last stage at each end:** take the front half off and look at the hidden ridge and ribs:
   - cracks at the ridge root, especially at its ends (θ about 35°, 145°, 215° and 325°);
   - whitening on the low-Y flank;
   - marks on the hub's groove flank;
   - the fins.
   Then close it and re-check the axial play (step 7 of the R1c / R1d assembly). Play that wasn't there before means
   something yielded: stop and tell me.

The test to failure needs a separate stop coupon (lug and slot). Tell me if you want one made.

## 5. Whole-arm torque test, up to 17 N·m

The RS02 back-drives when unpowered, so turning its output by hand puts almost no torque into the arm. The torque has to come
from the RS02 itself:
1. Clamp the hub to the bench with the arm horizontal.
2. Bolt a lever to the RS02 output.
3. Rest the lever's end on the scale (or tie it to the hanging scale), so the output can't turn.
4. Command the RS02 in torque mode, or in position hold against the lever.

Torque = scale reading (N) × lever length (m). Do both directions:
- **−T** (keys 3 and 1 bear): this one loads the back half's neck corner at φ 41° hardest, so do it first.
- **+T** (keys 0 and 2 bear).

Steps: **5, 10, 13.5, 17 N·m**.
- Hold each step for about 5 s. Keep the RS02 cool: it is not rated for long holds at peak.
- Unload fully between steps.

After **each** step, with the load off:
- **Neck corner, back half, φ about 41° (and the front half's at φ about 336°):** look for whitening (white haze in the
  PETG), a crack, or a broken witness line. Use the torch through the neck opening. After 13.5 and 17 N·m, also take the
  front half off and look directly.
- **Keys and ring:** witness lines across ring and halves. Any shift means the crush ribs have flattened and one key per
  direction now carries the torque. Note it, and expect it after the first peak load.
- **Hub seat and lugs:**
  - the seat witness line;
  - the seat lip for cracks or whitening;
  - the two hub lugs and their posts;
  - the seam bolts for looseness.
- **RS02 flange:** temperature, and whether the six ring screws are still tight (mark them).

**Stop the test at once and tell me** if you see any of these:
- whitening or a crack anywhere;
- a crack or creak sound;
- a broken or shifted witness line at the corner, the seat or the lugs;
- the arm or hub moving on the seat;
- a ring screw loosening;
- the flange over 50 °C (PETG softens near 70 °C).

Don't go past 17 N·m on this article: 34 N·m is outside its rating (stated limits below).

Model figures at 17 N·m (R1 geometry, fine mesh, nothing left out):
- **Neck corner:** about SF 2 or more.
- **One key per direction** (after the crush ribs flatten): SF 1.62 on the halves, 1.50 on the ring.

So nothing should show at 17 N·m. If the corner whitens below 17 N·m, the printed layer strength is below our 0.5 × yield
assumption.

## Stated limits of this article

- **Torque path:** rated 17 N·m with one key per direction. 34 N·m is not met.
- **Stop:** rated 17 N·m static (515 N at r 33). Impact can exceed that, so software must slow the arm before the ends of
  travel.
- **Neck corner:** layer-limited, bending across the back half's layers. It is the reason for the next revision (R2).
