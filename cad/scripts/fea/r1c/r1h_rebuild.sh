#!/bin/bash
# R1h back half rebuild (2026-11-13): the tie bridge's rounds as SolidWorks fillets (the vertical outline edges, then the lower
# edges). Worktree lock only (builds never take C:\joe\.fea_solve.lock), the 180 s gap after our last job, 18 GB free; then the
# slice and print gate into cad/_wip/r1d_r1h_print, the front half staying R1g.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
until mkdir $LK 2>/dev/null; do sleep 15; done; echo "r1hrebuild $$" > $LK/owner
trap 'grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK' EXIT
if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
until [ "$(free)" -ge 18000 ]; do sleep 60; done
echo "R1H REBUILD start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
# the same environment the queue's R1h step had (r1g6q.sh), so only the tie bridge's rounds differ
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3S38.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_r1g5.SLDPRT
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=1.0 HS_LUGFACE_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
(export ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_WIP_TAG=_r1h_print ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_END_DROP=0.70 ARM_SEAM_LEADIN=0.1,2.0 ARM_TIE_BRIDGE=1
 bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:back"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1h_build_rebuild.log)
date +%s > $STAMP
if grep -q "STOP at" cad/_wip/r1h_build_rebuild.log; then
  echo "R1H BUILD_FAILED $(grep -iE 'STOP at|error|traceback|R1H' cad/_wip/r1h_build_rebuild.log | tail -4 | tr '\n' ' ' | cut -c1-300)" >> $L; exit 1
fi
echo "R1H BUILT back half $(date +%H:%M) $(grep -E 'R1H' cad/_wip/r1h_build_rebuild.log | tr '\n' ' ' | cut -c1-400)" >> $L
X=$R/_wip/r1d_r1h_print
mkdir -p $X/exports $X/checks
cp -p $R/_wip/r1d_r1g_print/exports/upper_arm_organic_front_left.STL $R/_wip/r1d_r1g_print/exports/upper_arm_organic_rs02_ring_left.STL $X/exports/
(cd cad/scripts/arm && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print ARM_PRINT_SUFFIX=_r1h ARM_PRINT_HUBBAND_Y0=274.0 ARM_PRINT_FLANK_BLOCKER=1 ARM_FLANK_GAP=0 $PYC organic_print.py back > $X/slice.log 2>&1)
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print PRINT_WHITELIST=$R/reviews/upper-arm/20261111_r1c-delta/r1d/r1e/print_whitelist.json $PYC print_check.py back > $X/print_check.log 2>&1)
echo "R1H SLICED+GATED $(grep -oE '"(job|mesh_gate|time_s|grams)": "?[A-Za-z0-9.]+' $X/print_check.log | tr '\n' ' ')" >> $L
