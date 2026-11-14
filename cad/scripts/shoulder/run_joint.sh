#!/bin/bash
# The six-screw joint check (OPEN_ASSUMPTIONS item 41): the real fork front and fork rear as two bodies (forkj_real.SLDPRT),
# J_* cases, Intel direct sparse, under the solve lock, hidden, claim with the instance's PID.
#   CASES="J_MX ..." [NOBUILD=1] [J_PRE=400] bash run_joint.sh
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
L=$W/queue5.log
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
LK="$PY C:/joe/code/roark-wt/shoulder-study/cad/_wip/shoulder-pass1/solve_lock.py"
S=shoulder-study-fea
WP=$(cat /proc/$$/winpid)
export SW_VISIBLE=0
free_gb() { powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)"; }
trap '$LK drop $WP >> $L 2>&1; $CL release $S > /dev/null 2>&1' EXIT
job() {
  local st=$1 status=$2 out=$3; shift 3
  until [ "$(free_gb)" -ge 10 ]; do sleep 60; done
  $CL claim $S --worktree 'J:\code\roark-wt\shoulder-study' --status "$status" > /dev/null 2>&1
  SW_STATE_NAME=$st "$@" > $out 2>&1 &
  local pid=$!
  while kill -0 $pid 2>/dev/null; do
    [ "$(free_gb)" -lt 4 ] && { echo "free memory under 4 GB: stopping my job $(date +%T)" >> $L; kill $pid; }
    SP=$(cut -d" " -f1 $W/$st 2>/dev/null)
    $CL beat $S --status "$status" ${SP:+--sw-pid $SP} > /dev/null 2>&1
    sleep 10
  done
  wait $pid
}
if [ -z "$NOBUILD" ]; then
  FORK2_NOCOMBINE=1 job .sw_instance_pid_fj "joint check: two-body part" $W/forkj_real.txt $PY capped.py --mb 6144 -- $PY -u fork2_fea_part.py real
  grep "two bodies\|rror" $W/forkj_real.txt | cut -c1-120
fi
$LK take "shoulder fork joint" $WP >> $L 2>&1 || { echo "joint check: no solve lock" >> $L; exit 1; }
TAG=${TAG:-p${J_PRE:-400}}
for c in ${CASES:-J_MX}; do
  echo "joint check $c ($TAG) start $(date +%T)" >> $L
  FEA_FACE_CACHE=1 FEA_SOLVER=7 FEA_EL=${EL:-3.5} J_CTRL=${JC:-1.5} job .sw_instance_pid_j "joint check $c" $W/${c}_$TAG.txt $PY capped.py --mb 14336 -- $PY -u fea_shoulder.py $c
  for x in "" _u; do [ -f ../../_sim/shoulder/$c$x.npz ] && mv ../../_sim/shoulder/$c$x.npz ../../_sim/shoulder/${c}_$TAG$x.npz; done
  echo "joint check $c ($TAG) done $(date +%T): $(grep 'mesh \|solve' $W/${c}_$TAG.txt | tr '\n' ' ' | cut -c1-120)" >> $L
done
