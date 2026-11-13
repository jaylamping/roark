# Second review of the packet (pin 06b3e5fb): findings and responses (2026-11-13)

**Verdict.** The coupon, hub and shims may print; the halves wait.

Each point was checked against the files. "Confirmed" means the reviewer is right. Where the reviewer is wrong or only partly
right, that is said.

## A. Post-processing and text

### 1. The STOP_0 bolt path

**Confirmed, and wider than STOP_0.**
- **The old script was wrong.** `fx_path.py` averaged |x| over all shank nodes, interior included, so it printed a 0.8 "gap".
- **The fix.** It now uses surface nodes only (hole wall r 1.7, shank r 1.5), per direction (every 30 deg) and per 2 mm Z band
  inside the lug, and reads the deformed gap along each direction.
- **The true gap:** an M3 shank in the Dia 3.4 hole is 0.20 radial. The mesh reads 0.18-0.20.
- **The contact set exists.** The lug contact set (type 0, no penetration) pairs the hub's lug-zone faces, the hole wall
  included, with the arm faces and every bolt face. There is no friction and no preload.
- **Closure per case** (smallest gap left; files `r1g4_<case>.fx_path.txt`):

| Case | -X lug | +X lug |
| --- | --- | --- |
| STOP_0 | 0.186, **in contact** (-0.006) | 0.071 (0.109 left) |
| STOP_124 | 0.049 (0.145) | 0.200, **in contact** (-0.010) |
| YAW -17 | 0.133 (0.052) | 0.025 (0.161) |
| YAW +17 | 0.022 (0.155) | 0.116 (0.062) |
| G90 | 0.144 (0.046) | 0.051 (0.136) |
| G90 + YAW -17 | 0.202, **in contact** (-0.002) | 0.075 (0.115) |

- **The reviewer's figures.** The reviewer's 0.182 closure is right. The margin is not 0.02: in three cases the gap is fully closed
  and the shank bears on the hole. In STOP_0 that is 32-43 N sideways on the -X lug (`r1g4_stop0.fx_path.txt` and the lug loads).
- **Why the lug drifts.** Between frictionless, unclamped plates, nothing holds the lug sideways except its bolt and its outer
  face (0.20 from our pocket wall). The real joint is clamped (0.3 N·m), and its friction is about 200-300 N; it is not counted on.
- **Hole size for a 0.15 mm margin.** The free drift beyond 0.20 is unknown, because contact stops it there; the largest measured
  is 0.202. Dia 3.7 (0.35 radial) gives 0.15 only if the free drift is 0.20. **Dia 3.8 (0.40 radial)** gives about 0.20, with room
  if the drift runs on to the outer face (0.20 in X).
- **Running:** r1g5 = r1g4 with the hub lug holes Dia 3.8 in our FEA hub, for STOP_0, STOP_124 and G90 + YAW -17.

### 2. Missing rows

**Confirmed.**
- **YAW +17 arm end-face corner** (theta 296, X 186.7, Y 302.0, Z -26.6, r 36.4): shear 0.96 / 1.90 / 4.47, vm 1.44, 9 / 26 / 108
  nodes.
  - It is the lumped-shim end-face corner: the inner edge of our end face, with the shim merged in, bearing on the hub disc.
  - The R1g and r1g2 packets listed it (0.98 / 1.89, 0.96 / 2.06). I left it out of the r1g4 table by mistake.
  - Tensor-averaged at the corner: shear 1.05, p1 -7.4, p3 -34.6 MPa, which is compressive bearing.
  - Off the edge, 0.5 mm into the arm (-Y): shear 4.18, vm 3.64. At 1.0 mm: 16.3 / 7.62 (`r1g4_yawp_endface_corner_probe.txt`).
    So it is a contact-edge concentration.
  - It is now in the table and among the known items.
- **The hub layer rows**, 1.37-1.48 at 0.5 mm in the yaw cases: confirmed in the reports and added. They are in the hub, which
  the shoulder thread's FE governs.
- **STOP_0 "lowest":** confirmed. The -X fin reads shear 3.29 / 3.70 / 4.14 (region report), below the post's 3.63. Corrected.
- **The corner probe, like for like:** confirmed. The tensor average at the same centre is 1.44, so stepping in raises it from
  1.44 to 1.77 (0.5 mm) and 2.04 (1.0 mm). The packet now says so. The table's 1.02 is the spot report's average of nodal
  magnitudes.

### 3. packet_numbers_check.py

**Confirmed and rebuilt.**
- **Per-case check:** every table number must appear in that case's own reports (`r1g4_<case>.*.txt`), not in any of 182 files.
- **Completeness check:** every region of that case's spot and region reports whose 0.5 mm SF is under its target (1.2 for the
  stops, 1.5 otherwise) must be in the row. The only exceptions are regions that repeat a listed one, each named with its reason
  in the script.
