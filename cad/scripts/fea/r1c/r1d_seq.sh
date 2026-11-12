#!/bin/bash
# R1d solves one at a time (a SolidWorks launch waits while another instance is busy in a long call: PR #66 guard).
# 0.5 mm seat mesh control as the working size; a 0.35 mm check restricted to faces <= 60 mm2 at the end.
cd /j/code/roark-wt/left-arm-organic
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh \
  "tg01p:HS_STOP_0_fine:r1d6_tg01p_stop:arm-sw-fea:0:0.5" \
  "tg01p:HS_G90_fine:r1d6_tg01p_g90:arm-sw-fea:0:0.5" \
  "tg02p:HS_STOP_0_fine:r1d6_tg02p_stop:arm-sw-fea:0:0.5" \
  "tg02p:HS_G90_fine:r1d6_tg02p_g90:arm-sw-fea:0:0.5" \
  "tnom:HS_STOP_0_fine:r1d6_tnom_stop:arm-sw-fea:0:0.5" \
  "tnom:HS_G90_fine:r1d6_tnom_g90:arm-sw-fea:0:0.5" \
  "tg01p:HS_STOP_124_fine:r1d6_tg01p_stop124:arm-sw-fea:0:0.5" \
  "tg01p:HS_STOP_0_fine:r1d6_tg01p_stop_rep:arm-sw-fea:0:0.5"
HS_SEAT_MESH_AMAX=60 R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "tg01p:HS_STOP_0_fine:r1d6_tg01p_stop_m35:arm-sw-fea:0:0.35"
echo "SEQ_DONE $(date)" >> cad/_wip/r1d_chain4.log
