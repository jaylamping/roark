#!/bin/bash
# The RS02 on the fork front as a bolted joint (OPEN_ASSUMPTIONS item 49): R2_* cases on the combined real fork
# (fork2_real.SLDPRT), Intel direct sparse, under the solve lock, hidden, claim with the instance's PID.
#   CASES="R2_MX R2_MXn R2_MZ R2_STOP" [R2_PRE=250] [R2_HEAD_OD=7.0] [TAG=p250] bash run_r2.sh
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
  until [ "$(free_gb)" -ge ${FEA_FREE_GB:-18} ]; do sleep 60; done
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
$LK take "shoulder RS02 on fork" $WP >> $L 2>&1 || { echo "RS02 on fork: no solve lock" >> $L; exit 1; }
TAG=${TAG:-p${R2_PRE:-250}}
for c in ${CASES:-R2_MX}; do
  echo "RS02 on fork $c ($TAG) start $(date +%T)" >> $L
  FEA_SOLVER=7 FEA_EL=${EL:-3.5} FORK2_FEA_FILE=${FORK2:-fork2_real.SLDPRT} job .sw_instance_pid_r2 "RS02 on fork $c" $W/${c}_$TAG.txt $PY capped.py --mb ${FEA_MB:-20480} -- $PY -u fea_shoulder.py $c
  rm -f ../../_sim/shoulder/${c}_$TAG.npz
  grep -q "^ solve 0" $W/${c}_$TAG.txt && for x in "" _u; do [ -f ../../_sim/shoulder/$c$x.npz ] && mv ../../_sim/shoulder/$c$x.npz ../../_sim/shoulder/${c}_$TAG$x.npz; done
  echo "RS02 on fork $c ($TAG) done $(date +%T): $(grep 'mesh \|solve' $W/${c}_$TAG.txt | tr '\n' ' ' | cut -c1-120)" >> $L
done
