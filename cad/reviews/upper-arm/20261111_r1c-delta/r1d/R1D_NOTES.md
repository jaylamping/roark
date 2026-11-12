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

## Solver set in-process (2026-11-12 08:23)

What did work is a plain-text SolidWorks Basic macro (.swb), written by p3_fea (FEA_SOLVER_MACRO=1) and run inside our own
instance with RunMacro2:
- Solver 0 before, set with no error, 7 after. SolidWorks maps direct sparse (1) to its Intel direct sparse (7) here.
- The study was saved with that setting: `RING_G01_STOP0_DS` in `cad/_sim/r1d8_ring_saved/UA_HUBSEAT_r1d_ringg01p_ds.SLDPRT`
  (ring 0.1 gap STOP_0, 0.8 mm, 796,472 nodes, pads E 0.5).
- It is solved as saved by `r1d_ring_ds_solve.sh saved` (FEA_EXISTING_STUDY), with the memory stop.
- The earlier option c) 0.8 mm runs may have had pads at E 0.05: r1d_ring_c.sh didn't export HS_PAD_E. Both stalled, so no
  reported number depends on them.

## Ring STOP_0, Intel direct sparse: error 24 (2026-11-12 08:28)

- Solver confirmed in the BMC file: Intel Direct Sparse, 2,369,988 equations, 796,472 nodes, 14 contacts. SolidWorks deleted the
  .OUT on failure.
- It failed with error 24 after 143 s. The benchmark log stops at "GLOBAL-STIFFNESS-MATRIX-DECOMPOSITION-Start", which points to a
  singular (unstable) model.
- Likely cause: the two steel bolts, held only by no-penetration contact in clearance and with no preload. The pads stabilise
  the arm only. This is not proven.
- Memory: our processes peaked at 10.9 GB as factorisation began.

## Ring STOP_0 error 24: diagnosis (2026-11-12 08:45)

- Diff against the converged tapered STOP_0: the bodies, materials (pads E 0.5), fixture, load and lug contact set are the same.
  The seat contact set has fewer, larger faces (full-ring revolve).
- All four pads touch the hub (Y 296.0) in both models.
- The bolts fill their arm bores line-to-line and are bonded there by the global bond. Only the bolt-to-hub-lug faces are in
  contact. They are not free.
- Re-run with the .OUT captured: factorisation started at 69 s, and by 80 s free RAM had dropped from 26.5 to 12.0 GB (31.9 GB
  machine). The memory stop ended it cleanly. No singularity message.
- Conclusion: error 24 was the Intel direct sparse factorisation of 2.37 M equations running out of memory. Next: a coarser
  global mesh (HS_GLOBAL_EL) with the 0.8 mm seat control kept.

## Ring 0.1 gap STOP_0: repeat with the post/lug control (2026-11-12 09:27); queue stopped

- Run: r1d9_ringg01_stop_pm. Intel direct sparse, set by macro; the benchmark log shows Intel-solver lines only. 390,951 nodes:
  0.8 mm on the seat and on the lug/post/fin faces (Y 268-297.5), 4.0 mm global. Solve 414 s.
- Post-processor fix (hub_r1c.py): the -X bolt is nodes 557-4677, at the START of the node order. The index split counted it as
  arm, so the "arm hub posts" peak in both ring runs was a steel bolt node. Both runs have been re-post-processed; the review
  files here are the corrected ones.
- The joint regions repeat within a few percent of the first run.
- Arm ridge root / bore wall at θ 18, Y 302.0 (the inner corner of the end face against the hub disc):
  - vm 1.22 / 2.33 / 6.72 and shear 1.24 / 2.42 / 6.35 at 0.5 / 1 / 2 mm, with 9 and 8 nodes at 0.5 mm.
  - It halves from 0.5 to 1 mm and is gone by 2 mm: a contact-corner concentration, not a section.
