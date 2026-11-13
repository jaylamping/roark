#!/bin/bash
# R1f on hub rev D3 (shoulder thread 22ead5b; 2026-11-12). One process; every SolidWorks step under the one-job lock
# (cad/_wip/.fea_job_lock; 180 s since the last job; >= 16 GB free):
#   1. the R1f halves (web from offset 26.0), slice, gate        (r1f_build.sh)
#   2. closing path: D3 + the 0.70 ring + four 0.45 lug plates against the R1f halves
#   3. our FEA hub with the D3 lugs (hub_seat.py d3hub), checked by section against the D3 STL
#   4. the hub-seat model: the 0 gap arm (shim lumped), R1f pocket / webs / 0.5 slot, D3 hub, inserts and bolts
#   5. YAW +17, YAW -17, STOP_0, STOP_124, G90 on the global 4.0 mesh, one at a time (r1e_solve1.sh)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
D3=$R/_wip/shoulder_hub_d3_22ead5b/shoulder_hub_left_revD3_candidate.STL
X=$R/_wip/r1d_r1f_print
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
lock() { until mkdir $LK 2>/dev/null; do sleep 15; done; echo "$1 $$" > $LK/owner
  until ! python "$SWI" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
  if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
  until [ "$(free)" -ge 16000 ]; do sleep 60; done; }
unlock() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; date +%s > $STAMP; grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; }
trap 'grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK' EXIT
echo "R1G3S (r1g3 STOP_0, with the machine-wide solve lock) start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 ARM_PLATE_HOLE_R=3.0 HS_D3=1
# 5 STOP_0 on r1g3 (plate hole Dia 6.0; coordinator 2026-11-13); post / lug / fin control 1.0, bearing faces 0.8 (the R1g probe: 390 k nodes)
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=1.0 HS_LUGFACE_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3S.SLDPRT HUBSTL=HUB_D3S.STL DS_SOLVER=1 FEA_SAVE_DISP=1
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  bash cad/scripts/fea/r1c/mesh_guard.sh $1 &
  FOLDER=$1 MTAG=r1g3 CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve2.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '
' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1g3_stop0b HS_STOP_0_fine 0.5
echo "R1G3S_DONE $(date)" >> $L
