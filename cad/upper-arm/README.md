# Upper arm, concept A (drum and caps): requirements and design notes

Left upper arm, from today's shoulder hub down to the elbow drum. Parts:

| Part | File | Prints | Notes |
| --- | --- | --- | --- |
| Front half | `upper_arm_organic_front_left.SLDPRT` | seam face down | Ruthex M3 × 5.7 inserts in its 4 posts; keys 2 and 3 |
| Back half | `upper_arm_organic_back_left.SLDPRT` | seam face down | M3 heads from the back; keys 0 and 1 |
| RS02 mounting ring | `upper_arm_organic_rs02_ring_left.SLDPRT` | RS02 face down | 11.8 mm, 6 × M3 × 16 into the RS02 flange |
| Master | `upper_arm_organic_master_left.SLDPRT` | — | the halves as one body, before the split |

Built by `cad/scripts/arm/organic_master.py` and `organic_parts.py`. Print projects come from `organic_print.py`. Checks:
`cad/_wip/organic-arm/cad/rs02_fit.py` and `print_check.py`. FEA: `cad/scripts/fea/organic_fea.py`.

## Elbow stop: rated to 17 N·m (Joey, 2026-11-10)

The elbow's hard stops, at 0° and 124°, are a printed 60° lug on the drum's inboard end. It runs in a slot in the forearm's
inboard cheek.

- **Rating:** the RS02's own peak torque, 17 N·m. The lug's contact centre is at r 33 (the pad spans r 30.1–35.9), so
  17 N·m is **515 N** on a lug end face. (Until 2026-11-11 this was given as 444 N, a conversion at r 38.25; 444 N is only
  14.7 N·m.) At 515 N, fine mesh: lug root bulk SF 1.98, layer 1.59. Elsewhere layer 1.17. The pad edge itself is a
  load-application singularity that rises with mesh refinement, so only the bench test can settle it.
- **Known limit:** 34 N·m (1030 N at r 33) is past it.
- **Impact:** a static rating does not bound impact. A back-driven arm stopping on the lug over a fraction of a millimetre
  can see well over 17 N·m: for example, 5 kg at 283 mm moving at 1 rad/s into 0.4 mm of compliance is about 33 N·m peak.
  Software must slow the arm before the ends of travel, and the bench test should include a measured drop or swing into the stop.
- **A harder impact can break the lug.** The lug is part of the back half, so a break means a reprint.
- **Hand-off to the software project:** software must limit speed and torque approaching 0° and 124°, so the stop is only a
  backup and never a routine end of travel. Concretely: a soft limit inside each end, and a torque limit at or under
  17 N·m wherever the arm can reach a stop. Track this in the software project.
- **Bench test:** see "Bench tests" below. The stop coupon is loaded to 515 N (17 N·m), then taken to failure.

## RS02 mounting and torque path

Positions come from the vendor RS02 model, not the drawing alone. `rs02_fit.py` places the vendor STL and checks
everything against it.

- **Axial stack:**
  - The flange (9 × M3 × 8 on Ø73) is 28 mm behind the front face.
  - The ring meets the flange at X 165.7.
  - The front face sits 0.4 mm off the drum's end-wall stop (R1; 0.2 until 2026-11-11). Axial freedom 0.5 mm nominal, 0.1 worst case.
- **Plug:**
  - Two radial sockets (power + CAN, in parallel) stand 180° apart on the back.
  - The used one is clocked to face the neck (φ 1.5°), the only place a plug and cable have room. The plug goes in on the
    bench, through a window in the ring, and its cable leaves straight up the neck.
  - The other socket is unused: one trunk drop per motor, no pass-through (marengo `hardware/electrical/pdb/PLAN.md`). It
    sits in a clearance notch.
  - Service: take the front half off (2 seam screws, 2 hub screws), then unplug. No full teardown.
- **Screws:**
  - The socket tabs cover 3 of the 9 flange holes, so the ring uses the other 6, with M3 × 16 button heads.
  - That gives 6.2 mm of thread against the vendor's 8 mm.
  - The tab screw heads (2.4 mm proud of the flange) sit in pockets in the ring.
- **Torque path ring → halves:**
  - Four keys on the halves' rib, two per half (φ 80, 120, 240, 280), run through open slots in the ring to 0.3 mm short of
    the RS02 flange.
  - Each key bears on one face only.
  - Key 0 and key 2 bear for one direction, key 3 and key 1 for the other. The other faces have 1 mm of clearance, so they
    never bear first.
  - Two crush ribs (0.25 mm) on each bearing face put both bearing keys of each direction in contact from assembly.
  - Layer directions: the halves print seam face down (layers normal to Z), so key bending and shear lie in their layers.
    The ring prints flat (layers normal to X) and takes its keys in bearing and in-plane shear.
