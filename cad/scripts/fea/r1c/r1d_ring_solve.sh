#!/bin/bash
# Ring 0.1 gap STOP_0 with the mesh control reaching the ring's continuous ridge and groove faces (up to 600 mm2).
cd /j/code/roark-wt/left-arm-organic
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT R1C_RING=1 HUB_STL_NAME=HUB_GROOVE_RING.STL HS_SEAT_MESH_AMAX=600
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "ringg01p:HS_STOP_0_fine:r1d8_ringg01p_stop:arm-sw-fea:0:0.5"
echo "RING_SOLVE_DONE $(date)" >> cad/_wip/r1d_ring.log