- Posts, corrected (bolt excluded), fine mesh: vm 1.02 / 1.18 / 1.70, layer 0.63 / 0.71 / 1.18, shear 0.93 / 1.48 / 1.73
  (2 / 12 / 42 nodes).
  - The peak is at [147.1, 293.5, 11.1]: the front-half -X post, at the mouth of the bolt bore (r 1.55 from the bolt axis) on
    the face the hub lug bears on.
  - In the model the steel bolt is bonded along the whole bore. In the part, that face is the seam face where the brass insert
    sits.
  - σz within 1 / 2 / 3 mm of the peak: +34 / +18 / +5 MPa (tension).
- Lug forces: -X axial 55 N (sanity flag over 50 N), shear Fx 40 N, Fz 169 N; +X 2 / 0 / -112 N. The Fz pair is the stop
  moment about the hub axis. The full-ring ridge and groove cannot carry torque about that axis (frictionless), so the lugs carry
  all of it.
- Stop lug (stop_post.py, 2 mm pad exclusion): lug root 1.99 / 1.61, elsewhere 2.14 / 1.34. Matches the record.

## Post-processor body split rewritten, with a guard (2026-11-12 09:45)

The old split (hub_r1c.py since 2026-11-11) cut the node list into arm / hub / bolts by index ranges. The solver lists each body's
SURFACE nodes before its interior nodes, which broke it in two ways:
- The -X bolt (nodes 0-4705: surface first, then interior) was counted as arm. The ring runs' "arm hub posts" peaks, layer
  76.6 MPa at the bolt-bore mouth, were bolt surface nodes at r 1.500.
- About 15,500 hub surface nodes, between the last arm node and the hub's first interior node, were counted as arm. That shifted
  the arm ridge, seat and flank figures in every r1c/r1d result since 2026-11-11.

New split:
- Each node gets a certain geometric label where it can: inside a bolt shank or head, inside an insert sleeve, inside a pad,
  inside the hub mesh by more than 0.2, or outside it by more than 0.2.
- Unsure (interface) nodes between two certain blocks of different bodies get one cut point, placed where the fewest nodes land
  in a body they can't geometrically belong to.
- GUARD: the run stops (SystemExit) if any arm or hub node lies inside another body: the hub/arm mesh by more than 0.15 (the STL
  facets cut curved faces by up to about 0.1), or a bolt / insert / pad by more than 0.05.
- The run list is printed, e.g. "steel 0-4705, pad 4706-5280, arm 5281-192539, pad 192540-192728, hub 192729-386238,
  steel 386239-390950".

Re-post-processed with the new split (files here replaced; the tapered one is `r1d7_tg01p_stop.post_resplit.txt`):
- Tapered 0.1 gap STOP_0 still fails at the ridge end, θ 143: arm vm 0.64, shear 0.71; hub flank shear 0.67. So the move to the
  ring stands.
- Ring STOP_0 (repeat, post/lug control): arm hub posts pass, 1.94 / 1.61 / 1.38 at 0.5 mm. Joint regions change by a few
  percent (in the notes and the report).
- A layer average of "-" in the tables means no tensile average anywhere (all compression). It used to print as 0.00.

## Slot edge break for the shoulder thread's lug-root fillet (2026-11-12, prepared, not solved, not released)

