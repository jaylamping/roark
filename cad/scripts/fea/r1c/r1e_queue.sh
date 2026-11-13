#!/bin/bash
# R1e FEA queue, one process, one job at a time (2026-11-12). Every job goes through r1e_solve1.sh (own session folder, launch
# lock held until end_session, 3 min gap, >= 16 GB free).
# Bore mesh (2026-11-12, evening): global sizes over 3.0 now put 1.5 on the bore / spigot cylinders (hub_seat.py HS_BORE_MESH);
# at 5.0 their facets overlapped the 0.05 radial clearance and STOP_124_b came out at 8.8 GPa. Each model is mesh-probed first.
#   1. YAW +17, YAW -17 (HS_LC2 / HS_LC2M) on the 0 gap lumped model
#   2. STOP_124 and STOP_0 again, then G90 again (its 4.0 mesh sagged about 0.056 against the 0.05 clearance: check)
#   3. shim-body STOP_0
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
NMAX=${NMAX:-410000}
echo "R1E_QUEUE2 start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL DS_SOLVER=1 FEA_SAVE_DISP=1 PADE=0.5
probe() {      # model case -> echoes the first root spec under NMAX nodes (or nothing)
  for spec in "0.5,20,5.0" "0.6,20,5.0" "0.6,20,5.5"; do
    FOLDER=r1e_probe_$1 MTAG=$1 CASE=$2 FEA_MESH_ONLY=1 HS_ROOT_MESH=$spec bash cad/scripts/fea/r1c/r1e_solve1.sh >/dev/null 2>&1
    n=$(grep -oE "mesh 0 nodes [0-9]+" cad/_sim/r1e_probe_$1/run.log | grep -oE "[0-9]+$")
    echo "PROBE $1 root $spec: nodes ${n:-?} $(grep -E ' control ' cad/_sim/r1e_probe_$1/run.log | tr '\n' ' ' | cut -c1-140)" >> $L
    if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then echo "$spec"; return; fi
  done
}
job() {      # folder model case root-spec
  echo "$4" > cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=$2 CASE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0|shim contact|displacements saved" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-260) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
CH=$(probe ringg00zi HS_LC2_fine)
[ -z "$CH" ] && { echo "ROOT_REFINE g00: nothing under $NMAX nodes with the bore control; stopping" >> $L; exit 1; }
job r1e_g00_yawp2 ringg00zi HS_LC2_fine "$CH"
job r1e_g00_yawm2 ringg00zi HS_LC2M_fine "$CH"
echo "R1E_YAW_DONE $(date)" >> $L
job r1e_g00_stop124_c ringg00zi HS_STOP_124_fine "$CH"
job r1e_g00_stop_c ringg00zi HS_STOP_0_fine "$CH"
PADE=0.05 job r1e_g00_g90_c ringg00zi HS_G90_fine "$CH"
export HS_SHIM=0.70 R1C_SHIM=0.70
CS=$(probe ringg00s70i HS_STOP_0_fine)
if [ -n "$CS" ]; then job r1e_s70_stop2 ringg00s70i HS_STOP_0_fine "$CS"; else echo "ROOT_REFINE s70: nothing under $NMAX nodes; not solving" >> $L; fi
echo "R1E_QUEUE_DONE $(date)" >> $L
