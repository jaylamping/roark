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
3 × 4.6 for 20 AWG at the elbow. The three signal pairs go in another, 2.2 × 8 together or 2.2 × 3.4 each. A twisted pair is
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
to a round bundle and doesn't apply there. Free sections are from `cad/_wip/organic-arm/cad/passages.py` (neck slices) and
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
