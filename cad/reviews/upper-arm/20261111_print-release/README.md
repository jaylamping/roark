# Upper arm print release: review outcome (2026-11-11)

**Packet:** commit 7ad4452, `PACKET.md`, hashes in `SHA256SUMS.txt`.

**Reviewers:** both at High, run one after the other on the same packet:
- Codex `gpt-6.1-sol`. Its review is in `reviews/codex-sol.md`.
- Claude Code `claude-opus-5-5`, subscription, about $3.05. Its review is in `reviews/claude-opus.md`.

Hashes matched after each run.

**Verdict:** both reviewers say not for robot use yet. Both accept printing the halves as a bench test article once the infill
gap (B1) is fixed. B1 was fixed on 2026-11-11.

## Findings, reconciled

| # | Finding | Who | Decision |
| --- | --- | --- | --- |
| 1 | The 100% modifier ended at X 160.5. The keys and their wall tapers run to X 165.4 and beyond. | both (Opus: blocker) | **Accepted, fixed.** The modifier now runs to X 171. Halves re-sliced: back 5 h 05, front 4 h 34. Mesh gate passes. |
| 2 | The stop force was converted at r 38.25. The pad acts at r 33, so 17 N·m is 515 N, not 444 N. At 515 N the lug root is 1.98 / 1.59, but elsewhere the layer SF is 1.17–1.22. The stop cases are on v23 geometry. | both | **Accepted.** README corrected. Re-run STOP_0/124 on the final geometry before the stop is relied on. |
| 3 | A static rating doesn't bound impact. A back-driven or motor-driven hit can reach about 33 N·m. | both | **Accepted, recorded** as a software hand-off. A speed limit near each stop, from E = T²/2k, is needed as well as the torque limit. |
| 4 | Two keys sharing 34 N·m miss 1.5 in a second place: key 0's tip at 1.30 bulk. | both | **Accepted.** Declared alongside the neck corner. |
| 5 | Crush ribs: interference ranges from −0.15 to +0.45 per face. After the first peak load they flatten, and one key per direction then carries the torque. That gives 0.81 halves and 0.75 ring at 34 N·m. | both | **Accepted as the honest rating.** The torque path is rated 17 N·m with one key: halves 1.62, ring 1.50. 34 N·m isn't met. Measure rib height before the first assembly. |
| 6 | The ring's "no exclusion" layer figure still drops nodes within 2 mm of the fixed flange. Unexcluded it is 0.58 at 17 N·m: tension on a bonded rigid face, which is a fixture artefact. | both | **Accepted.** Packet wording was wrong. A contact or compression-only flange run is still to do. Use M3 washers under the heads and retorque after 24 h. |
| 7 | Axial stack: 0.2–0.3 mm nominal, worst case −0.2 to +0.6. The flange and stop positions are typed-in constants, not measured from the meshes. | both | **Accepted.** Proposed fix: move the stop face 0.2 mm outboard (internal). Needs approval. |
| 8 | Ring brim: the brim follows into the key slots and the window and leaves flash on the bearing flanks. The ring doesn't need a brim. | Opus | **Accepted** for any reprint: no brim on the ring. Joey's printed ring: clean all flanks before fitting. |
| 9 | Joey's ring has a 1.2 mm chamfer. Hand-filing it to 2 mm can't hold the clearance to the R2 round. | both | **Accepted.** Recommend a reprint: 58 min, no brim, 2.2 mm chamfer. |
| 10 | Support touches fit faces. Only visible faces are screened. | both | **Accepted.** List the fit faces (bore, rib face, key flanks and ends, stub) and inspect them. |
| 11 | The straight plug-cable envelope hits the hub at Y 300. The real cable turns earlier. | Sol | **Accepted.** Route the RS02 cable and the trunk into the back half before closing. A routed envelope check is still to do. |
| 12 | The RS02 output face is 0.5 mm beyond the modelled 197.2. | Sol | **Accepted**, on the forearm to-do list. |
| 13 | The stub coupon was printed at 3 walls / 15%. The final stub is 6 walls / 100%. | both | **Accepted.** Measure the stub on the first half. |
| 14 | The rib web candidate (option 2). | both | **Dropped.** It raised the peak (E34 SF 0.16). Opus suggests a bead along the wall's free edge at the neck opening, or narrowing the opening (φ −24 to 41) toward the harness's φ ±15. Kept as next options. |
| 15 | Heat and creep at the motor flange. PETG HDT is about 70 °C. | Opus | **Accepted.** Log the flange temperature during the bench torque test and retorque afterwards. |
| 16 | Minor: the key coupon misses the neck corner, model versions are mixed, some whitelist text is stale, the slice time differs by 1 min. | Opus | Noted. A whole-arm bench torque test covers the corner. |
| 17 | The neck corner is 1.28 / 1.10 at 34 N·m and about 2.2 at 17 N·m. | both | **Acceptable as a bench article only.** Test the whole arm in −T (keys 3 + 1) and watch φ 41° for whitening. |

## R1c (2026-11-11): hub joint tie, ahead of its delta review

R1 halves plus:
- inside fins joining the hub posts to the seam posts;
- a ridge in the hub seat that closes around a groove in the hub spigot (the hub's rev C+), so the joint carries load along
  the hub axis without the lugs and bolts;
- a seat collar;
- a 0.5 bore end chamfer;
- a floor corner ring.

The other parts of the arm are unchanged: geometry differs only between Y 276 and 302, the RS02 fit is identical to R1, and
G90_fine and HALFK31_fine are within mesh noise of R1.

Hub-seat contact FEA, bolted, no preload, with the grooved hub as its own body: see `r1c/RIDGE5_6_FEA.md`. The arm passes
G90 (1.5) and STOP_0 (1.2) at the 0.5 mm average. Each case was solved twice, and the two runs matched exactly.
With the plain hub the bolts would reach 770 MPa at the stop; with the ridge they see 105 MPa.

The halves need the grooved rev C+ hub and do not close around today's hub. Assembly order: `cad/upper-arm/BENCH_TESTS.md`.
Delta review packet: `cad/reviews/upper-arm/20261111_r1c-delta/`.

| Plate | Time | Filament | Mesh gate |
| --- | --- | --- | --- |
| Back half R1c | 5 h 27 | 124.5 g | PASS |
| Front half R1c | 4 h 45 | 108.2 g | PASS (the same 4 visible 8 mm² insert-hole support spots as R1) |
