#!/bin/bash
# After run_p.sh: the combined fork parts and the F2_* cases for each analysis build.
cd /j/code/roark-wt/shoulder-study/cad/_wip/shoulder-pass1
until grep -q "proper check all done" queue5.log; do sleep 20; done
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
L=$W/queue5.log
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CAP="$PY capped.py --mb 6144 --"
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
S=shoulder-study-fea
free_gb() { powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)"; }
trap '$CL release $S > /dev/null 2>&1' EXIT
job() {
  local st=$1 status=$2 out=$3; shift 3
  until [ "$(free_gb)" -ge 10 ]; do sleep 60; done
  $CL claim $S --worktree 'J:\code\roark-wt\shoulder-study' --status "$status" > /dev/null 2>&1
  SW_STATE_NAME=$st "$@" > $out 2>&1 &
  local pid=$!
  while kill -0 $pid 2>/dev/null; do
    SP=$(cut -d" " -f1 $W/$st 2>/dev/null)
    $CL beat $S --status "$status" ${SP:+--sw-pid $SP} > /dev/null 2>&1
    sleep 10
  done
  wait $pid
}
CASES_F=${CASES_F:-F2_MX F2_MXn F2_MXs F2_MZ F2_STOP}
for T in ${TAGS:-ffT ffTS ffYS}; do
  job .sw_instance_pid_f2_$T "fork2 part $T" $W/fork2_$T.txt $CAP $PY -u fork2_fea_part.py $T
  echo "  $T combined: $(grep 'volume kept\|did not combine\|Error' $W/fork2_$T.txt | cut -c1-110)" >> $L
  grep -q "volume kept" $W/fork2_$T.txt || continue
  FEA_FACE_CACHE=1 FEA_SOLVER=2 FEA_EL=2.0 FORK2_FEA_FILE=fork2_$T.SLDPRT job .sw_instance_pid_f_$T "FEA two-body $T" $W/F_$T.txt $CAP $PY -u fea_shoulder.py $CASES_F
  for c in $CASES_F; do
    for x in "" _u; do [ -f ../../_sim/shoulder/$c$x.npz ] && mv ../../_sim/shoulder/$c$x.npz ../../_sim/shoulder/${c}_$T$x.npz; done
  done
  echo "two-body $T done $(date +%T): $(grep -c '^ solve 0' $W/F_$T.txt) solved of $(echo $CASES_F | wc -w)" >> $L
done
echo "two-body all done $(date +%T)" >> $L