The shoulder thread adds R1.2 at the hub lug roots (lug Z faces at CZ ± 5 meeting the spigot underside at Y 296). Our slot walls
(the posts' lug-facing faces at CZ ± 5.1) run up to the floor at Y 295.7, so their top edges must be broken.
`slot_edge_break.py` (section study plus the printed halves and rev D meshes), `slot_edge_break.json`:
- Lug-bearing face per post: 48.4 mm² (front, with the Ø4.0 insert hole) and 51.8 mm² (back, Ø3.4 hole), contact Y 288.0-295.7.
- Clearance to the fillet, ligament on the face above the insert mouth (Ø4.0 hole top at Y 294.0), and face area removed:
  - 1.4 × 45° chamfer: 0.43 mm clearance, 0.3 mm ligament (back hole 0.6), 7.2 mm² removed (14-15 %).
  - 1.4 round: 0.18 mm clearance, under the 0.2 target.
  - 1.2 (down the face) × 1.6 (across the post top) chamfer: 0.28 mm clearance, 0.5 mm ligament (back 0.8), 6.2 mm²
    removed (13 %), 37° from vertical as printed. Preferred.
  - 1.1 × 1.5: 0.22 mm clearance, 0.6 mm ligament, 5.7 mm² removed.
  - 1.0 × anything: 0.14 mm clearance, too little. The face leg (a) sets the clearance; b only sets the print angle.
- Fins top out at Y 291.4, 2.9 below the break. No ridge, rib, end face, bore or outside surface is touched.
- Print: the post's lug face is a ceiling over the slot when the halves print seam face down, and it already prints on support. A
  chamfer steeper than 45° from vertical self-supports along its slope. A round's lower part runs toward horizontal and leans on
  the ceiling's support, and it under-clears anyway. So: chamfer.
- Prepared in code as `ARM_SLOT_BREAK="a,b"` (organic_parts.r1d_slot_break: the printed halves, and the FEA hub-seat posts),
  along each lug's X span + 0.5. Off unless set.

## Memory cap on every python job (2026-11-12, coordinator rule)

At 09:47 the first version of slot_edge_break.py (a point-in-mesh test over the whole half meshes) reached 61 GB committed and
took holly-pc to 3 GB free; Remote Control showed the machine offline at 15:47Z. It was stopped at about 09:53. The memory watch
had already ended my M solve's instance cleanly at 09:51. No other thread's SolidWorks instance crashed: the application log's
SolidWorks faults today are all my own instances, see below.
- `cad/scripts/fea/r1c/capped.py`: `python capped.py --mb 6144 -- python script.py ...`. It starts the job suspended, puts it in a
  Windows job object with a 6 GB per-process and per-job committed-memory limit and kill-on-close, then resumes it. Over the
  limit, allocations fail (MemoryError, non-zero exit) and it prints "CAPPED: ...".
  - Tested: a 4 GB array under a 1 GB cap fails cleanly; gradual growth stops at 785 of 800 MB with the CAPPED line.
- Used for all post-processing, geometry checks and slicing in the chain scripts (hub_r1c, organic_print + Bambu, print_check,
  close_path).
- Not for the SolidWorks clients: they launch SLDWORKS.exe, which would land in the same job under the same cap and be killed
  when the client exits. The solve memory watch (12 GB used / 4 GB free) covers those.
- Mesh work uses plane sections or 20k-point chunks, never whole-mesh point-in-mesh tests.

## SolidWorks application-error events at the solver-option readback (2026-11-12)

Every run of mine that touched StaticStudyOptions from python logged one SLDWORKS.exe access violation in the Application log:
- the SolverType probe puts (07:53-08:01), and the post-macro readback (08:22, 08:26, 08:38, 08:53, 09:14, 09:50, 09:56);
- each at the moment the call raised "The server threw an exception";
- the instance carried on and closed cleanly each time.
The post-macro readback is now removed. The macro's own log and the benchmark log are the record of the solver.

## M (as-built insert and bolt), first solve r1d10: INVALID (2026-11-12 10:44)

- Intel direct sparse ran 99 contact iterations. Then the solver raised a hidden prompt: "Excessive displacements detected …
  Yes = restart with Large Displacement, No = finish, Cancel = stop". I answered No in our own instance, so it finished and closed
  cleanly.
- Maximum displacement 5.38e6 mm at node 2, the +X brass insert's inner end. The insert came loose: the global bond did not hold
  it (its faces also sat in the lug no-penetration set).
- The result files are kept only as `r1d10_ringg01i_stop.INVALID_rigid_body_escape.*`. None of its stresses mean anything.
- Fix: explicit bonded contact sets (type 1) for insert outside ↔ arm insert hole and bolt shank ↔ insert bore. Only the insert's
  mouth face stays in the lug no-penetration set. pre() now prints every contact set's type.
  - CreateContactSet takes swsContactSetTypeStaticNonLinear_e: 0 = no penetration, 1 = bonded. So all earlier "type 0" sets
    were no-penetration, as intended. "Error 24" is swsRunAnalysisErrorAnalysisFailed, a generic failure.

## Shoulder hub bc16e97 (rev D candidate with R1.2 Z-face lug-root fillets): checks (2026-11-12 10:55)

- Fetched from claude/project-thread-90ef87 at bc16e97 (Git LFS). STL SHA-256 18db5676…f261e matches the coordinator's note.
  Volume 61,624.9 mm³ against 61,615.6 for 556cc44 (+9.3 mm³, about four R1.2 fillets 8 mm long).
- Sections (fixed axes, fillet_check.py): the only differences from 556cc44 are at X 140.5-148.5 and 192.5-200.5,
  Y 295.0-296.0. That is 0.619 mm² per X section = two R1.2 fillet sections (2 × 0.309). Only the lug roots changed.
- Our slot against the fillet:
  - The fillet spans X 140.25-148.5 and 192.5-200.75. The break spans planned earlier (142.5-152.25 / 188.75-198.5, taken from
    the lug-post contact) missed 2 mm at one end of each fillet and would have left corners 0.16 mm inside it. They are corrected
    to 139.75-149.0 and 192.0-201.25 (fillet ± 0.5), all on the posts.
  - With the 1.2 × 1.6 chamfer on those spans, the minimum clearance to the fillet is: -X front 0.292, +X front 0.285,
    -X back 0.451, +X back 0.451. Run-out ends 0.55-0.58. All above 0.2. (`slot_break_vs_bc16e97.json`)
  - Outside the fillet the front lug face sits 0.014 proud of |Z| 5.0, so the slot gap there is 0.086 instead of 0.1. Same on
    556cc44 (`slot_unbroken_vs_556cc44.json`): not new.
- M re-run (r1d10b) with explicit bonded sets: both bonds formed (2 + 2 faces, type 1); the four other sets read back as type 0.

## M confirmed: ring 0.1 gap STOP_0 with the lug bolt joint as built (r1d10b, 2026-11-12 10:59)

- Intel direct sparse, 387,144 nodes, solve 412 s; max displacement 1.34 mm, stable. Bodies by the new split: brass 0-2785,
  hub, pads, steel × 2, arm. Guard OK.
- Worst average SF at 0.5 mm (vm / layer / interlayer shear):
  - arm hub posts: 1.98 / 2.47 / 2.40, the lowest at the -X front post by the insert mouth, [143.3, 293.0, 11.1].
  - fins: 2.93 / 2.94 / 2.30.
  - arm ridge load flank: 3.65 / 4.58 / 2.70; ridge body: 3.65 / 4.06 / 2.70.
  - arm ridge root, end-face corner θ 18: vm 1.37 / 2.28 / 6.35 at 0.5 / 1 / 2 mm (7 nodes); θ 338 shear 1.34 / 2.33 / 5.99.
  - hub load flank: 2.49 / 1.70 / 1.53.
  - hub groove bottom + 45° flank: 2.31 / 1.22 / 1.26.
  - spigot ring above the groove: 2.82 / 1.53 / 1.62; spigot core: 2.69 / 1.22 / 1.91.
  - outer ring and θ 0/180: 3.90 / 1.90 / 3.56.
  - hub lug roots: 2.22 / 1.23 / 1.33, layer at [144.6, 295.7, 11.0] (-X lug, +Z face, Y 296: the root the shoulder thread
    fillets).
- Inserts 58 MPa (SF 4.1 against 240 MPa brass); bolts 59 MPa (SF 10.9).
- Lug forces: -X axial 34 N, Fx 38 N, Fz 174 N; +X 3 / 0 / -115 N.
- Pads 3.4 N in total. Sanity OK.
- So the as-built joint changes nothing material: the posts pass, and the joint and the 1.2-1.3 hub across-layer values hold.

## Combined pass: FEA hub (2026-11-12 11:05)

- HUB_RING_ZF = our ring FEA hub plus the shoulder thread's R1.2 Z-root fillet, with their exact edge selection (Y 296,
  |Z - CZ| 5, r 18-31.5 from the hub axis): 8 edge segments.
