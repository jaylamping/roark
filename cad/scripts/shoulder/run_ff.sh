#!/bin/bash
# The fork front alone, like for like: REVS="today yoke" CASES="FF_MX ..." bash run_ff.sh
# today = cad/shoulder/left (a copy), anything else = the look build cad/_wip/look/<rev>. Linear cases, 6 GB cap, FFEPlus.
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
L=$W/queue5.log
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CAP="$PY capped.py --mb 6144 --"
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
S=shoulder-study-fea
free_gb() { powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)"; }
trap '$CL release $S > /dev/null 2>&1' EXIT
for REV in ${REVS:-today yoke}; do
  until [ "$(free_gb)" -ge 10 ]; do sleep 60; done
  SRC=../../_wip/look/$REV/shoulder_fork_front_left.SLDPRT
  [ "$REV" = today ] && SRC=../../shoulder/left/shoulder_fork_front_left.SLDPRT
  cp $SRC ../../_sim/shoulder/ff_fea_$REV.SLDPRT
  $CL claim $S --worktree 'J:\code\roark-wt\shoulder-study' --status "FEA fork front $REV" >> $L 2>&1
  echo "start fork front cases on $REV $(date +%T)" >> $L
  [ -n "$EL" ] && export FEA_EL=$EL
  [ -n "$TOL" ] && export FEA_TOL=$TOL
  [ -n "$SUP" ] && export FEA_SUPPRESS=$SUP
  FEA_FACE_CACHE=1 FEA_SOLVER=2 SW_STATE_NAME=.sw_instance_pid_ff_$REV FF_FEA_FILE=ff_fea_$REV.SLDPRT $CAP $PY -u fea_shoulder.py ${CASES:-FF_MX FF_MXn FF_MZ FF_SIDE FF_STOP} > $W/FF_$REV.txt 2>&1 &
  pid=$!
  while kill -0 $pid 2>/dev/null; do
    [ "$(free_gb)" -lt 4 ] && { echo "free memory under 4 GB: stopping my job $(date +%T)" >> $L; kill $pid; }
    SP=$(cut -d" " -f1 $W/.sw_instance_pid_ff_$REV 2>/dev/null)      # my instance, so --status shows the claim against it
    $CL beat $S --status "FEA fork front $REV" ${SP:+--sw-pid $SP} > /dev/null 2>&1
    sleep 10
  done
  wait $pid
  for c in ${CASES:-FF_MX FF_MXn FF_MZ FF_SIDE FF_STOP}; do
    for x in "" _u; do [ -f ../../_sim/shoulder/$c$x.npz ] && mv ../../_sim/shoulder/$c$x.npz ../../_sim/shoulder/${c}_$REV$x.npz; done
  done
  echo "fork front cases on $REV done $(date +%T): $(grep -c '^ solve 0' $W/FF_$REV.txt) solved" >> $L
done
