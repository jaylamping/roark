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
