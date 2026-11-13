#!/bin/bash
# Keep this worktree's claim (tools/pc/claims.py, session left-arm-organic) alive while our queues run: a beat every 4 minutes with
# the queue's last milestone and the SolidWorks PID of the job running now (from its session state file), until R1G6Q_DONE or a
# CLAIM_BEAT_STOP file; then release the claim.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
while [ ! -f cad/_wip/CLAIM_BEAT_STOP ] && ! grep -q "R1G6Q_DONE" $L; do
  pidf=$(ls -t cad/_wip/arm-sw-job-*/.sw_instance_pid 2>/dev/null | head -1)
  sp=""; [ -n "$pidf" ] && sp="--sw-pid $(awk '{print $1}' "$pidf")"
  st="r1g6 queue: $(tail -1 $L | cut -c1-90)"
  python tools/pc/claims.py beat left-arm-organic --status "$st" $sp > /dev/null 2>&1
  sleep 240
done
python tools/pc/claims.py release left-arm-organic > /dev/null 2>&1
