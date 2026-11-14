#!/bin/bash
# One look build:  V=<look name> PARTS="fork_front ..." bash look_build.sh
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CAP="$PY capped.py --mb 6144 --"
free_gb() { powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)"; }
until [ "$(free_gb)" -ge 10 ]; do sleep 30; done
echo "start look build $V ($PARTS) $(date +%T)" >> $W/queue5.log
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
$CL claim shoulder-study-fea --worktree 'J:\codeoark-wt\shoulder-study' --status "look build $V" > /dev/null 2>&1
trap '$CL release shoulder-study-fea > /dev/null 2>&1' EXIT
SW_STATE_NAME=.sw_instance_pid_$V LOOK=$V $CAP $PY -u build_parts.py $PARTS > $W/build_$V.txt 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  SP=$(cut -d" " -f1 $W/.sw_instance_pid_$V 2>/dev/null)
  $CL beat shoulder-study-fea ${SP:+--sw-pid $SP} > /dev/null 2>&1
  sleep 10
done
wait $pid
echo "look build $V done $(date +%T): $(grep 'integrity\|== shoulder' $W/build_$V.txt | tr '\n' ' ' | cut -c1-220)" >> $W/queue5.log