- Check against our unfilleted hub (`hub_zf_vs_ring.json`): Y sections differ only at Y 295.0-295.75, the fillet. The X-section
  differences of about 1 mm² across the middle come from STL export resolution (the new hub was exported finer).
- Clearance from the 1.2 × 1.6 break to this fillet: 0.286 / 0.292 front, 0.446 / 0.452 back, the same as to bc16e97.
- Against bc16e97 itself (`hub_zf_vs_bc16e97.json`):
  - the joint zone matches (Y 295.5-300 section areas within 0.1 %);
  - above Y 300.5 rev D differs: slightly larger outer radius from Y 302.5, and a much smaller top boss (r about 24 at Y 319,
    ours 38.7).
  - So our fixture face at the hub top (Y 319.86) is larger than rev D's. Joint and lug-root figures are representative. The
    hub's upper-region figures (outer ring above the groove) are this approximation, so the shoulder thread's own FEA governs
    there.

## End-face inner edge: decision (2026-11-12, coordinator) and bearing

Decision: keep the existing 0.5 × 45° chamfer. No geometry change.
- The chamfer clears the rev D spigot-foot fillet by 0.248 (bc16e97 sections: the disc's flat face starts at r 36.02-36.04).
  The end face (r 36.4-37.6) seats flat on the Y 302 datum.
- The face is only 1.2 mm wide; a round would cost a quarter of it.
- The G90 corner value is compressive, at a contact edge: shear 0.81 / 1.88 / 6.55 at 0.5 / 1 / 2 mm, on 9 nodes. A real PETG
  edge beds in locally there.
- It is recorded in the results as a contact-edge value below target at 0.5 mm.
- An ARM_END_ROUND option (R0.8 tangent round) was prepared and is NOT used (default 0).

End-face bearing on the hub disc (σy, both sides of the contact; face band r 36.45-37.55; PETG 45 MPa;
`endface_pressure_r1d11.json`):

| Case | Mean compression | Peak in the face | Worst 0.5 mm average | Worst 1 mm average | Inner-edge node |
| --- | --- | --- | --- | --- | --- |
| 0.1 gap STOP_0 | 0.41 MPa | 32.7 MPa (SF 1.38), θ 18 | 9.3 MPa (SF 4.8) | 4.8 MPa (SF 9.3) | 62 MPa |
| 0.1 gap G90 | 0.99 MPa | 18.6 MPa (SF 2.42), θ 310 | 5.8 MPa (SF 7.7) | 4.4 MPa (SF 10.3) | 53 MPa |

The bench notes' split-and-inspect step now looks at that edge and the hub disc for crushing or whitening.

## Crush ribs: decision C (2026-11-12, coordinator), bedding, play, fit coupon

- Decision: no rib change now. The ribs are take-up features, not the strength path. In nominal STOP_0 and G90 (cases 3 and 4)
  the ribs, 0.1 proud and touching, carry the flank load as point contacts (arm shear 0.36 / 0.43 at 0.5 mm). That is rib
  bedding, expected, and not a strength failure. As assembled, the ribs are already crushed 0.15 and sitting at yield; under
  load they flatten until the flank bears.
- The strength claim rests on the flank bearing across the print's gap band. Done: 0.1 gap STOP_0 and G90. Queued: 0.2 gap
  STOP_0 and G90; 0 gap (flank in contact, no ribs) G90 and STOP_0.
- Hub flank marking risk: the hub shows shear 0.70 (stop) and 0.83 (G90) at 0.5 mm, locally, under a rib. Flagged for the
  shoulder thread and the reviewer.
- Rib flattening load:
  - A rib's flank face is 0.8 mm radial (0.92 mm along the 30° flank) × 1.0 mm, so about 0.9 mm² once fully engaged. At PETG
    45-55 MPa that holds about 41-51 N before it flattens further.
  - Crown-rib load in G90: the 22.9 N·m moment over a couple of about 70 mm puts about 330 N on the lift-off side, shared by 3-4
    ribs 30° apart: 80-110 N axial, 95-130 N normal to the flank, plus about 5 N from the 62 N axial.
  - So the crown ribs bed in under routine G90, within the first few cycles, not only on a hard stop. The FEA agrees: the rib
    averages are already past yield.
- Play once bedded in (flank gap g, set normal to the 30° flank):
  - axial play = g / cos 30: 0.115 mm (g 0.1), 0.231 mm (g 0.2);
  - rocking about the end-face rim against the opposite flank (about 72 mm apart): 1.6 mrad (0.09°) / 3.2 mrad (0.18°);
  - at the wrist, about 410 mm out: 0.66 / 1.31 mm sideways and 0.12 / 0.23 mm along the arm, plus up to ±0.1 mm from the
    0.1 radial bore clearance.
  - G90 loads the joint one way, so the play shows only when the load reverses (the arm pushed up, or decelerating).
- R2 options:
  - (B) the 0.1 gap with short, wide ribs that crush flush on assembly (about 0.12-0.15 printed, about 3 mm of arc each, or 24
    ribs), so the flank is the load path from the start;
  - (A) the flank line-to-line as printed, with little or no rib.
- Fit coupon: the hub end of the final halves, cut flat at a Y plane, sliced with the halves' pipeline (same orientation,
  settings, zones and crown blocker; no settings difference to the seed).
  Trial cuts on the pre-break ring halves:
  - Y ≥ 266, keeping the seam posts and screws: back 1 h 43 / 34.7 g, front 1 h 32 / 29.0 g. Total about 3 h 15, 64 g.
  - Y ≥ 284, the seat, ridge, ribs, end face, floor, slot breaks and the four hub posts with their insert and clearance holes;
    closes on the two lug bolts: back 1 h 10 / 17.4 g, front 1 h 04 / 16.2 g. Total about 2 h 14, 34 g.
  - Without the 100 % hub band the times barely change (Y 284: 70 + 64 min). Time is set by the geometry: a 39 mm tall
    half-ring of walls with the crown on support.
  - Under 45 min would need cutting the ring into a sector, which loses the closing behaviour the coupon exists to test.

