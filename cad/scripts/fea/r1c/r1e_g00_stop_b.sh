#!/bin/bash
# R1e: 0 gap STOP_0 again with the lug-root control limited to the fillet faces (0.3 mm on faces under 20 mm2). The first try
# (r1e_g00_stop) put 0.3 on the whole lug faces too, 1.18 M nodes, and the memory watch stopped it cleanly. After the shim cases.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
until grep -q "R1E_SHIM_DONE" $L; do sleep 30; done
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
echo "0.3,20" > cad/_wip/hs_root_mesh/r1e_g00_stop_b.txt
FOLDER=r1e_g00_stop_b MTAG=ringg00zi CASE=HS_STOP_0_fine PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
echo "CASE_DONE r1e_g00_stop_b $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/r1e_g00_stop_b/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) r1e_g00_stop_b" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
echo "R1E_STOPB_DONE $(date)" >> $L
