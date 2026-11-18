#!/bin/bash
# Hub candidate from a copy of the released part (hub_candidate_mod.py), hidden, with a claim.   V=hubNS bash run_hub_mod.sh
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
$CL claim shoulder-study-fea --worktree 'J:\code\roark-wt\shoulder-study' --status "hub candidate $V (modify copy)" > /dev/null 2>&1
trap '$CL release shoulder-study-fea > /dev/null 2>&1' EXIT
echo "start hub candidate $V (modify copy) $(date +%T)" >> $W/queue5.log
SW_VISIBLE=0 SW_STATE_NAME=.sw_instance_pid_$V LOOK=$V $PY capped.py --mb 6144 -- $PY -u ${SCRIPT:-hub_candidate_mod.py} > $W/build_$V.txt 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  SP=$(cut -d" " -f1 $W/.sw_instance_pid_$V 2>/dev/null)
  $CL beat shoulder-study-fea ${SP:+--sw-pid $SP} > /dev/null 2>&1
  sleep 5
done
wait $pid
echo "hub candidate $V done $(date +%T): $(grep 'integrity\|== shoulder' $W/build_$V.txt | tr '\n' ' ' | cut -c1-220)" >> $W/queue5.log
