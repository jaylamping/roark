#!/bin/bash
# "M" (2026-11-12): ring 0.1 gap hub-seat model with the lug bolt joint as built (HS_INSERT_MODEL: brass insert in the front
# post, bolt bonded in it, head and shank in no-penetration contact in the back post), then the 0.1 gap STOP_0 with the post/lug
# control, Intel direct sparse set by macro. One SolidWorks job at a time, 3-minute gaps, clean closes.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring_insert.log
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_WIP_TAG=_ring_g01 ARM_FLANK_GAP=0.1 ARM_RIB_PROUD=0 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g01.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_ringg01i.SLDPRT CAD_WRITER='upper-arm-r1:2bcc415b'
echo "start $(date)" >> $L
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED (HUNG_PID)" >> $L; exit 1; }
waitfree
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01i.SLDPRT
ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_ringg01i.log 2>&1; fin "$R/_wip/arm-sw-hub"
grep -q "  inserts True" cad/_wip/r1d_hub_ringg01i.log && grep -q "  pads True" cad/_wip/r1d_hub_ringg01i.log || { echo "HUB_BUILD_FAILED $(tail -3 cad/_wip/r1d_hub_ringg01i.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "BUILT ringg01i $(date +%H:%M) $(grep -E 'bolt bodies|insert bodies|  inserts' cad/_wip/r1d_hub_ringg01i.log | tr '\n' ' ' | cut -c1-300)" >> $L
sleep 180
FOLDER=r1d10_ringg01i_stop MTAG=ringg01i CASE=HS_STOP_0_fine PADE=0.5 HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
echo "INSERT_RUN_DONE $(date +%H:%M)" >> $L
