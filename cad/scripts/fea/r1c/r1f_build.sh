#!/bin/bash
# R1f WIP halves (2026-11-12): R1e plus the hub rev D3 extended-lug pocket, post-to-wall webs, root relief, 0.5 breaks and the
# 0.5 per-side lug slot (ARM_LUG_POCKET=1, ARM_SLOT_CL=0.5). SolidWorks under the same one-job lock as the FEA (r1e_solve1.sh
# rules: lock taken before the launch, released after end_session; 180 s since the last job; >= 16 GB free). Then the slice,
# mesh gate and a wall check at the seam, under capped.py. WIP only (cad/_wip/r1d_r1f_print).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1f_build.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
until mkdir $LK 2>/dev/null; do sleep 15; done
echo "r1f_build $$" > $LK/owner
trap 'grep -q "^r1f_build $$\$" $LK/owner 2>/dev/null && rm -rf $LK' EXIT
until ! python "$SWI" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
until [ "$(free)" -ge 16000 ]; do sleep 60; done
echo "start $(date +%H:%M) (lock held)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_WIP_TAG=_r1f_print ARM_FLANK_GAP=0 ARM_RIB_PROUD=0
export ARM_SLOT_BREAK=1.2,1.6 ARM_END_DROP=0.70 ARM_SEAM_LEADIN=0.1,2.0 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:front parts:back"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1f_build_rebuild.log
date +%s > $STAMP
grep -q "^r1f_build $$\$" $LK/owner 2>/dev/null && rm -rf $LK      # SolidWorks done: release for the FEA queue
if grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log; then echo "BUILD_FAILED $(grep 'STOP at' cad/_wip/organic-arm/rebuild_ua.log | tail -1) $(grep -iE 'error|traceback|R1F' cad/_wip/organic-arm/rebuild_ua.log | tail -4 | tr '\n' ' ' | cut -c1-300)" >> $L; exit 1; fi
echo "BUILT r1f halves $(date +%H:%M) $(grep -E 'R1F' cad/_wip/r1f_build_rebuild.log | tr '\n' ' ' | cut -c1-300)" >> $L
X=$R/_wip/r1d_r1f_print
mkdir -p $X/exports $X/checks
cp -p cad/exports/upper-arm/upper_arm_organic_rs02_ring_left.STL $X/exports/ 2>/dev/null
(cd cad/scripts/arm && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print ARM_PRINT_SUFFIX=_r1f ARM_PRINT_HUBBAND_Y0=274.0 ARM_PRINT_FLANK_BLOCKER=1 ARM_FLANK_GAP=0 $PYC organic_print.py back front > $X/slice.log 2>&1)
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print PRINT_WHITELIST=$R/reviews/upper-arm/20261111_r1c-delta/r1d/r1e/print_whitelist.json $PYC print_check.py back front > $X/print_check.log 2>&1)
echo "SLICED+GATED $(grep -E '"job"' $X/print_check.log | sed -E 's/.*"job": "([a-z]+)", "mesh_gate": "([A-Z]+)".*"time_s": ([0-9]+), "grams": ([0-9.]+).*/\1 \2 \3s \4g/' | tr '\n' ' ')" >> $L
$PYC $R/scripts/fea/r1c/bore_survey.py $X/exports > $X/checks/bore_survey.txt 2>&1
echo "R1F_BUILD_DONE $(date +%H:%M)" >> $L
