#!/bin/bash
# Read-back trim test runner (2026-11-14, coordinator): a copy of the solved r1g6_g90 study, read all-node and per body, then the
# spot and region reports from both reads, diffed. Lock rules as for a large job (it loads a full result): the worktree lock, 180 s
# after our last job, 18 GB free, the large-solve lock (solve_lock_hold.py, main's layout, never removing another's).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
wpid() { cat /proc/$$/winpid 2>/dev/null || echo $$; }
until mkdir $LK 2>/dev/null; do sleep 15; done; echo "readback $$" > $LK/owner
STF=$R/_wip/.solve_lock_held_readback; RELF=$R/_wip/.solve_lock_release_readback; hpid=
slrelease() { [ -n "$hpid" ] || return 0; touch $RELF; for i in $(seq 30); do kill -0 $hpid 2>/dev/null || break; sleep 1; done; hpid=; }
trap 'grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; slrelease' EXIT
if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
until [ "$(free)" -ge 18000 ]; do sleep 60; done
rm -f $STF $RELF
python cad/scripts/fea/r1c/solve_lock_hold.py "left-arm-organic readback" $STF $RELF $(wpid) $L & hpid=$!
until [ -f $STF ] || ! kill -0 $hpid 2>/dev/null; do sleep 5; done
[ -f $STF ] || { echo "READBACK: no solve lock" >> $L; exit 1; }
D=cad/_sim/readback_test; mkdir -p $D
cp -p cad/_sim/r1g6_g90/UA_HUBSEAT_r1d_r1g6.SLDPRT cad/_sim/r1g6_g90/UA_HUBSEAT_r1d_r1g6-r1g6_g90.* cad/_sim/r1g6_g90/post.txt cad/_sim/r1g6_g90/HUB_GROOVE_r1d.STL $D/
echo "READBACK start $(date +%H:%M) free $(free) MB" >> $L
python cad/scripts/fea/r1c/readback_trim.py "$(cygpath -w $PWD/$D/UA_HUBSEAT_r1d_r1g6.SLDPRT)" r1g6_g90 $D > $D/readback.log 2>&1
echo "READBACK read done $(date +%H:%M): $(grep -E 'SECONDS|largest|not in' $D/readback.log | tr '\n' ' ')" >> $L
date +%s > $STAMP
slrelease
grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK
for x in A B; do
  $PYC cad/scripts/fea/r1c/spot_report.py $D/$x.npz $D/post.txt 1.7 294.6 > $D/spot_$x.txt 2>&1
  $PYC cad/scripts/fea/r1c/yaw_report.py $D/$x.npz $D/post.txt > $D/region_$x.txt 2>&1
done
for f in spot region; do cmp -s <(grep -v "^result:" $D/${f}_A.txt) <(grep -v "^result:" $D/${f}_B.txt) && echo "$f: IDENTICAL" || echo "$f: DIFFERENT"; done > $D/compare.txt
echo "READBACK done $(date +%H:%M): $(tr '\n' ' ' < $D/compare.txt)" >> $L
