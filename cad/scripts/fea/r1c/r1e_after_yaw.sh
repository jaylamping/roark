#!/bin/bash
# After the yaw cases and STOP_124 (r1e_yaw.sh): the 0 gap STOP_0 again (its 17:57 run was stopped by the memory watch when another
# thread's job took the free RAM), then the shim-body STOP_0 (r1e_shim_stop2.sh: probes, then the solve).
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
until grep -q "R1E_STOPB_DONE .*(after the yaw cases)" $L; do sleep 30; done
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
echo "0.5,20,5.0" > cad/_wip/hs_root_mesh/r1e_g00_stop_c.txt
FOLDER=r1e_g00_stop_c MTAG=ringg00zi CASE=HS_STOP_0_fine PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 FEA_SAVE_DISP=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
echo "CASE_DONE r1e_g00_stop_c $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/r1e_g00_stop_c/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) r1e_g00_stop_c" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
bash cad/scripts/fea/r1c/r1e_shim_stop2.sh
