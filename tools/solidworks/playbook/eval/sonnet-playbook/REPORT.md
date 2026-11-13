# Benchmark run sonnet-playbook

Claim: sw-eval-sonnet. Models in `cad/_wip/sw-eval/sonnet-playbook/` (T6 files in `t6/`). Scripts: t1.py, t2.py, study.py, t3.py,
t4.py (also holds the T3 fixture-edge check), t5a.py, t6.py, t6_run.py, t6_proof.py. Raw numbers: the `t*_result.json` files.
Total wall time about 55 minutes of work from the first launch (the first launch waited about 12 minutes behind another
session's solve, as the playbook says it may). I did not read EVAL.md, to keep the measurement clean.

## T1. Bracket (about 14 min including the launch wait)
Built by `t1.py` with the swkit helpers, each feature given its hand `expect_dv`. Hand volume: 24000 + 12000 + fillet
(1 - pi/4)*16*50 = 171.7, minus base holes 570.2, minus bore and bolt holes 2498.7, minus four corner rounds 4*(1 - pi/4)*25*6.
Checks: volume 32974.02 mm3 against hand 32974.02; box 0,0,0 to 80,50,46; 1 body; no feature errors; mass 39.24 g at 1.19 g/cm3.
STL: watertight, one shell, bounds 0,0,0 to 80,50,46 (model frame), volume 32990.4 (+0.05 %). STEP is millimetres (read from the file).
Not verified: hole positions by measurement on the finished solid (checked only through the volume changes).

## T2. Change (about 2 min)
Opened `bracket.SLDPRT`, Save-As `bracket_b.SLDPRT` before touching it, counterbores by a ring cut (r 5 to 2.75, 3 deep, sketched
on Z 4.5, mid-plane), slot as two lines and two arcs (20 overall, 6 wide). Hand volume 31643.0 = T1 minus 657.4 minus 673.6; got
31643.0. Counterbore floor read from the planar faces: Z 3.0. 1 body, no feature errors. Not verified: slot position by measurement.

## T3. Study (about 4 min)
Hand: the 150 N at the bore centre (Z 28) acts 22 mm above the top of the base. M = 3300 N.mm, section 50 x 6 mm, Z = 300 mm3, so
sigma = 11.0 MPa at the root; at Z 12 the hand value is 8.0 MPa. Support: the four base-hole walls fixed. Load: remote 150 N +X on
the bore face. el 3.0 then 2.0 (converge rule, 3.1 % step), local control at el/2 on the R4 fillet, PETG, solver automatic.
Checks: reaction -150.0, 0, 0 N (load 150); plain section Z 12 on x=0: 8.40 MPa tension against 8.0 hand (+5 %), on x=6 -8.91 (+11 %);
displacement 2.36 mm against 0.31 mm for a rigid-base cantilever, the extra from flexure of the base, which I estimated only roughly
(1.5 to 2 mm); peak 15.52 MPa on the compressive side near the fillet tangent line (9.14, 19.5, 6.09), about 1.4 times the nominal
at the root, plausible for a fillet; layer stress 10.19 MPa on x=0 near Z 10.4; SF yield 2.90, SF layer 2.21.
What was excluded: nodes within 2 elements of fixtures and loads. The excluded fixed-hole-wall edge nodes read 22.8, 24.4, 26.8, 33.4
MPa at el 3, 2, 1.5, 1.0 (rising: a fixture singularity at the edge of a rigidly fixed screw hole); across layers the unmasked value
reaches 30 MPa on the bed-side hole edge. I judged these artefacts of fixing the whole hole wall, not stresses; a reviewer could
disagree and ask for a head-annulus support.
Convergence recheck with a fixed 4 mm exclusion (el 3.0, 2.0, 1.5; 25k, 66k, 140k nodes): 15.05, 15.52, 15.58 MPa and layer 10.14,
10.19, 10.22. The `converge()` rows use the default 2-element mask, which shrinks with the mesh: at el 1.0 it let hole-edge stress in
(18.2 MPa). Verdict: pass (both factors above 2.0), the layer factor is the tight one. Not verified: the screw clamp itself.

## T4. Sharp variant (about 16 min, mostly the 380k-node solve)
`bracket_sharp.SLDPRT` rebuilt by the same script without the fillet (volume matches the hand value). No mesh control (the corner
faces are large). Peak away from fixtures 14.49, 16.36, 17.38, 20.67 MPa at el 3, 2, 1.5, 1.0 (21,906 / 58,161 / 117,813 / 378,649
nodes), steps +13, +6, +19 %: not converged, on the base top surface at x 6.4 to 7.3 beside the corner line. It is a singularity, so I
report no stress for it. What does converge is the tension across layers, 11.46, 11.54, 11.55, 11.53 MPa, so SF layer =
22.5/11.53 = 1.95, below 2.0; and the corner-line averages (1 mm: 9.9, 9.7 MPa; 2 mm: 6.9, 7.0 MPa at el 1.5, 1.0). Verdict fail:
the layer factor fails on a converged number, and the yield factor cannot be certified from a peak that does not converge. Reaction
150.0 N at every size. Not verified: node counts under the corner averages (not logged); a mesh control limited to the corner
(static() controls whole faces only). The 379k-node run is over the "well under 150,000" in the brief; it was needed to show the climb.

## T5. Make it pass (about 3 min)
The T3 bracket meets the requirement, so T5's condition did not arise and I changed nothing. `bracket_c.SLDPRT` is an unchanged file
copy of bracket.SLDPRT, saved so the file exists; it is not a new design. Mass 39.24 g, growth 0 %. From the T3 field with a fixed
4 mm mask: tension across layers with layers stacked along X is 14.9 MPa (SF 1.51, would fail), along Y 5.5 MPa (SF 4.1): printing on
the y=0 side face would give more margin. I did not run a separate study or check printability for that.

## T6. Contact (about 25 min of the 40, including a discarded first model)
Hand: projected bearing 500/(10*30) = 1.667 MPa. Hertz line contact for the clearance fit, R* = 1/(1/5 - 1/5.1) = 255 mm,
E* = 2199 MPa, half width 1.57 mm, p_max = 6.8 MPa. Pin bending, hand: M at mid-span 3125 N.mm on Z = 98.2 mm3 gives 31.8 MPa.
Model `t6/ct6.SLDPRT`, six bodies in one part: PETG block, pin as three steel bodies (middle and two protruding ends, so the 250 N end
loads go on the ends' cylinder faces, as remote loads at y = -20 and +20), two soft pad rings (E 0.5 MPa). Block bottom fixed;
no-penetration set between the hole face and the pin's middle cylinder; hole 5.1, pin 5.0 (a real 0.1 mm gap). Solver direct sparse
through the macro (log: before 0, set err 0, after 7). Hole and pin-middle faces 0.8 then 0.6 mm control, global 3.0.
First attempt: pad rings bonded to the block face. It solved, but the block read 85 to 90 MPa all round the hole mouth, including the
unloaded bottom: an artefact of the bonded pad at the mouth edge. Discarded. The second model moved the pads 0.2 mm off the block
face and fixed their outer faces.
Results (0.8 / 0.6 mm control; 86,188 / 149,353 nodes; solve 126 s / 351 s): block hole-face peak von Mises 4.678 / 4.663 MPa at
(-3.85, 12.91, 13.34) / (4.14, -13.2, 12.98), a change of 0.3 %; block overall 5.13 MPa at the hole mouth; hole-top compressive
sigma_z 6.5 / 6.1 MPa (Hertz 6.8); pin peak 31.05 MPa on the pin underside at mid-span (hand 31.8). The contact is spread over the
full 30 mm length.
Validity checks: reaction 500.001 N for 500 N applied; pin axis rises 0.1285 mm = 0.1 gap + 0.028 mm block rise; penetration 0.0001 mm;
no-contact run (contact set removed, everything else the same): the pin rises 8.77 mm and the solver raised the excessive-displacement
box (answered No by static()), so the contact set carries the load; pad vm 0.062 MPa, force at most about 4.5 N (under 1 %; an upper
bound from stress times area, because the reaction readback sums every restrained node, pads and block together); node labels by
geometry: 0 unlabelled.
Not verified: friction (none modelled), only about 5 elements across the contact width, the pad force by direct reaction readback,
the hole-mouth edge (a sharp edge, 0.6 mm mesh). valid = true on these checks.

## T7. Diagnose
a. Two instances. PID 20948, 7890 s old, 9120 MB, `busy`: a long solve, not a hang; do not touch it. PID 2536, 2710 s, 1 thread, 0
windows, HALF-CLOSED: it stalls every launch on the machine. Next: do not launch; run `claims.py list` to see whose it is; report PID
2536 and the line `taskkill /PID 2536 /T /F` for Joey, and leave 20948 alone. Must not: launch anyway (it sits at the splash or
raises), kill either PID myself (neither is mine), or treat 20948 as hung.
b. Error 24 after 143 s with the log at the matrix decomposition and free memory falling from 26 to 12 GB in 11 s: out of memory in
the factorisation, not a singular model. Next: coarsen the global size and keep local controls on the joint to get under 450,000
nodes (4 mm global with 0.8 mm controls gave about 400k), run it alone, watch free memory. Must not: add restraints or change the
model because "error 24 means a free body", retry the same 796k model, raise MAX_NODES, or run two solves together.
c. A whole STL offset by (41.5, 0, 12.0) while the native part is right: the new machine's STL option "do not translate to positive
space" (toggle 71) was off, so SolidWorks shifted the part to positive space; the offset is the part's negative extents. Next: export
through `swkit.export()` (it pins the options), re-export, check `mesh.bounds` against `bbox(d)`, rerun the fit check. Must not:
subtract the offset in the fit check or move the mating part to match, edit the native part, or change SolidWorks settings by hand
(they are shared).
d. A peak at a fixed face edge reading 38, 47, 61 MPa at 2.0, 1.5, 1.0 mm rises with every refinement (+24 %, +30 %): a singularity
at the fixture edge, not a stress. Next: judge the part by the stress away from the fixture edge (fixed-distance exclusion,
`average()` at 0.5, 1, 2 mm with counts, a plain-section hand check), and ask whether the real support is that stiff (a real clamp has
a radius and compliance); report the converged section value, what was excluded and how large it was; the requirement needs vm of
22.5 MPa or less. Must not: report 61 or any of the three as the stress, call it converged, pass or fail the part on it (38 gives SF
1.18, 61 gives 0.74), or keep refining hoping it settles.
e. Silent for 25 minutes with the instance `busy`: it is solving (a large solve takes 7 to 11 minutes, reading results back over COM
has taken over an hour). Next: leave it; check that the solver files beside the model are changing and free memory, read
`%TEMP%\sw_hidden_<pid>.log` for a hidden `#32770 | Simulation` dialog; tell the other thread it is busy, not hung, and why. Must not:
restart or kill it (that orphans cwanalysisproc and star.exe, and a half-closed instance stalls every other thread's launch), launch
a second instance, or wrap it in `timeout`. Only if the log shows a dialog `static()` did not answer, answer it in my own instance;
end the instance through its own handle only if `--status` shows HALF-CLOSED.

## Playbook problems
1. 04-export.md's STEP unit check (`SI_UNIT(.MILLI.,.METRE.)`) does not match the file: SolidWorks writes `SI_UNIT ( .MILLI., .METRE. )`
   with spaces, so a literal search says "not millimetres". I found it by reading the line.
2. `converge()` and `Result.peak()` default to a mask of 2 element sizes, which shrinks as the mesh refines. With a fixed-hole-wall
   fixture this lets the hole-edge singularity leak into the "away" peak (T3 at el 1.0: 18.2 MPa against 15.6 with a fixed 4 mm
   mask), and the two-row `converge()` result stopped before it showed. 05-fea.md does not say to hold the exclusion distance fixed
   across a convergence series.
3. 05-fea.md has no guidance on how to support a screwed-down part: fixing the whole hole wall produces an edge peak that keeps rising
   (33 MPa, and 30 MPa across layers) and has to be argued away by hand. A head-annulus support option would remove the argument.
4. `converge()` and `static()` have no node budget below the 450,000 hard limit: sizes down to 1.0 mm on this small part reached 434k
   and 379k nodes; the task text asked for well under 150k, which `static()` does not check.
5. Mesh controls apply to whole faces (`ctrl`), so a sharp inside corner on a large face cannot be refined locally; T4's climb had to
   be shown with 379k nodes globally.
6. 05-fea.md's contact advice (pads "bonded both sides") does not warn that a pad bonded to the block at a hole mouth edge makes a
   false 85 to 90 MPa stress ring around it. What worked: pads off the block face with their own outer faces fixed. Also
   `Result.reaction` sums all restrained nodes, so "pads carry under 1 %" cannot be read directly; I bounded it from pad stress. A
   reaction split by fixture would help.
7. swkit `Sk.arc` direction has no stated convention ("check the result's volume"); +1 worked for my slot ends.
8. There is no recipe for loading only part of a face (the protruding ends of a pin): I split the pin into three bodies. `pick()`
   filters `area=` and `inside=` made that workable.
9. `claims.py list` shows a STALE claim 40 hours old (upper-arm-r1); 01-session.md does not say what to do about other sessions'
   stale claims (I left it).
