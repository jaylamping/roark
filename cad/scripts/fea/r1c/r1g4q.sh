#!/bin/bash
# r1g4 (2026-11-13, after the review of 39154dd): lug plates with a Dia 3.8 hole (the plate holds the insert captive) and the
# plate top at Y 294.7; halves unchanged. After R1G2R (YAW -17, G90 + YAW +17 on r1g2):
#   1. build the hub-seat model UA_HUBSEAT_r1d_r1g4 (plates lumped inside their outline, boss hole r 1.9, top 294.7)
#   2. STOP_0, then G90, one at a time (r1e_solve2.sh: worktree lock + machine-wide solve lock, mesh guard, memory watch)
#   3. post_r1g.sh on each (all-candidate averages, spot list, region report, Fx path for STOP_0)
# The build also holds both locks (it runs SolidWorks).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
SL=/c/joe/.fea_solve.lock
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
wpid() { cat /proc/$$/winpid 2>/dev/null || echo $$; }
lock() {
  until mkdir $LK 2>/dev/null; do sleep 15; done; echo "$1 $$" > $LK/owner
  until ! python "$SWI" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
  if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
  while true; do
    if ( set -o noclobber; echo "left-arm-organic $(wpid) $(date +%s) $1" > $SL ) 2>/dev/null; then break; fi
    op=$(awk '{print $2}' $SL 2>/dev/null)
    if [ -n "$op" ] && ! powershell -NoProfile -c "if (Get-Process -Id $op -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"; then
      echo "stale solve lock (PID $op dead): removed $(date +%H:%M)" >> $L; rm -f $SL; continue
    fi
    sleep 30
  done
  until [ "$(free)" -ge 18000 ]; do sleep 60; done; }
unlock() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; date +%s > $STAMP
  grep -q "^left-arm-organic $(wpid) " $SL 2>/dev/null && rm -f $SL
  grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; }
trap 'grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; grep -q "^left-arm-organic $(wpid) " $SL 2>/dev/null && rm -f $SL' EXIT
until grep -q "R1G2R_DONE" $L; do sleep 30; done
echo "R1G4Q (plates Dia 3.8, top 294.7) start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 ARM_PLATE_HOLE_R=1.9 ARM_PLATE_TOP=294.7 HS_D3=1
# 1 hub-seat model (as r1g2 / r1g3, only the plate hole and top differ)
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3S.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_r1g4.SLDPRT
S=$R/_wip/arm-sw-r1g4build
lock r1g4build
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_r1g4.SLDPRT
ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1g4_hs.log 2>&1
unlock "$S"
grep -q "  inserts True" cad/_wip/r1g4_hs.log || { echo "R1G4Q STOP: hub-seat build failed $(tail -3 cad/_wip/r1g4_hs.log | tr '
' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "R1G4Q BUILT model $(date +%H:%M) $(grep -E 'R1F_PLATE' cad/_wip/r1g4_hs.log | tr '
' ' ' | cut -c1-200)" >> $L
# 2 STOP_0, then G90; post / lug / fin control 1.0, bearing faces 0.8 (as r1g2: about 390 k nodes)
unset HS_MODEL
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=1.0 HS_LUGFACE_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3S.SLDPRT HUBSTL=HUB_D3S.STL DS_SOLVER=1 FEA_SAVE_DISP=1
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  bash cad/scripts/fea/r1c/mesh_guard.sh $1 &
  FOLDER=$1 MTAG=r1g4 CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve2.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '
' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
  grep -q "^SOLVED $1" cad/_wip/r1d_ring_ds.log && bash cad/scripts/fea/r1c/post_r1g.sh $1 1.9 294.7 >> $L 2>&1
}
job r1g4_stop0 HS_STOP_0_fine 0.5
job r1g4_g90 HS_G90_fine 0.05
echo "R1G4Q_DONE $(date)" >> $L