- **Criterion (coordinator, 2026-11-11):**
  - (a) Any one key alone carries the RS02's own 17 N·m peak at bulk and layer SF ≥ 1.5, at the fine mesh, on the ring and
    the halves.
  - (b) 34 N·m is carried by two keys sharing, at SF ≥ 1.5.
  - (c) The faces that must not bear first are relieved.
  - Results are in the FEA table below.
- **Correction:** the 34 N·m motor-ring result reported until 2026-11-10 (SF 1.97 bulk / 1.63 layer) came from a bonded
  model. That model merged the ring into the drum and left the ring zone out, so the keys were never loaded. Loaded properly
  (one key, rigid notch faces), the old ring's keys gave SF 0.38 bulk and 0.20 layer at 34 N·m.

## Cable passages (for the wiring study)

The trunk comes down the neck, passes the rib at the top, turns in between the drum end wall and the RS02's back, then runs
through the hollow stub into the pocket under the inboard elbow cap. It coils there for the elbow's travel and drops into
the forearm. The elbow RS02's own cable plugs in through the ring window and goes up the neck beside the trunk.

Requirements (Joey, 2026-11-11). Each hand has its own CAN bus, and there is a reserve for a third thin pair (a future hand
camera). Every joint carries 48 V, GND and up to three signal pairs. Room to keep, total:
- Upper-arm yaw region and neck: 3.5 × 13 flat, or Ø9 round.
- Elbow and the forearm's fixed run: 3 × 12.

The total may be split across passages (Joey). The power pair goes in one, 3.5 × 5.6 for 18 AWG in the upper arm and
3 × 4.6 for 20 AWG at the elbow.

**Wire gauge: 18 AWG power for the arm, decided by Joey 2026-11-15** (the arm trunk was 16 AWG).
- **Upper arm, neck and hub window:** no change. Their room was sized for 16 or 18 AWG.
- **Elbow and forearm passages:** these were sized for a 20 AWG power pair (3 × 4.6), so 18 AWG uses their margin up rather than
  gaining.
  - With 18 AWG silicone at about 2.4 OD, the pair is about 2.4 × 4.8.
  - Under the inboard elbow cap, the one-layer coil (power pair plus the 2.2 × 8 signal pairs) then needs about 12.8 wide, against
    12.8 available: 0 spare instead of 0.8.
  - At the 3.5 × 5.6 allowance used in the upper arm, it needs 13.6: 0.8 short.
- **Open:** before the elbow and forearm are rebuilt, measure the 18 AWG wire actually bought. Then either:
  - widen the cap pocket by about 1 mm; or
  - route one signal pair (2.2 × 3.4) through another passage, as the split above allows.
- The drop into the forearm (3 × 10) was already 2 mm too narrow; its planned widening to 4 × 12 covers 18 AWG. The three signal pairs go in another, 2.2 × 8 together or 2.2 × 3.4 each. A twisted pair is
never split, 48 V and its ground stay together, and no outside shape grows for wiring. Every upper-arm passage below meets
the single-passage total, so no split is needed there.

| Passage | Where | Free section (smallest) | Required room | Status |
| --- | --- | --- | --- | --- |
| Neck, at the seam posts | Y 272, between the two Ø7.5 posts | about 30 × 48 mm | 3.5 × 13 or Ø9 | meets |
| Neck, at the hub posts | Y 292 | about 37 mm wide | 3.5 × 13 or Ø9 | meets |
| Neck, open sections | Y 248–288 | 1340–3240 mm², largest circle Ø20–60 | 3.5 × 13 or Ø9 | meets |
| Into the drum | the neck opening at the drum top | the full neck section | 3.5 × 13 or Ø9 | meets |
| Past the rib | rib gap, φ −15° to 15°, X 144.5–153.9 | 9.4 (X) × 19.7 (tangential at r 37.7) mm | 3.5 × 13 or Ø9 | meets |
| Down to the stub | between the drum end wall (X 144.5) and the RS02's back (X 152.3), inside r 32.5 | 7.8 mm wide, open across | 3.5 × 13 or Ø9 | meets |
| Hollow stub | Ø32 bore, X 134–145.5 | Ø32 | 3 × 12 | meets |
| Into the cap pocket | the opening in the cheek's 6808 shoulder layer, r 21.5 | Ø43 | 3 × 12 | meets |
| Under the inboard elbow cap | coil at r 22–34.8, under the cap's hollow underside | 4.3 deep × 12.8 wide, one layer | 3 × 12 | meets: 1.3 mm spare depth, 0.8 mm width |
| Drop into the forearm | the channel from the pocket down the inboard cheek | 3 × 10 | 3 × 12 | **2 mm too narrow** (forearm part): widen to 4 × 12 with the forearm rebuild, in the cheek web away from the bearing |
| RS02 plug and cable | ring window, φ ±16°, through the ring, opening into the neck | plug body 16 × 6.5 × 15 and a Ø7 cable, 0 interference | the RS02's own cable | fits, checked with the vendor model |

