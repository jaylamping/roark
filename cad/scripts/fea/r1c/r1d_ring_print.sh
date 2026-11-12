#!/bin/bash
# Ring print geometry (WIP only, not a release): after the ring stop solve(s) end, build the halves (0.1 gap, ribs 0.25), slice with
# the ridge blocker at the crown, mesh gate, and the closing-path / overlap check against the shoulder rev D candidate (556cc44).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring_print.log
# 2026-11-12 08:10: no longer waits on the ring stop solve (the solver could not be switched; that run is stopped). Waits only for a free instance.
until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
echo "start $(date)" >> $L
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_WIP_TAG=_ring_print ARM_FLANK_GAP=0.1 ARM_RIB_PROUD=0.25 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:front parts:back"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_ring_print.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED" >> $L; exit 1; }
echo "BUILT ring print $(date +%H:%M)" >> $L
X=$R/_wip/r1d_ring_print
cp -p cad/exports/upper-arm/upper_arm_organic_rs02_ring_left.STL $X/exports/
(cd cad/scripts/arm && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print ARM_PRINT_SUFFIX=_r1d_ring ARM_PRINT_HUBBAND_Y0=274.0 ARM_PRINT_FLANK_BLOCKER=1 ARM_FLANK_GAP=0.1 python J:/code/roark-wt/left-arm-organic/cad/scripts/fea/r1c/capped.py --mb 6144 -- python organic_print.py back front > $X/slice.log 2>&1)
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print python J:/code/roark-wt/left-arm-organic/cad/scripts/fea/r1c/capped.py --mb 6144 -- python print_check.py back front > $X/print_check.log 2>&1)
echo "SLICED+GATED $(grep -E '\"job\"' $X/print_check.log | sed -E 's/.*\"job\": \"([a-z]+)\", \"mesh_gate\": \"([A-Z]+)\".*\"time_s\": ([0-9]+), \"grams\": ([0-9.]+).*/\1 \2 \3s \4g/' | tr '\n' ' ')" >> $L
mkdir -p $X/checks
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports FIT_JSON=$X/checks/rs02_fit.json HUB_STL=$R/_wip/shoulder_hub_556cc44/shoulder_hub_left_revD_candidate.STL CLOSE_JSON=$X/checks/close_path_revD.json PYTHONPATH=. python J:/code/roark-wt/left-arm-organic/cad/scripts/fea/r1c/capped.py --mb 6144 -- python ../../../scripts/fea/r1c/close_path_r1c.py > $X/checks/close_path_revD.log 2>&1)
echo "CLOSE_CHECKED $(grep -E 'final overlap|path_collisions' $X/checks/close_path_revD.log | grep -E 'hub|final' | tr -s ' ' | cut -c1-200 | tr '\n' ' ')" >> $L
echo "RING_PRINT_DONE $(date)" >> $L
