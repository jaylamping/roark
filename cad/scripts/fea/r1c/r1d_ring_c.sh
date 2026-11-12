#!/bin/bash
# Option c): if the ring 0.5 mm STOP_0 has not finished by 07:00 local, stop it cleanly, 3-min gap, re-run at 0.8 mm seat mesh.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_ring.log
until grep -q "SOLVED r1d8_ringg01p_stop\|SOLVE_FAILED r1d8_ringg01p_stop" cad/_wip/r1d_chain4.log || [ "$(date +%H%M)" -ge 0700 ]; do sleep 30; done
grep -q "SOLVED r1d8_ringg01p_stop" cad/_wip/r1d_chain4.log && { echo "C_NOT_NEEDED $(date +%H:%M)" >> $L; exit 0; }
echo "C_CUTOFF $(date +%H:%M): stopping the 0.5 mm ring solve" >> $L
powershell -NoProfile -c "Get-CimInstance Win32_Process | ? { (\$_.CommandLine -match 'r1d_ring_solve.sh|r1d_chain4.sh|organic_fea') -and \$_.CommandLine -notmatch 'source |tail|r1d_ring_c' } | % { Stop-Process -Id \$_.ProcessId -Confirm:\$false -ErrorAction SilentlyContinue }"
sleep 3
(cd cad/scripts/arm && ARM_SW_DIR=J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-fea python -c "from swlib import finish; finish()") >> $L 2>&1
sleep 180
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT R1C_RING=1 HUB_STL_NAME=HUB_GROOVE_RING.STL HS_SEAT_MESH_AMAX=600
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "ringg01p:HS_STOP_0_fine:r1d8_ringg01p_stop_m80:arm-sw-fea:0:0.8"
echo "C_DONE $(date)" >> $L
