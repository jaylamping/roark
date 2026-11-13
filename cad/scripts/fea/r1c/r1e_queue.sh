#!/bin/bash
# R1e FEA queue, one process, one job at a time (2026-11-12). Every job goes through r1e_solve1.sh (own session folder, launch
# lock held until end_session, 3 min gap, >= 16 GB free). Hand-off: waits for the STOP_124 run already in progress (its
# r1d_ring_ds_solve.sh, pid given as $1) to exit, rather than racing it.
#   1. YAW +17, YAW -17 (HS_LC2 / HS_LC2M) on the 0 gap lumped model, lug roots 0.5 at global 5.0
#   2. STOP_0 again (its 17:57 run was stopped when another thread's job took the free RAM)
#   3. shim-body STOP_0: mesh probes, then the solve with the first under NMAX nodes
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
NMAX=${NMAX:-410000}
PREV=${1:-}
[ -n "$PREV" ] && while [ -e /proc/$PREV ]; do sleep 15; done
echo "R1E_QUEUE start $(date +%H:%M) (previous run ${PREV:-none} exited)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL DS_SOLVER=1 FEA_SAVE_DISP=1 PADE=0.5
job() {      # folder model case [root spec]
  [ -n "$4" ] && echo "$4" > cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=$2 CASE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0|shim contact|displacements saved" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-240) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1e_g00_yawp ringg00zi HS_LC2_fine "0.5,20,5.0"
job r1e_g00_yawm ringg00zi HS_LC2M_fine "0.5,20,5.0"
echo "R1E_YAW_DONE $(date)" >> $L
grep -q "^SOLVED r1e_g00_stop124_b" cad/_wip/r1d_ring_ds.log || job r1e_g00_stop124_c ringg00zi HS_STOP_124_fine "0.5,20,5.0"
job r1e_g00_stop_c ringg00zi HS_STOP_0_fine "0.5,20,5.0"
# shim body: probe, then solve
export HS_SHIM=0.70 R1C_SHIM=0.70
CH=""
for spec in "0.4,20,5.0" "0.5,20,5.0" "0.6,20,5.5"; do
  FOLDER=r1e_s70_probe MTAG=ringg00s70i CASE=HS_STOP_0_fine FEA_MESH_ONLY=1 HS_ROOT_MESH=$spec bash cad/scripts/fea/r1c/r1e_solve1.sh
  n=$(grep -oE "mesh 0 nodes [0-9]+" cad/_sim/r1e_s70_probe/run.log | grep -oE "[0-9]+$")
  echo "PROBE r1e s70 root $spec: nodes ${n:-?}" >> $L
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then CH=$spec; break; fi
done
if [ -n "$CH" ]; then job r1e_s70_stop2 ringg00s70i HS_STOP_0_fine "$CH"; else echo "ROOT_REFINE s70: nothing under $NMAX nodes; not solving" >> $L; fi
echo "R1E_QUEUE_DONE $(date)" >> $L