Bend radius: the coil under the cap is flat and bends in its own plane, at r 22 and up. The 25–30 mm dynamic radius applies
to a round bundle and doesn't apply there.

### Drop splices and fuses in the arm (checked 2026-11-15)

Sources: the trunk spec, marengo `hardware/electrical/wiring/left-arm-trunk/README.md` and `BUY_LIST.md` (option B: spliced trunk,
inline 58 V Littelfuse 997 MINI fuse on every drop, XT30(2+2)-F plug on each RS02 / RS00).

- **The elbow RS02's own cable ends inside the upper arm.** It is the M14 drop: from the XT30(2+2)-F plugged into the RS02's
  socket at the ring window, up the neck, at most 150 mm, to the **M14 splice** on the trunk. Per the trunk spec that splice is at
  the shoulder end of the upper arm.
  - The M14 splice has two inline fuse holders: the 5 A drop fuse, and the 5 A segment fuse for the elbow crossing (S4).
  - The splice lump is about 6 mm across, with its four conductors staggered 10 mm apart.
- **Room in the halves: yes, no change needed.**
  - The neck cavity, halves closed, is 1438-3393 mm² at every 5 mm from Y 250 to 295.
  - It takes two inline holders side by side (assumed 15 × 10 mm in section and about 38 mm long; Joey to check the holders he
    buys) beside the 3.5 × 13 bundle reserve.
  - A drop of up to 150 mm from the plug, at about Y 252, reaches a splice anywhere in Y 255-295.
- **Fuse change: only by opening the front half.** That means 2 seam screws and 2 lug bolts; the ring and plates stay with the
  back half and the hub. There is no hatch, and adding one would change the halves, so the front half is the cover the trunk spec
  asks for ("put each fuse holder where a hatch or cover gives access").
