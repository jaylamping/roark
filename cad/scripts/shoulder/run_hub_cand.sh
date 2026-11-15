#!/bin/bash
# FE cases on a hub look variant (a candidate), each on its own copy of the look part, under the solve lock, hidden,
# claim with the instance's PID. Bolted-contact cases (HUBB_*) on Intel direct sparse at element 2.6, as the D3c7 record.
#   V=hubNS TAG=revNS CASES="HUBB_Ah HUBL_G90YAWP_MAX" bash run_hub_cand.sh
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
L=$W/queue5.log
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
LK="$PY C:/joe/code/roark-wt/shoulder-study/cad/_wip/shoulder-pass1/solve_lock.py"
S=shoulder-study-fea
WP=$(cat /proc/$$/winpid)
export SW_VISIBLE=0 HUB_LUG_D=3.8
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
$LK take "shoulder hub candidate $V" $WP >> $L 2>&1 || { echo "hub candidate: no solve lock" >> $L; exit 1; }
for c in $CASES; do
  echo "hub candidate $V $c start $(date +%T)" >> $L
  cp ../../_wip/look/$V/shoulder_hub_left.SLDPRT ../../_sim/shoulder/hub_fea_${TAG}_$c.SLDPRT
  case $c in
    HUBB_*) SOLV=7; ELV=${EL_HUBB:-2.6} ;;
    *) SOLV=2; ELV= ;;
  esac
  if [ -n "$ELV" ]; then export FEA_EL=$ELV; else unset FEA_EL; fi
  FEA_SOLVER=$SOLV HUB_FEA_FILE=hub_fea_${TAG}_$c.SLDPRT job .sw_instance_pid_hc "hub candidate $V $c" $W/${c}_$TAG.txt $PY capped.py --mb 14336 -- $PY -u fea_shoulder.py $c
  rm -f ../../_sim/shoulder/${c}_$TAG.npz; grep -q "^ solve 0" $W/${c}_$TAG.txt && cp ../../_sim/shoulder/$c.npz ../../_sim/shoulder/${c}_$TAG.npz
  echo "hub candidate $V $c done $(date +%T): $(grep 'mesh \|solve' $W/${c}_$TAG.txt | tr '\n' ' ' | cut -c1-120)" >> $L
done
