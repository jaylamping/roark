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

### R1c / R1d / R1e halves: hub and assembly order (2026-11-12)

R1c, R1d and R1e halves have a ridge inside the hub seat that closes around a groove in the hub spigot.
- **R1e** (the play-free version): no crush ribs. The ridge's flank is line-to-line with the groove, and a printed shim ring
  between the end face and the hub disc takes up the rest. Pick the ring once, by trial, on the coupon (section 2b), and use the
  same ring in the arm. The ring goes over the hub spigot, flat against the disc, before the hub goes into the back half.
- R1d (superseded): 12 small crush ribs on the ridge's low-Y flank, meant to be squashed on closing.
- **They need the grooved hub:** R1e the rev D hub (shoulder thread, bc16e97 or later); R1c / R1d rev C+.
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
   - R1e: the chosen shim ring is on the spigot, against the disc.
   - Close the front half over it slowly, by hand. Seat it on the RS02 ring's keys first, then press it down over the hub.
     R1d only: the ribs crush in the last 0.1-0.2 mm.
   - The seam faces must meet all round, with no gap a 0.1 mm feeler enters.
   - With the halves held closed, try to push the hub in and out along its axis, and rock it. **No play you can feel.**
   - **Stop and tell me** if the seam won't close by hand, or if there is play. R1e: the ring is too thick (seam won't close)
     or too thin (play); go one ring thinner or thicker as in section 2b. Don't force it with the screws, and don't sand anything.
   - Take it apart and look at the ridge flank and the hub's groove flank for marks (R1d: crushed rib tips are expected).
8. **Assemble:** the RS02 + ring and the cable in the back half as above. Then the hub, with the shim ring on its spigot (R1e),
   into the back half (ridge into groove, lugs between the posts). Then the front half closed over both.
   - Then the two seam screws (M3 × 18 into the inserts) and the two hub lug bolts (M3 × 25 DIN 912
     socket head, Ø5.5, no washer) into the front-half inserts. Use socket heads: R1d's head counterbores are Ø6.0, too tight
     for a Ø5.7 button head.
   - Torque the two seam screws to **0.5 N·m**, and the two hub lug bolts to **0.3 N·m** (the cap, until the coupon's insert
     check in 2b step 4b passes at a higher torque). These are my figures for M3 into these inserts in PETG, not datasheet
     values: the insert's outer diameter and pull-out rating are not recorded anywhere in the repo. Retorque after 24 h.
   - Check the arm turns freely on the RS02, and that the witness lines line up.

## 2b. R1e shim ring and hub-end fit coupon (before printing the R1e halves)

**Picking the ring: start with the thickest ring, and work down until the front half closes by hand with the seam shut. Use that
one.**

R1e has no play by design. A thin printed PETG ring sits between the arm's end face and the hub disc, and you pick its thickness
by trial, once, at assembly.
- **Rings:** 22 rings on three plates, 55 min and 9 g in all. Each ring's thickness is marked by notches in its inner edge:
  thickness = 0.25 + 0.05 × (number of notches). 1 notch = 0.30 mm ... 17 notches = 1.10 mm.
  - The two thinnest (0.30, 0.35) are held to a thin outer skirt by three small tabs; snap the skirt off.
  - Keep the rings flat. Don't sand them.
- **Coupon:** the hub end of each R1g half, cut flat at Y 284. Back 72 min, front 67 min, 35 g. It has the seat,
  ridge, end face, floor, slot breaks and the four hub posts with their insert and clearance holes. It closes on a printed D3b
  hub (shoulder thread, 6b2fd93 or its release) with the two lug bolts, as the arm does.

0. **Bare fit first, no ring and no plates:** lay the hub into the back coupon and close the front coupon by hand. Note whether
   it closes, and the play along the axis and in twist. This shows the coupon and hub fit before anything is added.
1. **Calliper check, every piece:** measure every ring (four places) and every lug plate (two places) and write the readings
   on the set sheet. If a whole set reads thicker or thinner than marked by the same amount, it is offset (first-layer squish);
   note it. Print two full plate sets. If the pick lands between two steps, print the half steps around it if it is cheap.
