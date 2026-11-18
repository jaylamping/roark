#!/bin/bash
# The proper neck check: for each analysis build (TAGS), build the fork front, combine it with the fork rear, then run the
# P_* (fork front alone, fine mesh at the boss root) and F2_* (combined with the rear leg, 6808 seat held radially) cases.
# One SolidWorks instance at a time; claim with the instance's PID; 6 GB cap; FFEPlus (no contact in these models).
cd /j/code/roark-wt/shoulder-study/cad/scripts/shoulder
W=../../_wip/shoulder-pass1
L=$W/queue5.log
PY=C:/joe/code/_venvs/shoulder/Scripts/python
CAP="$PY capped.py --mb ${CAPMB:-6144} --"
CL="$PY C:/joe/code/roark-wt/shoulder-study/tools/pc/claims.py"
S=shoulder-study-fea
free_gb() { powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)"; }
trap '$CL release $S > /dev/null 2>&1' EXIT
job() {   # job <state name> <status> <log> <command...>
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
if [ -z "$NOSWEEP" ]; then
  # the clearance sweep with the solid-neck yoke and the rim B ring, while no SolidWorks instance of mine is up
  mkdir -p $W/stl_look_yokeS_rimB
  cp $W/stl_look_yokeS/fork_front.STL $W/stl_look_yokeS_rimB/fork_front.stl
  cp $W/stl_look_rimB/ring.STL $W/stl_look_yokeS_rimB/ring.stl
  echo "start clearance sweep, yoke (solid neck) and rim B $(date +%T)" >> $L
  PART_STL_DIR=stl_look_yokeS_rimB PART_STL_PARTS=fork_front,ring CLEAR_JSON=clearance_yoke_rimB.json $CAP $PY check_clearance.py > $W/clearance_yoke_rimB.txt 2>&1
  echo "clearance sweep done $(date +%T) exit $?" >> $L
fi
CASES_P=${CASES_P:-P_MXb P_MXnb P_MXbs P_MX P_MXn P_MZ}
CASES_F=${CASES_F:-F2_MX F2_MXn F2_MXs F2_MZ F2_STOP}
for T in ${TAGS:-ffT ffTS ffYS}; do
  echo "proper check $T: build $(date +%T)" >> $L
  if [ -z "$NOBUILD" ]; then
    LOOK=$T job .sw_instance_pid_$T "look build $T" $W/build_$T.txt $CAP $PY -u build_parts.py fork_front
    echo "  $T built: $(grep '== shoulder' $W/build_$T.txt | cut -c1-110)" >> $L
    job .sw_instance_pid_f2_$T "fork2 part $T" $W/fork2_$T.txt $CAP $PY -u fork2_fea_part.py $T
    echo "  $T combined: $(grep 'volume kept\|did not combine' $W/fork2_$T.txt | cut -c1-110)" >> $L
  fi
  cp ../../_wip/look/$T/shoulder_fork_front_left.SLDPRT ../../_sim/shoulder/ffp_$T.SLDPRT
  FEA_FACE_CACHE=1 FEA_SOLVER=2 FEA_EL=${EL:-2.0} FF_FEA_FILE=ffp_$T.SLDPRT FORK2_FEA_FILE=fork2_$T.SLDPRT job .sw_instance_pid_p_$T "FEA proper check $T" $W/P_$T.txt $CAP $PY -u fea_shoulder.py $CASES_P $CASES_F
  for c in $CASES_P $CASES_F; do
    for x in "" _u; do [ -f ../../_sim/shoulder/$c$x.npz ] && mv ../../_sim/shoulder/$c$x.npz ../../_sim/shoulder/${c}_$T$x.npz; done
  done
  echo "proper check $T done $(date +%T): $(grep -c '^ solve 0' $W/P_$T.txt) solved of $(echo $CASES_P $CASES_F | wc -w)" >> $L
done
echo "proper check all done $(date +%T)" >> $L
