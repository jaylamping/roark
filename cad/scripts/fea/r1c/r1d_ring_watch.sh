#!/bin/bash
# Watchdog for option c (ring 0.8 mm): if one contact iteration lasts > 20 min, stop cleanly, 3-min gap, re-run with direct sparse.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_ring.log; D=cad/_sim/r1d8_ringg01p_stop_m80
last=""; since=$(date +%s)
while true; do
  grep -q "SOLVED r1d8_ringg01p_stop_m80\|SOLVE_FAILED r1d8_ringg01p_stop_m80" cad/_wip/r1d_chain4.log && { echo "WATCH_END $(date +%H:%M)" >> $L; exit 0; }
  it=$(cat $D/*.OUT 2>/dev/null | grep "CONTACT ITERATION NUMBER" | tail -1 | tr -dc '0-9')
  if [ "$it" != "$last" ]; then last=$it; since=$(date +%s); fi
  if [ -n "$it" ] && [ $(( $(date +%s) - since )) -gt 1200 ]; then
    echo "WATCH_STALL $(date +%H:%M): iteration $it for 20 min; switching to direct sparse" >> $L
    powershell -NoProfile -c "Get-CimInstance Win32_Process | ? { (\$_.CommandLine -match 'r1d_ring_c.sh|r1d_chain4.sh|organic_fea') -and \$_.CommandLine -notmatch 'source |tail|r1d_ring_watch' } | % { Stop-Process -Id \$_.ProcessId -Confirm:\$false -ErrorAction SilentlyContinue }"
    sleep 3; (cd cad/scripts/arm && ARM_SW_DIR=J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-fea python -c "from swlib import finish; finish()") >> $L 2>&1
    sleep 180
    export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT R1C_RING=1 HUB_STL_NAME=HUB_GROOVE_RING.STL HS_SEAT_MESH_AMAX=600 FEA_SOLVER=${FEA_SOLVER_DIRECT:-1}
    R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "ringg01p:HS_STOP_0_fine:r1d8_ringg01p_stop_m80ds:arm-sw-fea:0:0.8"
    echo "DIRECT_DONE $(date)" >> $L; exit 0
  fi
  sleep 60
done
