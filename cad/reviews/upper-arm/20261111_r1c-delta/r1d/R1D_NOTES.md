# R1d: notes, restart instructions and the geometric argument (2026-11-12)

R1d is the arm revision that answers the R1c delta review (`../README.md`). Scripts: `cad/scripts/arm/organic_master.py`
(`ARM_R1D=1`), `organic_parts.py`, `cad/scripts/fea/hub_seat.py`, `cad/scripts/fea/r1c/*`. The hub is unchanged (rev C+);
R1d changes nothing on the hub.

## Geometry changes against R1c

All arm-side:
- **One axial datum:** the arm's end face bears on the hub disc at Y 302.
- **Floor and post tops at Y 295.7:** 0.3 below the spigot and its fill (they were line-to-line at Y 296 / 295.9).
- **Load flank 0.1 off** the groove's (`ARM_FLANK_GAP`, measured normal to the flank), with **12 crush ribs** on it:
  - 6 per arc at θ 45, 63, 81, 99, 117, 135 (+180);
  - 1 wide, over r 34.95-35.75;
  - `ARM_RIB_PROUD`: 0.25 to print (0.15 interference), 0.1 in the "nominal" FEA (touching), 0 in the gap cases.
- **Tip relieved to r 34.8** (0.5 off the groove bottom), with a 0.15 load-side chamfer. Top chamfer (34.8, 300.4) to
  (35.0, 300.8): at least 0.33 clear of the hub's R1.0 corner round.
- **Floor corner ring dropped.**
- **Collar foot:** a 45° chamfer into the arm's inside wall, replacing the 0.3 ledge.
- **FEA posts:** keep the printed 0.1 clearance to the lug faces.

## Geometric argument for the gap case (option D, supporting evidence)

With the flank gap, the arm can move away from the hub along −Y until something catches it:
- **The ridge:** the 30° flank closes after 0.1 / cos 30 = **0.115 mm** of axial travel (0.1 gap), or 0.231 mm (0.2 gap).
- **The bolts:** the lug holes are Ø3.4 on M3 bolts (Ø3.0), so a bolt only bears after **0.2 mm** of radial travel of the lug
  relative to the posts. At Ø3.6, the shoulder thread's option, that becomes 0.3 mm.
- **Nothing else:** the posts carry the lugs only in Z (0.1 clear), the floor is 0.3 clear, and the bore is 0.1 clear
  radially.

So with a 0.1 gap the ridge engages first (0.115 < 0.2). With a 0.2 gap the bolts engage first (0.231 > 0.2), so 0.2 is
past the limit. Tilting under the G90 moment changes this locally (points far from the tilt axis move more), which is why
the gap solves are still needed. The printed play limit follows: after crushing the ribs there must be **no measurable
axial play** (under 0.05). Anything that leaves a gap near 0.2 hands the joint back to the bolts (the R1 state: bolts 770
MPa, lug root layer SF 0.26).

## Mesh and solver notes

- The 0.35 mm mesh control first caught every face crossing the seat box (186-246 faces), giving 2.4 M nodes. It now takes
  only ridge and groove faces up to 150 mm², which gives 1.2-1.3 M nodes.
- With a flank gap the arm has no initial restraint along −Y, so the linear static solve fails (error 24).
  - Option A: soft springs (`HS_SOFT_SPRING=1`).
  - Option B: four soft bonded pads, if A fails.
  - In either case: report the spring force (applied minus fixture reaction, under 1% of the load), check the ridge is
    engaged, and check that the joint displacement is about the gap size.

## Restart elsewhere: commands (bash, repo root, forward-slash paths)

```bash
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
# one variant (tag gap rib): g01 0.1 0 | nom 0.1 0.1 | g02 0.2 0 | print 0.1 0.25 (print: jobs "master:upper parts:front parts:back")
export ARM_WIP_TAG=_g01 ARM_FLANK_GAP=0.1 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_g01.SLDPRT
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"
cp cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_g01.SLDPRT cad/_sim/ua2/
# hub-seat model; the grooved hub (rev C+ mirror: r 23 fill, R1.0 / R0.4 corners, lug-root R1.0) is built once with
# HS_GROOVE=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 (no HS_REUSE_HUB),
# then reused:
export HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_MODEL=UA_HUBSEAT_r1d_g01.SLDPRT
ARM_SW_DIR=J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-hub ARM_FEA_DIR=J:/code/roark-wt/left-arm-organic/cad/_sim/ua2 python cad/scripts/fea/hub_seat.py build
# solve (copy the model into its own folder; HS_SOFT_SPRING=1 for the gap cases):
HS_SEAT_MESH=0.35 ARM_SW_DIR=.../arm-sw-fea ARM_FEA_DIR=.../cad/_sim/<folder> python cad/scripts/fea/organic_fea.py HS_STOP_0_fine
python cad/scripts/fea/r1c/hub_r1c.py cad/_sim/<folder>/org16_HS_STOP_0_fine.npz cad/_sim/ua2/HUB_GROOVE_r1d.STL
```
The chains as run: `cad/scripts/fea/r1c/r1d_chain2.sh`, `r1d_chain3.sh`, `r1d_probe_then_soft.sh`.

