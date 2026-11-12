#!/bin/bash
# R1d gap cases with soft bonded pads (soft springs crash SolidWorks here). Waits for the tapered arm builds, builds the pad
# hub-seat models for the 0.1 and 0.2 gap variants, then solves in priority order (no hard timeouts; stops on HUNG_PID).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_pads.log
echo "start $(date)" >> $L
until grep -qE "BUILT tprint|BUILD_FAILED|HUB_BUILD_FAILED|STOPPED|ALL_DONE" cad/_wip/r1d_tapered.log 2>/dev/null; do sleep 30; done
sleep 20
pkill -f r1d_tapered_all.sh 2>/dev/null; powershell -NoProfile -c "Get-CimInstance Win32_Process | ? { \$_.CommandLine -match 'r1d_tapered_all' } | % { Stop-Process -Id \$_.ProcessId -Confirm:\$false }" 2>/dev/null
echo "tapered builds: $(grep -E 'BUILT|FAILED' cad/_wip/r1d_tapered.log | tr '\n' ' ')" >> $L
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_PADS=1 HS_PAD_E=0.05
for t in tg01 tg02; do
  ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_$t.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_${t}p.SLDPRT ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_${t}p.log 2>&1
  (cd cad/scripts/arm && ARM_SW_DIR="$R/_wip/arm-sw-hub" python -c "from swlib import finish; finish()") >> $L 2>&1
  ls cad/_sim/ua2/UA_HUBSEAT_r1d_${t}p.SLDPRT >/dev/null 2>&1 && echo "BUILT ${t}p $(grep -c 'PAD' cad/_wip/r1d_hub_${t}p.log) pad lines" >> $L || { echo "HUB_BUILD_FAILED ${t}p" >> $L; exit 1; }
done
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "tg01p:HS_STOP_0_fine:r1d5_tg01p_stop:arm-sw-fea:0" "tg01p:HS_G90_fine:r1d5_tg01p_g90:arm-sw-fea:0" "tg02p:HS_STOP_0_fine:r1d5_tg02p_stop:arm-sw-fea:0" "tg02p:HS_G90_fine:r1d5_tg02p_g90:arm-sw-fea:0" "tnom:HS_STOP_0_fine:r1d5_tnom_stop:arm-sw-fea:0" "tnom:HS_G90_fine:r1d5_tnom_g90:arm-sw-fea:0" "tg01p:HS_STOP_124_fine:r1d5_tg01p_stop124:arm-sw-fea:0" "tg01p:HS_STOP_0_fine:r1d5_tg01p_stop_rep:arm-sw-fea:0" "tg01p:HS_STOP_0_fine:r1d5_tg01p_stop_m25:arm-sw-fea:0:0.25"
echo "PADS_DONE $(date)" >> $L