## R2 rib option, sized on paper only (2026-11-12; no build, no solve)

- G90 flank load, any pose: the lift-off side can be at any θ, so size for the peak of a cosine distribution all round.
  - Peak line load at the flank's mean radius 35.35: q = 22.9e3 / (π · 35.35²) + 62 / (2π · 35.35) = 5.83 + 0.28 = 6.1 N/mm
    axial, or 7.1 N/mm normal to the 30° flank.
  - At 12 ribs (30°, 18.5 mm of arc each) a rib takes about 131 N normal. At 24 ribs, about 65 N.
- Ribs that carry that at 1.5 with no further yield (45 MPa):
  - 4.4 mm² per rib at 12 ribs, i.e. about 4.8 mm of arc on the 0.92 mm flank face; or 2.2 mm² (2.4 mm arc) at 24 ribs.
  - Either way, 26 % of the flank ring is rib face, about 53 mm² in all.
- Closing force to crush them 0.15:
  - plastic flow at about 45-55 MPa over 53 mm² is about 2.6 kN normal to the flank;
  - through the 30° wedge (closing force about 0.76 × normal at the crown) that is about 2 kN of closing force.
  - Two lug bolts and two seam screws at 0.5 N·m give at most about 0.8 kN each in theory (F = T / (0.2 d)), less in PETG
    inserts, and 2 kN would bend the halves. **Ribs strong enough to carry G90 cannot also be crush-fitted.** Load-carrying and
    take-up conflict, so ribs stay take-up only.
  - Today's 12 ribs (about 0.92 mm² each) crush at about 46 N normal each, about 35 N of closing per crown rib: easy for the
    screws.
