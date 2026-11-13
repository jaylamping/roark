#!/bin/bash
# Hold our FEA queue for the shoulder thread's D3b hub build (coordinator, 2026-11-13): take the one-job lock as soon as the
# running job (r1g_g90) releases it, keep it with no SolidWorks of ours alive until another instance has launched and gone
# (or 30 min), then release it so the r1g2 / r1g3 re-runs continue.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
until grep -q "r1g_g90" $LK/owner 2>/dev/null; do sleep 5; done
until mkdir $LK 2>/dev/null; do sleep 1; done
echo "pause_for_shoulder $$" > $LK/owner
echo "PAUSE for the shoulder thread's D3b build $(date +%H:%M) (lock held, no instance of ours)" >> $L
t0=$(date +%s); seen=0
while [ $(( $(date +%s) - t0 )) -lt 1800 ]; do
  n=$(python "$SWI" --status 2>/dev/null | awk 'NR>1 && $1 ~ /^[0-9]+$/' | wc -l)
  if [ "$n" -gt 0 ]; then seen=1; fi
  if [ "$seen" = 1 ] && [ "$n" -eq 0 ]; then echo "PAUSE: the other build's instance came and went $(date +%H:%M)" >> $L; break; fi
  sleep 20
done
[ "$seen" = 0 ] && echo "PAUSE: no other instance appeared in 30 min" >> $L
date +%s > cad/_wip/.fea_job_last_end
grep -q " $$\$" $LK/owner && rm -rf $LK
echo "RESUME $(date +%H:%M)" >> $L
