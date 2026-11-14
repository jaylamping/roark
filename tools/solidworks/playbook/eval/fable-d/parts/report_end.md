## Where the playbook or a helper was wrong, unclear or missing something

1. **`r.average()` is the wrong tool for check 3 on a part in bending** (05-fea.md, "five checks"). It averages
   over a ball, so round a point on a surface it takes in nodes below the surface, where bending stress falls: 0.97 MPa
   where the surface carries 1.237 and the hand value is 1.235. Followed as written, a correct study fails its own
   check by 22 %. Needs a surface-only variant, or a line saying so.
2. **`Result.summary()` and `peak()` do not know about bodies.** In the eight-body housing model they reported the
   steel screw's 50 and 120 MPa as the peak and printed `sf_yield` 0.89 and 0.37 against PETG's yield. 05-fea.md says
   to split by geometry but swfea has no helper for it; I wrote one (`d2_post.py`, `classify`). A reader who trusts
   `summary()` on a contact model is told a passing part fails.
3. **No way to get reactions per node.** `static()` only returns the sum over every restrained node. The share a
   pad carries then has to be bounded from stress times area (05, contact rule 2). I used `post=` and the private
   `swfea._arr` to read the per-node table and split it by position: exact, and four lines. Worth a helper.
4. **`converge()` follows von Mises and layer tension but not shear between layers,** while 07-done.md asks for all
   three measures converged before a pass. I wrote my own loops.
5. **`sheet.py` cannot draw an assembly.** Several STLs become rows, not one scene, and there is no STL writer. Every
   task here asked for a picture of parts together; I wrote `merge_stl` and `box_tris` in `common.py`.
6. **"Predict the node count" has no rule to predict with.** I used 12.3 x volume / element size cubed: 17 % low
   on a plain part, 46 % low once local controls and thin screws were in. One line in 07-done.md would do.
7. **Nothing on clamped joints.** 05-fea.md covers contact, pads and proofs well, but not how to stand in for a
   screw, and not that tightening a screw across a split with a gap is itself a load case, here larger than the
   service load. That was the main judgment in D2 and the pages are silent on it.
8. **Nothing on changing an existing part.** 03-modelling.md says "prefer changing the script and rebuilding" and
   02-com.md has no call for reading or setting a feature's dimension or for editing a sketch in place. D3 part two
   forbids a rebuild. What worked is in `d3_plates.py` (`set_dim`, `redraw_circles`) and belongs in 02-com.md.
9. **`extrude()`'s docstring says THRU_ALL "cuts through both sides".** The call it makes is single-direction; it
   works because both directions are tried. Harmless here, wrong as written.
10. **05-fea.md, the rigid-load warning, is right and under-sold.** It is filed under holes beside a loaded face. In
    D1 the same effect changed the deflection by four times with no hole anywhere, by holding four post tops level.
    The prediction caught it; the page should say a rigid load also fixes rotations.
11. **A pass needs three mesh sizes, the cap is 200,000 nodes, and a contact model with screws starts at 146,000.**
    The finest size I could add was 1.19 times smaller. The pages do not say what to do when the cap and the
    convergence rule meet; I coarsened the screws and reported the series as it is.
12. **Small:** `claims.py list` showed a STALE claim (`upper-arm-r1`, 3,100 minutes old), left alone as 01-session.md
    says. Free memory was 12.7 GB of 32 with no SolidWorks running at all, 4.7 GB above the floor `job()` enforces:
    something else on the machine holds about 19 GB.