- Near-seam ribs (θ 15, 165, 195, 345, and partly 45 / 135):
  - The halves close along Z, which is almost tangent to the ring at θ 15 / 165. Those ribs are not pressed into the flank;
    they are dragged sideways across it through the 0.15 interference, over the last few mm of travel.
  - Physically they shave: the rib is planed toward flush, leaving a smear or burr, and may score the hub flank. They give
    little lasting take-up.
  - Ribs near the crown (θ 75 / 105) approach radially and crush by wedge action (0.3 radial travel for 0.15 normal).
  - That matches the closing-path check: contact up to 0.18 at every rib angle, deepest near the crown, sliding near the seam.
- Simpler alternatives:
  - **Wedge seat, seam relieved at the hub end.** Make the flank line-to-line as printed, and relieve the seam faces 0.15 over
    the hub end only, so tightening the lug bolts pulls the halves together and the conical flank wedges the ridge axially into
    the groove: a preloaded, play-free seat whatever the print tolerance. Catch: the hub-end seam stays visibly 0.1-0.2 open,
    the halves bend slightly there (PETG creep relaxes the preload over time), and the seam faces carry nothing at the hub end.
  - **Tapered gap around θ.** Flank gap 0 at the crowns (θ 90 / 270, where closing is radial and wedges) growing to 0.2 at the
    seam (where closing would shave). Catch: for poses whose lift-off side is near the seam, the play is the full 0.2 (axial
    0.23).

