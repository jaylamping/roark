#!/bin/bash
# Combined pass, last case (2026-11-12, coordinator): 0.1 gap STOP_124, the highest lug load with the flank bearing. Waits for
# the extension cases (EXT_DONE).
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
until grep -q "EXT_DONE" $L; do sleep 30; done
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
FOLDER=r1d11_g01_stop124 MTAG=ringg01zi CASE=HS_STOP_124_fine PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
echo "CASE_DONE r1d11_g01_stop124 $(date +%H:%M) $(grep -E "^(SOLVED|SOLVE_FAILED) r1d11_g01_stop124" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
echo "EXT2_DONE $(date)" >> $L
