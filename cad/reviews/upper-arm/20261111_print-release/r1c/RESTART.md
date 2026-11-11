# R1c: restart on another machine (state at ridge6b, 2026-11-11)

Branch `left-arm-organic-r1`. R1 release files (commit 70cf634) are unchanged. Everything for R1c is built from scripts; the WIP
models below are gitignored and can be regenerated.

## What a restart needs

- This branch, plus the `left-arm` worktree for today's hub native part:
  `J:/code/roark-wt/left-arm/cad/upper-arm/upper_arm_hub_left.SLDPRT`
  (SHA-256 7b857f61855fb2a65fd4e6d73981605c4b9f12747af1e5abcfd2a75bc5ddcb0b). `hub_seat.py` copies it as `HUB_SRC`.
- The paths in `cad/upper-arm/HANDOFF.md` ("Machine paths to fix on a new machine").
- SolidWorks 2026 with Simulation; part template `C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot` (MMGS).
- Python with trimesh, numpy, scipy and pywin32.

## Rebuild ridge6b from the scripts alone (bash, from the repo root)

```bash
export ARM_R1C=1 ARM_RIDGE=1 ARM_SEAT_RIBS=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
# 1. arm: master, halves (with STL/STEP exports in cad/_wip/r1c/exports), FEA model UA_ORGANIC_BONDED_v31
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:front parts:back parts:fea_upper"
mkdir -p cad/_sim/ua2 && cp cad/_sim/upper-arm/UA_ORGANIC_BONDED_v31.SLDPRT cad/_sim/ua2/
# 2. grooved hub (rev C+) + bolted hub-seat model
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_MODEL=UA_HUBSEAT_v31_ridge6b_bolted.SLDPRT
ARM_SW_DIR=J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-fea ARM_FEA_DIR=J:/code/roark-wt/left-arm-organic/cad/_sim/ua2 python cad/scripts/fea/hub_seat.py build
# 3. solves, one fresh SolidWorks instance per case (copy the model into its own run folder first)
mkdir -p cad/_sim/r1c_u && cp cad/_sim/ua2/$HS_MODEL cad/_sim/r1c_u/
ARM_SW_DIR=J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-fea ARM_FEA_DIR=J:/code/roark-wt/left-arm-organic/cad/_sim/r1c_u python cad/scripts/fea/organic_fea.py HS_G90_fine
# (then close that instance: cd cad/scripts/arm && ARM_SW_DIR=... python -c "from swlib import finish; finish()"), and repeat for HS_STOP_0_fine
# 4. post-processing (chunked, about 1-2 GB)
python cad/scripts/fea/r1c/hub_r1c.py cad/_sim/r1c_u/org16_HS_G90_fine.npz cad/_sim/ua2/HUB_GROOVE.STL
```

Use forward-slash paths in bash. `"...\_sim\$2"` escapes the `$` and silently breaks the run folder.
`cad/scripts/fea/r1c/r1c_ridge6.sh`, `r1c_ridge6b.sh` and `r1c_ridge6b_par.sh` are the chains as run.

## WIP files at ridge6b (SHA-256, bytes)

| File | SHA-256 | Bytes |
| --- | --- | --- |
| cad/_wip/r1c/upper_arm_organic_master_left_r1c.SLDPRT | 91e73589c28e226e4a90f720d9e40ae7b1ff74f99a71cbe8e4b8e7c74d8b06d3 | 1926153 |
| cad/_wip/r1c/upper_arm_organic_front_left.SLDPRT | 7d01270d121b618a394ed15a9c75214c7abe907b0aa157dd5d87876e46d339e8 | 1801006 |
| cad/_wip/r1c/upper_arm_organic_back_left.SLDPRT | ea9674329e9955a1b35434ae6ffcbfe07ca65eb8860fcca4a3136bac8a09c016 | 2109133 |
| cad/_wip/r1c/exports/upper_arm_organic_front_left.STL | 38fd51a10e35f62811c9c18dd20527602cb0e13b986c42f0cf17ea7f007ca76d | 774984 |
| cad/_wip/r1c/exports/upper_arm_organic_back_left.STL | 130fb4c04e5fc0b035152ba3981cd6f8d1a3e9c00476a4b5765f8e98434043b6 | 1081384 |
| cad/_wip/r1c/exports/upper_arm_organic_front_left.step | 7ccecaf24719f70a565267e168b55a647753c7de260189569280090a4cedf29e | 2605438 |
| cad/_wip/r1c/exports/upper_arm_organic_back_left.step | c08402ab0ce77a22845fced1b98f692983b981ab17dbb671860335cb270f230d | 3580495 |
| cad/_sim/upper-arm/UA_ORGANIC_BONDED_v31.SLDPRT | c04587e0ed1b65fa1a6ebf73e8cbc44a213425e1a7a901eea756685e0267c31b | 2222914 |
| cad/_sim/ua2/HUB_GROOVE.SLDPRT (rev C+ mirror) | 9e25fad32d81a5ef2942b04e01ed34af2a12928f79ac3a29ee95c59f1b77c336 | 1664258 |
| cad/_sim/ua2/HUB_GROOVE.STL | 9ae913ac7b828910cd7914adf53b559acdc0440247c41903c9050b464fca0f31 | 527984 |
| cad/_sim/ua2/HS_BOLTS.SLDPRT | 9ae8d024d3777b18fd4b68d02b1d174593d73d11a61dc4bedec534be87a9825a | 54637 |
| cad/_sim/ua2/UA_HUBSEAT_v31_ridge6b_bolted.SLDPRT | b168a406321ee338bb343cdd0e206fa842721b00a4eb0445e744a1c15415694c | 3337033 |

SolidWorks files are not byte-reproducible, so on a rebuild compare the STL exports with `geom_diff.py`, not hashes.
The ridge6b solves (`_sim/r1c_u`, `_sim/r1c_v`) were running when this was written.