### The wedge seat, thought through (coordinator question, notes only)

- Closing is along Z, so the wedge only preloads directly near the crowns (θ 90 / 270, radial approach). Near the seam
  (θ 0 / 180) the closing motion is tangential, so no wedge forms there.
- Rigid halves: the axial pull from the crown wedge moves the whole half's ridge in Y. A rigid half therefore seats near the
  seam too, and what remains there is only the local print deviation of the flank and the groove (about 0-0.1), not the design
  gap. Lift-off near the seam: about 0-0.1 normal (0-0.12 axial play).
- Flexible hub-end band: if the band twists between the crown and the seam, the seam region lags by that twist and keeps up to
  its printed gap. The band (collar, ridge and skin over Y 295.7-302) is stiff in that direction compared with 0.1 mm, so this
  should be closer to the rigid case. Not computed.
- Hoop compliance near the hub end does not help: the motion needed is axial, not radial. Relieving the seam so each half can
  tilt about X (rock in) lets the crown pull rotate the half instead of translating it, which would reduce the near-seam
  seating. Better to relieve the seam faces uniformly along the hub end (pure translation).
- Strength: the 0 gap solves (flank line-to-line, no ribs) are this design's bearing case, flank in contact all round. The
  wedge preload is not in them: it adds a steady axial compression on the flank and the end face, and tension in the lug bolts
  and the hub-end skin. To be checked with a preload step if the design is pursued.

## Free space around the hub lugs for a hub web (shoulder thread question, 2026-11-12)

Y-plane sections every 0.5 mm, Y 280-296, of our printed ring halves and the bc16e97 hub (`lug_envelope.py`,
`lug_envelope.json`). The slot edge break (Y 294.3-295.7 at the lug faces) is not in these halves; it only removes material.
- Lugs (bc16e97): r 18.8-29.8 from the hub axis, Y 288-296, |Z - CZ| ≤ 5.0.
- Inboard of the lugs: none of our material lies inside r 19.2 anywhere (all θ) for Y 280-296. The nearest is the inner edge of
  the four hub posts (Ø9 at X 147.5 / 193.5), which start at the lug faces (|Z - CZ| ≥ 5.1) and reach r 19.2 there.
  **Free with 0.5 clearance: r ≤ 18.7, all θ, Y 280-296.**
- Between each lug's outer end and our wall below Y 296, in the lug's own band (|Z - CZ| ≤ 4.6, i.e. 0.5 inside the post faces):
  our nearest material is the arm's inside wall at r 30.3 (Y 280), 33.4 (Y 288), 34.1 (Y 290), 34.8 (Y 292), 35.3 (Y 294),
  35.4 (Y 295). **Free with 0.5 clearance: r from the lug's outer end (29.8) to about 32.9 + 0.43 × (Y - 288), i.e. 32.9 at
  Y 288 up to 34.9 at Y 295.**
- In Z, the lug cannot grow: our posts sit 0.1 off its faces (|Z - CZ| ≥ 5.1) from r 19.2 outward over Y 285-295.7, with the
  fins below them (Y 276-291.4) and the 1.2 × 1.6 break at their top edges.
- Below the lugs (Y < 288), within |Z - CZ| ≤ 4.6: free down to Y 280 at least, for r ≤ about 29.8 (the inside wall is at r ≥ 30.3
  there).
