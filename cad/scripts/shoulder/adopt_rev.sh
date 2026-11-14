#!/bin/bash
# Adoption of 2026-11-14: fork front as the yoke (solid neck, root cone), flange ring with rolled rim B, fork rear with the
# LEG2 section, the yoke's single access plug, and the optional dark cover ring. The defaults are already switched in
# dims.py / envelope.py; this script builds the REAL parts, sweeps them, runs the four gating combined cases on the real
# set and writes the exports. Hidden windows, one SolidWorks instance at a time, claim with the instance's PID.
#   bash adopt_yoke.sh build | sweep | fea | exports
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
L=$W/queue5.log
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CAP="$PY capped.py --mb 6144 --"
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
S=shoulder-study-fea
export SW_VISIBLE=0
unset LOOK LEG2 FORK_YOKE RIM_B_ON
trap '$CL release $S > /dev/null 2>&1' EXIT
job() {   # job <state name> <status> <log> <command...>
  local st=$1 status=$2 out=$3; shift 3
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
case "$1" in
build)
  echo "adoption (revision): real builds start $(date +%T)" >> $L
  job .sw_instance_pid_adopt "adoption: real builds" $W/build_adopt_rev.txt $CAP $PY -u build_parts.py fork_front fork_rear
  echo "adoption (revision): real builds done $(date +%T): $(grep -c 'PASS. integrity' $W/build_adopt_rev.txt) of 2 pass the integrity scan" >> $L
  grep "integrity\|== shoulder" $W/build_adopt_rev.txt | cut -c1-150
  ;;
sweep)
  echo "adoption (revision): clearance sweep on the real set start $(date +%T)" >> $L
  CLEAR_JSON=clearance_adopt_rev.json $CAP $PY check_clearance.py > $W/clearance_adopt_rev.txt 2>&1
  echo "adoption (revision): clearance sweep done $(date +%T) exit $?" >> $L
  ;;
fea)
  job .sw_instance_pid_f2_real "adoption: combined part, real set" $W/fork2_real.txt $CAP $PY -u fork2_fea_part.py real
  grep "volume kept\|did not combine" $W/fork2_real.txt
  FEA_FACE_CACHE=1 FEA_SOLVER=2 FEA_EL=2.0 FORK2_FEA_FILE=fork2_real.SLDPRT job .sw_instance_pid_f_real "adoption: combined cases, real set" $W/F_real.txt $CAP $PY -u fea_shoulder.py F2_MX F2_MXn F2_MZ F2_STOP
  for c in F2_MX F2_MXn F2_MZ F2_STOP; do for x in "" _u; do [ -f ../../_sim/shoulder/$c$x.npz ] && mv ../../_sim/shoulder/$c$x.npz ../../_sim/shoulder/${c}_real$x.npz; done; done
  echo "adoption (revision): combined cases on the real set done $(date +%T): $(grep -c '^ solve 0' $W/F_real.txt) solved of 4" >> $L
  ;;
exports)
  cd /j/code/roark-wt/shoulder-study
  for k in fork_front:shoulder_fork_front_left fork_rear:shoulder_fork_rear_left; do
    key=${k%%:*}; name=${k##*:}
    cp cad/_wip/shoulder-pass1/step/$key.step cad/exports/shoulder/$name.STEP
    cp cad/_wip/shoulder-pass1/stl/$key.STL cad/exports/shoulder/$name.STL
    for f in STEP STL; do
      $PY tools/cad/record_export.py exports/shoulder/$name.$f shoulder/left/$name.SLDPRT --settings "adopted 2026-11-14 (key slot, joint floors, pad and plate): build_parts.py $key" > /dev/null || echo "record failed: $name.$f"
    done
  done
  $PY tools/cad/check_cad_layout.py cad | tail -2
  ;;
esac
