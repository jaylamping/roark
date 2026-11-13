#!/bin/bash
# r1g6 (2026-11-13, coordinator 20:11Z): hub lug holes Dia 3.8 (HUB_D3S38) with the lumped plate hole Dia 3.4 (r 1.7), plate top Y 294.6.
# One job at a time, both locks, 14 GB gate, "used" = our own process tree, stopped at 15 GB, free stop 2 GB (r1e_solve3).
#   R1G6_PHASE=first: build UA_HUBSEAT_r1d_r1g6, then G90 + YAW -17 only (the case that failed on r1g5), then stop for review.
#   R1G6_PHASE=rest : STOP_0, STOP_124, G90 + YAW +17, YAW -17, YAW +17, G90 on r1g6; the R1h back half; the convergence run on r1g6.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
SL=/c/joe/.fea_solve.lock
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
wpid() { cat /proc/$$/winpid 2>/dev/null || echo $$; }
lock() {
  until mkdir $LK 2>/dev/null; do sleep 15; done; echo "$1 $$" > $LK/owner
  until ! python "$SWI" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
  if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
  while true; do      # the shared solve lock only at the moment of launch (coordinator 14:17Z): memory, lock, re-check, else release and wait
    until [ "$(free)" -ge ${MINFREE:-18000} ]; do sleep 60; done
    if ( set -o noclobber; echo "left-arm-organic $(wpid) $(date +%s) $1" > $SL ) 2>/dev/null; then
      [ "$(free)" -ge ${MINFREE:-18000} ] && break
      rm -f $SL; sleep 60; continue
    fi
    op=$(awk '{print $2}' $SL 2>/dev/null)
    if [ -n "$op" ] && ! powershell -NoProfile -c "if (Get-Process -Id $op -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"; then
      echo "stale solve lock (PID $op dead): removed $(date +%H:%M)" >> $L; rm -f $SL; continue
    fi
    sleep 30
  done; }
unlock() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; date +%s > $STAMP
  grep -q "^left-arm-organic $(wpid) " $SL 2>/dev/null && rm -f $SL
  grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; }
trap 'grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; grep -q "^left-arm-organic $(wpid) " $SL 2>/dev/null && rm -f $SL' EXIT

echo "R1G5Q (hub lug holes Dia 3.8; STOP_0, STOP_124, G90 + YAW -17) start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 ARM_PLATE_HOLE_R=1.9 ARM_PLATE_TOP=294.7 HS_D3=1
# 1 hub-seat model (as r1g2 / r1g3, only the plate hole and top differ)
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3S38.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_r1g5.SLDPRT
until grep -q "R1G6Q_DONE" $L; do sleep 30; done
echo "R1G6 STOP_124 rerun start $(date +%H:%M) (the queue run failed: mesh guard, 215 k nodes)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 ARM_PLATE_HOLE_R=1.9 ARM_PLATE_TOP=294.7 HS_D3=1
# 1 hub-seat model (as r1g2 / r1g3, only the plate hole and top differ)
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3S38.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_r1g5.SLDPRT
echo "R1G6Q phase ${R1G6_PHASE:-first} start $(date +%H:%M)" >> $L
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 ARM_PLATE_HOLE_R=1.7 ARM_PLATE_TOP=294.6 HS_D3=1
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=1.0 HS_LUGFACE_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export DS_SOLVER=1 FEA_SAVE_DISP=1 HUBFILE=HUB_D3S38.SLDPRT HUBSTL=HUB_D3S38.STL FX_HOLE_R=1.9
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  bash cad/scripts/fea/r1c/mesh_guard.sh $1 &
  FOLDER=$1 MTAG=r1g6 CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve3.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '
' ' ' | cut -c1-260) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
  grep -q "^SOLVED $1" cad/_wip/r1d_ring_ds.log && bash cad/scripts/fea/r1c/post_r1g.sh $1 1.7 294.6 >> $L 2>&1
}
job r1g6_stop124 HS_STOP_124_fine 0.5
echo "R1G6_STOP124_RERUN_DONE $(date +%H:%M)" >> $L