- Through the middle: our parts put nothing inside r 19.2. The elbow RS02 cable and the harness trunk come up the neck and pass
  into the shoulder through the hub's centre. Their bundle size is not modelled here (it belongs to the electrical plan), so the
  hub web must leave the hub's own cable window clear.

## R1e (play-free joint): first numbers, before any new solve (2026-11-12)

Joey's decision: wait for a play-free joint. The gap-and-ribs fit is retired. The ring ridge, full-ring groove, fins, slot break,
end chamfer and as-built bolt joint stay; the hub interface is frozen.

### Wedge direction (confirmed)
- The 30° load flank is Y = 298.0 + (35.8 - r)·tan 30. On the arm, its normal points +Y and outward (0.866 Y, 0.5 r).
- A half closing inward at the crown is pushed +Y, onto the hub disc. So the end face stays the axial datum and is pulled onto
  the disc, as wanted.

### Seam-relief wedge: not feasible with these halves
- The halves close along Z, which is radial only at the crowns. Radial motion δr closes the flank by δr·sin 30 = 0.5 δr.
- Flank and groove each ±0.1 give ±0.2 along the flank normal, so each half's crown must move ±0.4 in Z to seat across the band.
  Hub-end seam relief would be at least 0.4 + 0.1 margin per half: a seam gap of 0.2 mm (loose extreme) up to 1.8 mm (tight
  extreme), 1.0 mm nominal.
- A half can move its hub end 0.4 only by:
  - rigid translation, which needs the whole seam relieved. That opens the elbow end too: the RS02 Ø40 stub bore goes oval by
    0.8-1.0, and the ring keys shift.
  - bending: the hub end (Y 296-302) is a half-tube about 30 mm from the nearest seam screws (Y 272). With E 2 GPa and I about
    1e5 mm⁴, F = 3EIδ / L³ ≈ 3 × 2000 × 1e5 × 0.4 / 27,000 ≈ 9 kN. The lug bolts and seam screws give at most about 0.8 kN each
    (0.5 N·m, F = T / (0.2 d)), and less in PETG.
- So the hub end cannot be pulled in by screws, and relieving the seam would only leave a visible gap.

### What can be play-free with the hub frozen
1. **Selective shim at the end face (recommended).** The axial play is a fixed stack: the ridge load flank to the end face
   (arm) against the groove flank to the disc underside (hub).
   - Lower the arm's end face by 0.4 (nominal), and fill the measured gap with a shim ring between the end face and the hub
     disc. The shim slides over the hub spigot from its free end before assembly, so a full ring works with no split.
   - Thickness picked from a set in 0.05 steps (0.20-0.60) after a feeler check on the closed assembly. Then both rigid stops
     touch: no play, no preload needed, so creep doesn't matter. Residual play is at most half a step (0.025), about 0.15 mm at
     the wrist.
   - Catch: one measure-and-pick step at assembly. A stock shim ring (DIN 988) is wider than the 1.2 mm end face (sizes near
     Ø72 × 82 overhang the r 38 skin), so either a custom ring (shim stock, laser-cut, or printed PETG in 0.05 steps, whose
     thickness accuracy needs checking) or a wider end face.
2. **Split clamp band (shaft-collar style).** Separate the inner collar band (the ridge, end face and hub posts, r 35.9-37.4)
   from the skin by slots, so the band halves can close 0.4 under the lug bolts while the skin seam stays closed; the band's own
   seam gap is hidden inside.
   - Catch: the band must flex 0.4 under about 1 kN yet carry the G90 / stop loads into the skin through its connections. That
     trade-off is hard in PETG, and it is a big redesign of the hub end.
3. **Spring bias (TPU ring in the end-face gap).** Biases the flank seated, so nothing rattles.
   - Catch: on the push side the joint is only as stiff as the TPU. Ring about 280 mm² × 1 mm at E 30 MPa gives a rocking
     stiffness of about 5.7e6 N·mm/rad, so G90 would rock about 4 mrad, 1.6 mm at the wrist: worse than the 0.66 mm of play.
     Not recommended.
