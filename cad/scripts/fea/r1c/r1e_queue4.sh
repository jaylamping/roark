#!/bin/bash
# R1e queue 4 (2026-11-12, 20:30): the shim-body G90 and STOP_0 again with the shim contact set fixed (every arm end face at the
# shim's underside, both halves; before, one half's face stayed globally bonded to the shim and carried the stop's twist).
# One job at a time through r1e_solve1.sh, on the 4.0 mesh.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
echo "R1E_QUEUE4 start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL DS_SOLVER=1 FEA_SAVE_DISP=1 HS_SHIM=0.70 R1C_SHIM=0.70
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=ringg00s70i CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E "shim contact|arm end face for|mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-300) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1e_s70_stop4 HS_STOP_0_fine 0.5
job r1e_s70_g90b HS_G90_fine 0.05
echo "R1E_QUEUE4_DONE $(date)" >> $L