- **Forearm yaw RS00 (M15 drop, 3 A fuse, the 120 Ω terminator, the hand drop):** all in the forearm, on the static side.
  - The trunk spec found little room there ("RS00 fills it").
  - That is an open item for the forearm rebuild (a pocket for a holder, the splice and the hand drop's XT30 cap). It does not touch
    the halves.
- **Through the hub slot: only the bare trunk segment S3** (power pair, CAN, reserve pairs). The M13 splice is at the yaw RS02
  housing, outside our arm. M14 is inside the arm. No plug or fuse holder passes the slot.
- **Mismatch to settle: the elbow segment's power wires.**
  - The trunk spec has S4 as **2 × 18 AWG red + 2 × 18 AWG black, paralleled per rail** (for RS00 plus the future hand, about
    6 A).
  - The A3 study and the elbow cable rig assume **one 18 AWG pair**. Four power wires don't fit A3's strip: the capacity drops to
    about 107 deg for 124 needed.
  - One 18 AWG silicone pair carries 6 A comfortably, so the paralleling looks like margin, not a need.
  - **Decision needed:** S4 as one 18 AWG pair (A3 works as studied), or as four wires (A3 needs rework).

### Elbow cable: findings for the elbow and forearm rebuild (2026-11-15)

**Decision (Joey, 2026-11-15 05:05Z): option A3, the inside spiral, rig first.** The halves print only after the rig passes, the bench passes and the corrected hub exists. The outside back loop (11-08) is superseded, pending the rig.

The options and the recommendation are in [ELBOW_CABLE_STUDY.md](../reviews/upper-arm/20261115_elbow-cable/ELBOW_CABLE_STUDY.md). In short: a flat clock-spring of the power pair under the inboard cap, with the signals on an FFC, and forearm changes only.

Checked against our current parts: the upper-arm R1h back and R1g front halves; the forearm parts, whose exports (11-10) match the
forearm models except the inboard cheek's stop lug, 23 min newer and away from this region. Exports in `cad/exports/forearm/`.

- **Which route the parts build.** The organic parts build the **internal** route:
  1. the rib gap and the drum end wall;
  2. the hollow stub, Ø32;
  3. the cheek's shoulder-layer opening, r 21.5;
  4. a flat one-layer coil in the pocket under the inboard cap (r 22–34.8, 4.3 deep);
  5. the drop slot down the inboard cheek (`organic_master.py`: CAP, POCKET, STUB_PASS, POCKET_DROP).

  They have no outside back loop, and no clip or saddle for one. The back loop (round cable in loom, about 190 mm free, R ≥ 27.9,
  Joey 2026-11-08) is still written in `upper_arm_requirements.md` and `forearm_requirements.md` and in the trunk README. The
  organic parts don't implement it. **Which of the two stands is open.** (An earlier note of mine called the back loop's R 27.9
  "unaffected" by 18 AWG; that requirement isn't built.)
- **Coil length and turns over 0–124°: not designed.** No file gives the coil's length or number of turns.
  - The pocket is an annulus r 22–34.8 (12.8 radial) × 4.3 deep, and the bundle it is sized for is 3 × 12 laid flat in one layer.
    The bundle fills 12 of the 12.8 mm radially, and all of it with 18 AWG (above).
  - A wound coil has to change radius as the elbow turns. 124° is 0.34 turn: a 1.25-turn coil at r 28 (201 mm, the render's
    assumption) needs its mean radius to move by roughly a third, about 7-9 mm, against 0-0.8 mm free.
  - So the coil as specified cannot wind and unwind through 124°. Its geometry has to be designed with the elbow/forearm rebuild:
    for example, wires spread across the annulus with the length to spare, a narrower bundle, a deeper pocket, or the back loop.
- **Cap-rim pinch at the drop slot: real in the current parts, not a stale-export effect.**
  - Measured between the inboard cap (`forearm_organic_cap_inboard_left`) and the inboard cheek: the coil pocket is 4.3-5.5 deep
    (X) at r 24-34.
  - Under the cap's rim (r 35.9-36.9, arm Y 173-174), the free gap along X is **1.2 mm** all round. Where the drop slot starts
    (θ 180, |Z - CZ| up to 5), it is 2.4 over about 4.5 mm of the slot's width and 1.2 over the rest. Then the slot is 3 × 10.
  - The wires have to pass under that rim. 18 AWG is about 2.3-2.4 OD, and the six wires side by side need about 9.4 wide.
  - **Fix (forearm parts only):** cut the cap rim and the cheek recess open over the slot's width, at least 3 deep and 12 wide,
    when the drop is widened to 4 × 12 as already planned.
- **The upper-arm halves are not involved in any of these.**
  - Below Y 185 the halves start at X 141.5. The cap, the cheek, the stub ring, the pocket and the drop slot are all forearm
    parts, at X 125.6-141.
  - The halves' own passages (neck, rib gap, down to the stub) meet the 3.5 × 13 reserve, and they gain room with 18 AWG.
  - **One condition:** if the rebuild chooses the outside back loop instead of the internal route, the cable has to leave the
    upper arm before the elbow. The halves have no exit for that, so they would change. Decide the elbow route before the halves
    are printed, or accept that the halves commit the arm to the internal route.
- **Signal wires our passages were sized for:** up to three signal pairs per joint (Joey, 2026-11-11), each pair 2.2 × 3.4, three
  together 2.2 × 8. That fits pairs of about 1.1 mm OD wire: 26 AWG silicone, as CABLE_SLACK assumes ("plus 26 AWG pairs"). One
  26 AWG pair, or two 28 AWG pairs plus a reserved pair, both fit inside that allowance. Free sections are from `cad/_wip/organic-arm/cad/passages.py` (neck slices) and
the CAD dimensions (everything else).

## FEA

TABLE

## Bench tests

Full steps for the printed bench article (assembly, inspection, key coupon, stop proof load, whole-arm torque test to
17 N·m, when to stop): [BENCH_TESTS.md](BENCH_TESTS.md). The list below is the summary.


1. **Stub coupon** (`prints/upper-arm/upper_arm_organic_stub_coupon.3mf`), **done 2026-11-11:** a 6808 inner race fits
   perfectly on the printed Ø40.0 stub (two half-stubs, seam closed, 3 walls / 15%). No caliper reading. The stub stays at
   Ø40.0.
2. **Stop coupon:** the lug and its slot, loaded to 515 N (17 N·m at r 33) and held, then taken to failure. Record the failure load
   and where it broke.
3. **Ring-and-key torque coupon** (`prints/upper-arm/upper_arm_organic_key_coupon.3mf` plus a second ring):
   - Bolt the ring to a flat plate through its six holes.
   - Engage the key coupon in its slot and load the key face through a lever.
   - Hold at 453 N (17 N·m on key 0 alone), then take it to failure.
   - Record the load and where it broke (key, ring, or the rib).

## Forearm to-do, from this round (the forearm is on hold until the upper arm prints)

- Widen the drop channel from the cap pocket into the forearm from 3 × 10 to 4 × 12.
- Open the drive shaft's ribbon window from 10 to 12 mm for a 10-way 1.0 mm FFC (11 mm wide). Keep the 12 mm coil height.
- Check the forearm's fixed run (belly channel, stub-ring slot) against 3 × 12, splitting power and signal where that avoids bulk.
- The vendor RS00 model is 51.0 mm long plus a 0.4 mm output step. My A2 fit check used a 46.1 mm cylinder. Re-check A2
  against the vendor model.
- Re-export and record the stale forearm STLs (inboard cheek and inboard shell).