2. Press the two inserts into the front coupon (clear the holes with a Ø4.0 drill by hand first).
3. **Pick the ring:**
   - Slide the thickest ring (17 notches) over the hub's spigot, flat against the disc.
   - Lay the hub into the back coupon (lugs between the posts), then close the front coupon over it **by hand, no screws**.
   - If the seam doesn't close fully, take it apart and try the next thinner ring. Keep going down until the front closes by hand
     with the seam shut. That ring is the one.
   - **Never force it closed with the screws.** A ring that's too thick only closes by crushing the ridge flank, which makes play
     later.
   - **R1g (the D3b hub's extended lugs): then pick the lug plates.**
     - **The plates:** flat printed plates, 0.25-0.75 in 0.05 steps, two of each, on plates A and B (about 15 min each). They
       are marked on the inner edge: wide notch = 0.25, narrow = 0.05, counted from 0.25.
     - **Fitting:** one plate goes on each Z face of each lug, with its lip hooked under the lug's free end. The bolt hole lines
       up with the lug's.
     - **Before the plates:** the two brass inserts in the front posts must sit flush with the post face or up to 0.1 below it.
       Check with a straightedge across each insert. A proud insert would lift the plate. The plate's Dia 3.8 hole is smaller than the
       insert's Dia 4.0 hole, so the plate sits on the insert's rim and holds it in against the bolt's pull.
     - **Pick, with the ring chosen:** "Start each lug with the thickest pair, and take one plate down a step at a time,
       alternating sides, until the front half closes by hand with the seam shut; use those." Both lugs are picked in the same
       trials.
     - **Never force it closed with the screws.**
4. With the chosen ring and lug plates in, fit the two lug bolts (M3 × 25 DIN 912) and torque to **0.3 N·m** (the cap). The
   seam must stay shut: no gap a 0.1 mm feeler enters, if you have one; otherwise none you can see against a light.
4b. **Insert check (one lug bolt, plates in):** mark the insert's rim and the post face with a fine pen line across both.
   Tighten that bolt in steps of 0.3, 0.5 and 0.7 N·m. After each step, back the bolt out and look: has the insert moved
   (pen line broken, rim proud of the face, insert turning)? Record the torque at which it moved, or that it did not move
   at 0.7. The lug-bolt torque for the arm is then the highest step with no movement, less one step, and never above 0.5.
   Re-press or replace that insert before going on if it moved.
5. **Rock check:** clamp the hub. Push and pull the coupon along the hub axis, then rock it firmly by hand in every direction.
   R1g: also twist the coupon about the hub axis, both ways: there must be no click or free turn (the lug plates take the
   yaw torque).
   There should be no movement and no click. Then do ten firm rocking cycles and check again.
6. **Open and look:** take the bolts out and the front coupon off. Check the ring (flat, not cut or crushed at its inner edge),
   the ridge flank and the hub's groove flank (marks, scuffing), especially near the seam. Photograph them.
7. Close again with the same ring and plates, lug bolts at 0.3 N·m, and repeat the rock check once.
8. **R1g (lug plates), after the stop-load test:** take the lug plates out. Inspect the post faces and the hub lug faces
   around each lug bolt for an imprint of the plate's hole edge, and at the plate's outer top corner (by the lug's root,
   X offset 34, on the back post of the +X lug especially). Record its depth by feel (fingernail: none / felt / catches)
   and photograph it. The FEA puts the stop's highest local pressure on that edge.

9. **Coupon load fixture (printed parts only):**
   - **Yaw:** clamp the hub. Bolt a printed lever to the coupon (any stiff PETG bar, 200 mm from the hub axis to the hook
     hole). Pull 8.7 kg on a luggage scale at 200 mm (17 N·m), each way, 10 s.
   - **Side load on the lug:** push the coupon sideways (along X) at the lug line with the scale, 5 kg, each way.
   - **Play:** read the movement at the lever tip with a dial indicator if you have one, otherwise with feelers against a
     fixed block, loaded and unloaded.
10. **24 h re-check:** leave it bolted 24 h, re-torque the lug bolts, and repeat the rock, twist and play checks once.

**Pass, before the halves are printed (all of these):**
- **Ring:** one ring closes by hand with the seam shut; the ring is flat, not cut or crushed.
- **Plates:** one pick closes by hand with the seam shut; the plates are flat and whole (the strip above the hole intact).
- **Twist check:** no click or free turn by hand; under the 17 N·m lever, play at 200 mm under 0.5 mm and back to zero when
  unloaded.
- **Imprint:** none, or felt only, on the post and lug faces around each bolt; nothing that catches a fingernail.
- **24 h:** the same after the re-torque.

**Otherwise stop and tell me.**
- Every ring too thick (even the thinnest won't close), or every ring too loose (even the thickest rocks): the set is offset.
  Reprint the set shifted (I'll send the file); the coupon and the arm stay as they are.

The same ring then goes into the arm, together with the same printed hub.

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
   - the fins;
   - the end face's inner edge: the ring where the small 45° chamfer at the top of the bore meets the end face (it bears on the
     hub's disc, all round), and the matching ring on the underside of the hub disc. Look for crushing, a shiny flattened band,
     or whitening. The model puts its highest local contact pressure on that edge, in the stop case and in normal lifting (G90).
   - R1e: the shim ring. Measure it with the calliper at four places and compare with its marked thickness (or the reading from
     2b step 1). It carries all the axial load, so a ring now thinner by 0.03 or more, a shiny flattened band, or a cut inner edge
     means it is creeping or crushing: stop and tell me.
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
