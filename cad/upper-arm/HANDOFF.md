# Upper arm: hand-off to holly-pc (2026-11-11)

## Where things stand

| Branch | Commit | What it is |
| --- | --- | --- |
| `left-arm-organic` | ad67bd0 | The **reviewed geometry**, called v26 in the FEA, plus the review fixes. Print files in `cad/prints/upper-arm/`. Review outcome in `cad/reviews/upper-arm/20261111_print-release/README.md`. |
| `left-arm-organic-r1` | eed7031 | **R1, code only, never rebuilt.** The RS02 stop face is 0.2 mm further out (`STOP_PLAY` 0.4 in `organic_master.py`). The ring's print project has no brim. FEA model names are v28. |

**R2** is an attempt to strengthen the neck-opening corner where the rib meets the drum wall, at φ 41° and 336°. Nothing is
built yet. Tried and dropped: a web on the rib's inboard side, which raised the peak to E34 SF 0.16.
The next ideas, both from the Opus review:
- a bead along the drum wall's free edge at the neck opening, at φ 36–46° and 331–341°;
- narrowing the neck opening (now φ −24° to 41°) toward the φ ±15° the harness needs.
Both must keep 3.5 × 13 for the harness, the RS02 plug path, and finger room for plugging in. No outside change.

**Joey has printed:** the stub coupon (fits) and an RS02 ring with the old 1.2 mm chamfer. That ring is for the RS02
test fit only. A new ring, with a 2.2 mm chamfer and no brim, is to be printed.

## Remaining steps, in order

1. **R1 rebuild** (branch `left-arm-organic-r1`). Rebuild master, ring, front, back and the FEA model: `run/rebuild_ua.sh`.
   It runs `organic_master.py upper`, then `organic_parts.py ring front back fea_upper`, one fresh SolidWorks instance per job.
2. **R1 fit:** `python cad/_wip/organic-arm/cad/rs02_fit.py`. Check the stack and the worst-case axial shift: the
   `axial_freedom_mm` and `shifted_0p2_overlap_mm3` keys. The only overlaps allowed are the crush ribs, 0.15 thick.
3. **R1 print:** `python cad/scripts/arm/organic_print.py ring back front key_coupon`. Then, from `cad/_wip/organic-arm/cad`,
   `python print_check.py ring back front key_coupon`. Copy the `.3mf` and `.gcode` into `cad/prints/upper-arm/`.
   Record the exports with `tools/cad/record_export.py`. `tools/cad/check_cad_layout.py cad` must show 0 errors.
4. **Stop cases at 515 N on the current geometry.** 17 N·m at the pad radius r 33 is 515 N.
   - In `organic_fea.py`, set the STOP force to 515.0. It is 889.0 now: `CASES['STOP_' + tag]`.
   - Run STOP_0, STOP_0_fine, STOP_124 and STOP_124_fine, then `stop_post.py` (its `889N`/`444N` keys need relabelling).
5. **R2** (optional; R1 is the release if R2 doesn't clearly help): copy the master into a separate config or branch, add the
   change, then run E34_fine, HALFK02_fine, HALFK31_fine, HALFK0_fine, G90_fine and the stop cases. Adopt only if the
   neck corner reaches about 1.35 bulk and layer at 34 N·m with nothing else worse.
6. **Report:** the final numbers, with the stop at 515 N and the torque path rated at 17 N·m with one key. Then the file list,
   print order (ring, back, front) and checklist (`cad/prints/upper-arm/SETTINGS_CHECKLIST.md`). Then the bench tests
   (`cad/upper-arm/README.md`).

**Running FEA:** `run/fea_q26.sh CASE ...`. Each case gets a fresh instance (`ARM_SW_DIR` = `cad/_wip/arm-sw-fea`;
`run/fea_q26b.sh` uses `arm-sw`). Results land in `ARM_FEA_DIR` (`cad/_sim/ua2`). Before a run, copy the FEA models
(`cad/_sim/upper-arm/UA_ORGANIC_BONDED_v*.SLDPRT`, the ring SLDPRT as `RING_v*.SLDPRT`, the master as
`UA_HALVES_v*.SLDPRT`) into `cad/_sim/ua2` under the names in `organic_fea.py`. Tables: `cad/_wip/organic-arm/cad/fea_table.py`.
Two solvers at once is fine for small cases. Two ~390k-node halves solves at once crashed reading back their results, so
run those one at a time.

## Machine paths to fix on a new machine

- `J:/code/roark-wt/left-arm/...`, used by:
  - `print_check.py` and `a2_check.py` (`support_check.py`, `mesh_check` path)
  - `print_check.py` and `build_packet.py` (today's hub STL `cad/exports/upper-arm/upper_arm_hub_left.stl`)
  - `render_parts.py` (shoulder STLs, `concepts.py`)
- `J:/code/marengo/...`, used by:
  - the vendor RS02 STL `cad/_wip/left-arm-layout-import/envelope/stl/ELBOW_RS02.STL` (`rs02_fit.py`)
  - `hardware/tools/mesh_check.py` (`print_check.py`)
  - the seed project `hardware/designs/left-arm/prints/upper-arm/upper_arm.3mf` (`organic_print.py`)
- `C:/Program Files/Bambu Studio/bambu-studio.exe` (`organic_print.py`)
- `C:/Temp/REVIEW_PACKET_UA_PRINT_20261111`: the review packet as sent (`build_packet.py`). A copy of its summary and the reviews
  is in `cad/reviews/upper-arm/20261111_print-release/`.
- `cad/_wip/organic-arm/` (gitignored) holds the check, render and packet scripts and the print outputs. Copy it across.
