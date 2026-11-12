#!/bin/bash
# Combined pass, resumed after the end-face review (2026-11-12, coordinator: keep the 0.5 chamfer, no geometry change). Waits
# for the nominal STOP_0 solve (pid in $1) to finish, then the remaining cases in order. The 0.1 gap STOP_0 repeat carries the
# 0.3 mm lug-root control (flag file cad/_wip/hs_root_mesh/r1d11_g01_stop_rep.txt).
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
while [ -n "$1" ] && kill -0 "$1" 2>/dev/null; do sleep 30; done
echo "RESUMED $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
HUBF=HUB_RING_ZF.SLDPRT; HUBS=HUB_RING_ZF.STL
solve() {
  ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
  FOLDER=$1 MTAG=$2 CASE=$3 PADE=$4 HUBFILE=$HUBF HUBSTL=$HUBS HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
solve r1d11_nom_g90 ringnomzi HS_G90_fine 0.05
solve r1d11_nom_stop124 ringnomzi HS_STOP_124_fine 0.5
solve r1d11_g02_stop ringg02zi HS_STOP_0_fine 0.5
solve r1d11_g01_stop_rep ringg01zi HS_STOP_0_fine 0.5
echo "COMBINED_DONE $(date)" >> $L
