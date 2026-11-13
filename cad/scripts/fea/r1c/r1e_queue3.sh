#!/bin/bash
# R1e queue 3 (2026-11-12, 18:55): the lug-root refinement (0.5 on the root faces at global 5.0) gives a broken local mesh at the hub
# spigot underside by the -X lug (7-9 GPa, hub nodes moving 1-2.6 mm, in STOP_0_b, STOP_124_b and YAW +17 alike; G90 at 4.0
# without it is clean). So the cases run on the mesh G90 showed sane: global 4.0, 0.8 on seat / posts / lugs / fins, no root
# control. One job at a time through r1e_solve1.sh.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
echo "R1E_QUEUE3 start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL DS_SOLVER=1 FEA_SAVE_DISP=1 PADE=0.5
job() {      # folder model case
  rm -f cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=$2 CASE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0|shim contact" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-240) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1e_g00_yawp3 ringg00zi HS_LC2_fine
job r1e_g00_yawm3 ringg00zi HS_LC2M_fine
echo "R1E_YAW_DONE $(date)" >> $L
job r1e_g00_stop124_d ringg00zi HS_STOP_124_fine
job r1e_g00_stop_d ringg00zi HS_STOP_0_fine
export HS_SHIM=0.70 R1C_SHIM=0.70
job r1e_s70_stop3 ringg00s70i HS_STOP_0_fine
echo "R1E_QUEUE_DONE $(date)" >> $L