- **Proof that it works:** run on the first r1g4 table, it failed with the same omissions as the reviewer's (10 failures). The
  table now passes (`packet_numbers_check.txt`).

### 4. Stale bench text

**Confirmed.** BENCH 2b is rewritten:
- The title is R1g.
- The hub is "the final hub only (the shoulder thread's frozen release)".
- The plates are four of each per print (two full sets).

### 5. Mesh

**Confirmed.**
- **Packet note:** the packet now says that the 0.5 mm values are near-nodal at the 0.8 face size (4-9 nodes in the sphere) and
  that no convergence run exists.
- **Local refinement of the plate and end-face corners:** it does not fit within the 12 GB "used" solve stop. The model is about
  391 k nodes, and G90 + YAW -17 already peaked at 11.9 GB.
- **What it would take:** raising that stop to about 14-15 GB with the free-memory stop kept at 2 GB (the machine has about
  22 GB free now). That is your call.
- **Not queued.**

## B. Solves

- **G90 + YAW +17 on r1g4:** see the message and `r1g4_g90y.*`.
- **r1g5 (hub lug holes Dia 3.8):** STOP_0, STOP_124 and G90 + YAW -17, queued after it.

## C. Bench 2b (BENCH_TESTS.md)

6. **Stop-equivalent load:**
   - **What it reproduces:** STOP_0 puts 176 N on the -X lug's front plate (centre X offset 30.6, Y 291.7), 43 N sideways toward
     -X through its bolt, and 75 N on the +X lug's back plate (`lug_loads.py` on `r1g4_stop0`).
   - **On the coupon:** the yaw lever pulled toward the front side at 8.7 kg gives 245 N on that plate, which covers 176 N by 1.4.
     At the same time, 4.5 kg (44 N) hangs from a cord at the -X lug line, pulling -X. Then the mirror.
   - The imprint inspection is moved after all the loads (step 10).
7. **Yaw lever:** `prints/upper-arm/upper_arm_organic_coupon_yaw_lever.3mf/.gcode` (106 min / 72 g; script `yaw_lever_print.py`).
   - **Fit:** its pocket is the coupon's own cut-end outline (+0.20, 5 deep), so it keys onto the coupon, which needs no feature.
   - **Set-up:** the hub clamped with its axis vertical, the coupon on top, the lever dropped on.
   - **Hook:** at 200 mm. The arm tapers 50 → 20 in the pulling plane.
8. **Yaw play limit:**
   - **Expected:** the FEA's elastic turn of the coupon's cut end under 17 N·m is 0.32 deg. At the dial point (60 mm) that is
     0.34 mm, plus 0.03 of lever bending: **0.37 mm**.
   - **Pass:** loaded, at most **0.47 mm** at 60 mm; unloaded, back within 0.05. Repeated with the lug bolts loosened.
   - **The old limit was wrong.** The old "under 0.5 mm at 200 mm" could never pass, because the elastic turn alone is 1.12 mm
     at 200 mm.
9. **Inserts:**
   - flush to 0.05 below the face;
   - three tested (two in the coupon, one in a scrap PETG block);
   - outer diameter and length measured with the calliper before pressing;
   - if one moves at 0.5 N·m, the arm torque stays 0.3 and the plates' hold on the rim is relied on. If one moves at 0.3, stop.
10. **Final hub only:** stated at the head of 2b, with the reason (a re-pick otherwise).
11. **Plate checks:**
    - **Blue check:** marker on each plate's top edge (lug side), close, bolt, open. No blue on the hub's root fillet.
    - **Slice preview:** at Z 0.35, the 0.7 strip is the hole's first perimeter overlapping the plate's outer perimeter (2 lines
      across it on every plate checked), a closed loop (`r1g_lug_plate_strip_slice.png`, `plate_slice_check.py`).

## D. Cable

The window is fixed at 68 deg and the bundle is clamped at the hub window.
- **The R 15 static S-bend to the rib gap is acceptable.** The wires are loose (16 or 18 AWG silicone, OD about 3.0, plus 26 AWG
  pairs). R 15 at the centre line is 5 x the largest OD, and the innermost wire is at about R 13 (4.4 x OD). That is within the
  usual 4-6 x OD for fixed runs, because the clamp keeps it from ever flexing. It would not be acceptable for a moving run.
- **Tie point: proposed, not applied** (`cable_tie_point_proposal.png`, CABLE_SLACK.md).
  - **Shape:** a bridge on the back half's -X inner wall at the neck, Y 255-261: a 2.0 x 4.0 bar, 1.6 off the wall, and a 3.0 x
    1.6 slot for a 2.5 mm tie.
  - **Printing:** it stands on the seam face, so no support; the outside is unchanged.
  - **Clearances:** 7 mm from the seam post, clear of the fins (Y 268-276).
  - **Cost:** about 0.1 g, under a minute.