Today's hub native part (the mirror's source) is now read from `cad/_wip/hub_ref/` (copied from the left-arm worktree,
SHA-256 pinned in `hub_seat.py`). The real rev C+ hub exports come from the shoulder branch at 6ee2b21 via `git show`,
into `cad/_wip/shoulder_hub_6ee2b21/`.

## WIP files at this point (SHA-256)

| File | SHA-256 |
| --- | --- |
| cad/_wip/r1d_g01/upper_arm_organic_master_left_r1d.SLDPRT | f3cbcd2bcc7588b8d9e511ae67d629d5d78b42a9dcc3ed7e067c1fb3772b916c |
| cad/_wip/r1d_nom/upper_arm_organic_master_left_r1d.SLDPRT | 78d334003a47429d665638e5c468fa73775e08fc33510e8f5071a3971a4883ab |
| cad/_wip/r1d_g02/upper_arm_organic_master_left_r1d.SLDPRT | 5be68e97ae99fbb805287ead2a2144cbb215268c54dfaff64477d831b7eead7b |
| cad/_wip/r1d_print/upper_arm_organic_master_left_r1d.SLDPRT | a73e9c3461497ee780f48c878a3f1532e94eeb89f77fdbfd9c785207ac4c46a3 |
| cad/_wip/r1d_print/exports/upper_arm_organic_front_left.STL | 4fb3537a4eba5a8720e72ec6c2ae614ca4c698b24a610a6c549af7e590ecfcc2 |
| cad/_wip/r1d_print/exports/upper_arm_organic_back_left.STL | 6229517fe7fa4b77e6d3951d461da53e3ad4845af4b2a36cd790cd0ab32ec090 |
| cad/_sim/ua2/UA_ORGANIC_BONDED_v32_g01.SLDPRT | 46eedcffbcdee2baab5ee791770aa3fc2b9a6e38b33eec1be21a8e090ea1c02d |
| cad/_sim/ua2/UA_ORGANIC_BONDED_v32_nom.SLDPRT | c61347db6f241bdf72fb4f406d3cdc048640c9fbd4ff3e9ad1517a2c3d97e4c6 |
| cad/_sim/ua2/UA_ORGANIC_BONDED_v32_g02.SLDPRT | 96ed2430d1e322c49a7f85c15f64a55ef2a589415d89b7e8732890f775b243ef |
| cad/_sim/ua2/UA_HUBSEAT_r1d_g01.SLDPRT | 585e976df380faccc029aa79b7c6da34c1c3092e24eca8468847a72e7d704e9c |
| cad/_sim/ua2/UA_HUBSEAT_r1d_nom.SLDPRT | 2f6e33e8002abc6cc2e14bb64e77c18dfe75b32e12934ea727a8db93c7121c8b |
| cad/_sim/ua2/UA_HUBSEAT_r1d_g02.SLDPRT | 0588467493dd78995eb34c4a5efb5e85f39c7c5e5a674b90b3eed20e084ca2eb |
| cad/_sim/ua2/HUB_GROOVE.SLDPRT (rev C+ mirror, r 23) | 140a953418a31228bdb3a73c2fa3192a424d4b4d68080c9c000f94e66b49fcbe |
| cad/_sim/ua2/HUB_GROOVE_r1d.STL | 88d90a918082efc5c9f843cf7d38b2e3944f2a313477b6c412f1af8cb5d2b820 |
| cad/_sim/ua2/HS_BOLTS.SLDPRT | 16853fdad35f77fcff1e7a9ce4340da1abe8247069a5fa04629511f086920823 |
| cad/_wip/hub_ref/upper_arm_hub_left.SLDPRT (today's hub) | 7b857f61855fb2a65fd4e6d73981605c4b9f12747af1e5abcfd2a75bc5ddcb0b |
| cad/_wip/shoulder_hub_6ee2b21/shoulder_hub_left.STL | 523eb9946660f90e92bf84c16c820bc1c9c4296ebbe1852d6a1f80397356d176 |
| cad/_wip/shoulder_hub_6ee2b21/shoulder_hub_left.STEP | 39f002b915ce916eb8ff256c39f99f4f1015a02a0972ccfe14087cd88802f690 |

## Checks already done on the R1d print geometry (`close_path_realhub.json`, `rs02_fit_r1d.json`)

Against the real rev C+ hub STL (fd0cef8 / 6ee2b21):
- Only the 12 ribs overlap the hub at the final position, by at most 0.154 (θ 45-135 and 225-315, Y 297.9-298.5).
- The closing path is clean apart from that rib crush in the last 0.06-0.11 mm.
- The RS02 fit is identical to R1 in all 72 values.

## Provisional R1d slice (WIP, not a release)

**Support blocker.** The halves were sliced with a support blocker over the whole ridge section (Y 297.6-301.9, r 34.0-36.05,
over each ridge arc ±2°), as part 4 of the 3MF, subtype support_blocker. Support points mapped back from the G-code to the
arm frame:

| Blocker | Points within 0.5 mm of the load flank (front / back) | Tip, top chamfer, 45° flank |
| --- | --- | --- |
| None (R1c, from the review) | 367 / 374, closest 0.10 / 0.16 | supported |
| Flank-only band | 246 / 380, closest 0.06 / 0.12 | supported |
| Whole ridge | 92 / 137, closest 0.41 / 0.39 | no support; nearest point 0.70 mm away |

With the whole-ridge blocker, the remaining points near the flank are the bore-ceiling support just below the ridge. Both
flanks are self-supporting. The 0.9-1.2 mm tip bridges between them, and it has 0.5 radial clearance to absorb droop.

**Slices.** Back 5 h 20 min, 122.5 g. Front 4 h 42 min, 107.6 g. No warnings; settings identical to the seed.

**Mesh gate.** Front PASS. Back FAIL: with the post tops at Y 295.7, only 0.45-0.48 mm of skin was left over the back posts'
Ø6.5 bolt-head counterbores (their tops are at Y 295.25). Fix: the R1d counterbore is Ø6.0, which leaves 0.7 mm. Use a
DIN 912 socket head (Ø5.5); a Ø5.7 button head is tight. This needs a rebuild of the print halves, so SolidWorks.

## Release basis if the gap solves are not available (option D)

The tapered R1d baseline (5-segment ramps, about 1.2 mm faces) meshes in 39 s, 0.93 M nodes at 0.5 mm on the ridge and groove.

1. **Geometry: the ridge takes the tie before the bolts.**
   - The 0.1 flank gap closes after 0.115 mm of axial travel.
   - The lug bolts only bear after 0.2 mm, because the lug holes are Ø3.4 on M3. At Ø3.6, the shoulder thread's option, that
     becomes 0.3 mm.
   - Nothing else restrains the arm along −Y: the floor is 0.3 clear, and the posts are 0.1 clear of the lugs.
   - So, from the first loading, the joint behaves like the nominal model (flank seated) plus a 0.115 mm rigid shift.
2. **Strength: the nominal solves.** These are the crush ribs seated on the flank: tapered geometry, real lug-hole
   clearance, posts 0.1 clear. They cover STOP_0, G90 and STOP_124, with worst averages and interlayer shear.
3. **Bench limit carries the rest.** After assembly there must be no measurable axial play (under 0.05 mm). Play means
   the ribs did not seat, the gap is open, and the load could reach the bolts first. In that case: do not proof-load, report.
   - Staged proof to 515 N, with split-and-inspect after.
   - What it does not cover: how the gap closes under the G90 tilt. Points far from the tilt axis move more than the
     0.115 mm average, so a lug could touch its bolt before the whole flank seats. The 0.1 gap solve was meant to settle that.

## Solver choice through the API (2026-11-12 08:05)

The ring 0.1 gap STOP_0 runs (0.5 and 0.8 mm) stall at contact iteration 7 with the iterative solver: the .OUT shows ISOL 2
for both. Switching to direct sparse through the API failed:
- The Simulation enum (cosworks.tlb) is swsSolverType_e: Automatic 0, DirectSparse 1, FFEPlus 2, Intel (large-problem
  direct sparse) 7. Studies read back 0 (Automatic), and Automatic picked the iterative solver.
- Writing ICWStaticStudyOptions.SolverType fails for every value, 0 included (that is, rewriting the current value). It fails
  through late binding ("can not be set" / "server threw an exception") and through the typed cosworks wrapper. The soft-spring
  setting on the same object failed the same way earlier. So puts on StaticStudyOptions don't work in this out-of-process
  flow.
- No Simulation solver default is stored under HKCU\Software\SolidWorks\SOLIDWORKS 2026\Simulation (only SolverOffload).
- Probe: cad/scripts/fea/r1c/r1d_solver_probe.sh, mesh-only at 0.8 mm (796,472 nodes, 35 s per mesh), every instance ended
  cleanly.

## Ring print geometry, provisional (WIP only, 2026-11-12 08:18; not released)

Built from the ring variant (full-semicircle ridge per half, 0.1 flank gap, crush ribs 0.25 proud at θ 15/45/75/105/135/165 and
+180), exported, and sliced with the support blocker at the ridge crown. Files are in `cad/_wip/r1d_ring_print/`, hashes in
`ring_print/SHA256SUMS_wip.txt`.
- Mesh gate and slice: back PASS, 5 h 26 min, 123.7 g; front PASS, 4 h 45 min, 107.9 g.
- Closing path against shoulder hub rev D (556cc44 STL):
  - The final overlap is at the crush ribs only: max 0.154 mm (front) and 0.150 mm (back), at r 34.83-35.69, Y 297.9-298.5 and
    exactly the 12 rib angles. That is the ribs' 0.25 proud minus the 0.1 gap, so it is the intended crush.
  - Path contacts while closing: 30 per half, again at the rib angles, ≤0.18 mm.
  - The halves' own sweep has no path collisions. The RS02 ring contacts are its designed seat.
- Not a release: the ring STOP_0 FEA is still open (solver), and the print files are not in `prints/`.
