#!/bin/bash
# After r1g5 (coordinator 18:31Z): one queue, one SolidWorks job at a time, both locks, 14 GB gate.
#   1. r1g5 STOP_0 and STOP_124 again (a refused launch and an old-rule memory stop), then G90 + YAW +17; "used" = our own process
#      tree, stopped at 15 GB (MEMSTOP_USED=15360), the free stop 2 GB, launch at 14 GB (coordinator 19:35Z)
#   2. R1h back half: the R1g build plus the harness tie bridge (ARM_TIE_BRIDGE=1), into cad/_wip/r1d_r1h_print; slice, mesh gate;
#      the front half stays R1g (its files unchanged)
#   3. the convergence run, last: r1g4 G90 + YAW +17 with local refinement 0.5 (HS_LOCAL_REFINE) at the plate outline corners, the
#      end-face corner and the PETG ring by the inserts; for this job only the "used" stop is 15 GB, the free stop 2 GB, launch at
#      20 GB free. If the mesher or memory refuses, it is recorded and not retried.
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
until grep -q "R1G5Q_DONE" $L; do sleep 30; done
echo "R1HQ start $(date +%H:%M)" >> $L
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 ARM_PLATE_HOLE_R=1.9 ARM_PLATE_TOP=294.7 HS_D3=1
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=1.0 HS_LUGFACE_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export DS_SOLVER=1 FEA_SAVE_DISP=1
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  bash cad/scripts/fea/r1c/mesh_guard.sh $1 &
  FOLDER=$1 MTAG=$4 CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve3.sh      # own-process-tree memory (coordinator 19:35Z)
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '
' ' ' | cut -c1-260) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
  grep -q "^SOLVED $1" cad/_wip/r1d_ring_ds.log && bash cad/scripts/fea/r1c/post_r1g.sh $1 1.9 294.7 >> $L 2>&1
}
# 1. r1g5 G90 + YAW +17
# r1g5 STOP_0 again: its first launch (12:50) was refused by sw_instance's busy-instance guard (another session's SolidWorks, PID 12852, not answering)
HUBFILE=HUB_D3S38.SLDPRT HUBSTL=HUB_D3S38.STL job r1g5_stop0 HS_STOP_0_fine 0.5 r1g5
# r1g5 STOP_124 again: its first run (13:03) hit the old 12 GB machine-wide "used" stop with 8.8 GB still free
HUBFILE=HUB_D3S38.SLDPRT HUBSTL=HUB_D3S38.STL job r1g5_stop124 HS_STOP_124_fine 0.5 r1g5
HUBFILE=HUB_D3S38.SLDPRT HUBSTL=HUB_D3S38.STL job r1g5_g90y HS_G90Y_fine 0.05 r1g5
# 2. R1h back half
S=$R/_wip/arm-sw
lock r1hbuild
(export ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_WIP_TAG=_r1h_print ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_END_DROP=0.70 ARM_SEAM_LEADIN=0.1,2.0 ARM_TIE_BRIDGE=1
 unset ARM_PLATE_LUMP ARM_PLATE_HOLE_R ARM_PLATE_TOP HS_D3
 bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:back"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1h_build_rebuild.log)
date +%s > $STAMP
grep -q "^left-arm-organic $(wpid) " $SL 2>/dev/null && rm -f $SL
grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK
if grep -q "STOP at" cad/_wip/r1h_build_rebuild.log; then echo "R1H BUILD_FAILED $(grep -iE 'STOP at|error|traceback|R1H' cad/_wip/r1h_build_rebuild.log | tail -4 | tr '
' ' ' | cut -c1-300)" >> $L
else
  echo "R1H BUILT back half $(date +%H:%M) $(grep -E 'R1H' cad/_wip/r1h_build_rebuild.log | tr '
' ' ' | cut -c1-300)" >> $L
  X=$R/_wip/r1d_r1h_print
  mkdir -p $X/exports $X/checks
  cp -p $R/_wip/r1d_r1g_print/exports/upper_arm_organic_front_left.STL $R/_wip/r1d_r1g_print/exports/upper_arm_organic_rs02_ring_left.STL $X/exports/
  (cd cad/scripts/arm && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print ARM_PRINT_SUFFIX=_r1h ARM_PRINT_HUBBAND_Y0=274.0 ARM_PRINT_FLANK_BLOCKER=1 ARM_FLANK_GAP=0 $PYC organic_print.py back > $X/slice.log 2>&1)
  (cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print PRINT_WHITELIST=$R/reviews/upper-arm/20261111_r1c-delta/r1d/r1e/print_whitelist.json $PYC print_check.py back > $X/print_check.log 2>&1)
  echo "R1H SLICED+GATED $(grep -E '"job"' $X/print_check.log | sed -E 's/.*"job": "([a-z]+)", "mesh_gate": "([A-Z]+)".*"time_s": ([0-9]+), "grams": ([0-9.]+).*/  s g/' | tr '
' ' ')" >> $L
fi
# 3. convergence run (last)
MEMSTOP_USED=15360 MINFREE=20000 HS_LOCAL_REFINE=0.5 HUBFILE=HUB_D3S.SLDPRT HUBSTL=HUB_D3S.STL job r1g4_g90y_ref HS_G90Y_fine 0.05 r1g4
echo "R1HQ_DONE $(date)" >> $L
