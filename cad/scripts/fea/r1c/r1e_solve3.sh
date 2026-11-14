#!/bin/bash
# r1e_solve3 (2026-11-13, coordinator 19:35Z): as r1e_solve2, but "used" counts only our own process tree (resident: working set; the
# first version summed private commit, which reads about 1.4x the resident figure and stopped a job with 11 GB free): the job's Python process and
# our SolidWorks (its PID from this job's session state file) with all their child processes. The free-memory
# stop (MEMSTOP_FREE) still guards the machine. Before: "used" was the machine's free-memory drop, so another session's solve counted.
# One hub-seat FEA job, one at a time, with the machine-wide solve lock (r1e_solve2: 2026-11-13) (2026-11-12, after two solves launched together from one session folder and a memory stop
# ended the wrong instance). Same as r1d_ring_ds_solve.sh "new" mode, plus:
#   - its own SolidWorks session folder and pid file: cad/_wip/arm-sw-job-<FOLDER> (never shared between jobs);
#   - a lock (cad/_wip/.fea_job_lock, mkdir) taken before the launch and released only after end_session, so no second job of
#     ours can launch in between; the lock holds the job name and our bash pid;
#   - before launching: no SolidWorks of ours left from an earlier job (any arm-sw-job-* state file naming a live instance),
#     no instance busy, >= 16 GB free, and 180 s since the last job ended (stamp file).
# Memory watch as before: stop cleanly (end our session) at 12 GB used (free-RAM drop since our start) or under 4 GB free.
#   usage: FOLDER=... MTAG=... CASE=... [PADE HUBFILE HUBSTL DS_SOLVER FEA_SAVE_DISP FEA_MESH_ONLY HS_ROOT_MESH] bash r1e_solve1.sh
MTAG=${MTAG:?}; CASE=${CASE:?}; folder=${FOLDER:?}
[[ "$MTAG" == *i ]] && export R1C_INSERTS=1
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring_ds.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
RV=cad/reviews/upper-arm/20261111_r1c-delta/r1d
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=${HUBFILE:-HUB_GROOVE_RING.SLDPRT} HS_PAD_E=${PADE:-0.5} HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 R1C_RING=1 CAD_WRITER='upper-arm-r1:2bcc415b'
S="$R/_wip/arm-sw-job-$folder"; mkdir -p "$S"
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
endjob() {      # end our session, stamp the time, release the lock (only if it is ours)
  (cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish(); print('ended $folder')") >> $L 2>&1
  date +%s > $STAMP
  slrelease
  grep -q "^$folder $$\$" $LK/owner 2>/dev/null && rm -rf $LK
}
ours_live() { for f in cad/_wip/arm-sw-job-*/.sw_instance_pid cad/_wip/arm-sw-fea/.sw_instance_pid; do [ -f "$f" ] && python -c "import sys; sys.path.insert(0, r'C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks'); import sw_instance as S; sys.exit(0 if S._session_pid(r'$f') else 1)" 2>/dev/null && return 0; done; return 1; }
# lock first, then the checks (the lock is what serialises launches)
until mkdir $LK 2>/dev/null; do sleep 15; done
echo "$folder $$" > $LK/owner
# the large-solve lock is held by a helper process (solve_lock_hold.py, main's big_solve layout); RELF tells it to let go
STF=$R/_wip/.solve_lock_held_$folder; RELF=$R/_wip/.solve_lock_release_$folder
slrelease() { [ -n "$hpid" ] || return 0; touch $RELF; for i in $(seq 30); do kill -0 $hpid 2>/dev/null || break; sleep 1; done; hpid=; }
trap 'grep -q "^$folder $$\$" $LK/owner 2>/dev/null && rm -rf $LK; slrelease' EXIT
while ours_live; do sleep 30; done
until ! python "$SWI" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
# The machine-wide large-solve lock C:\joe\.fea_solve.lock (RULES.md rule 6), taken ONLY at the moment of launch: wait for free
# memory, take the lock, re-check free memory, launch; if the re-check fails, let it go and wait again. Since 2026-11-14 (coordinator)
# it is taken in main's big_solve layout by a helper process (solve_lock_hold.py) that lives for the whole job, and a lock that looks
# stale is NEVER removed: the helper waits and logs it for a person (a Git Bash pid in another thread's lock looked dead on 2026-11-13
# while its solve was alive). Released by slrelease after end_session.
wpid() { cat /proc/$$/winpid 2>/dev/null || echo $$; }
hpid=
while true; do
  until [ "$(free)" -ge ${MINFREE:-18000} ]; do sleep 60; done
  rm -f $STF $RELF
  python cad/scripts/fea/r1c/solve_lock_hold.py "left-arm-organic $folder" $STF $RELF $(wpid) $L &
  hpid=$!
  until [ -f $STF ] || ! kill -0 $hpid 2>/dev/null; do sleep 5; done
  if [ ! -f $STF ]; then echo "solve lock helper ended without the lock $(date +%H:%M)" >> $L; hpid=; sleep 60; continue; fi
  [ "$(free)" -ge ${MINFREE:-18000} ] && break
  slrelease; echo "solve lock released, memory dropped after taking it $(date +%H:%M)" >> $L; sleep 60
done
D=cad/_sim/$folder; rm -rf $D; mkdir -p $D
cp cad/_sim/ua2/UA_HUBSEAT_r1d_$MTAG.SLDPRT $D/; cp cad/_sim/ua2/${HUBSTL:-HUB_GROOVE_RING.STL} $D/HUB_GROOVE_r1d.STL
if [ "$FEA_MESH_ONLY" = 1 ]; then ENVX="HS_MODEL=UA_HUBSEAT_r1d_$MTAG.SLDPRT"; else ENVX="HS_MODEL=UA_HUBSEAT_r1d_$MTAG.SLDPRT FEA_SOLVER_MACRO=${DS_SOLVER:-1} FEA_STUDY_NAME=$folder"; fi
echo "START $folder (job, lock held) $(date +%H:%M) free $(free) MB session $S" >> $L
env $ENVX ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ringg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$folder" python cad/scripts/fea/organic_fea.py $CASE >> $D/run.log 2>&1 &
cpid=$!
free0=$(free); peak=0
ownmb() {      # private MB of our Python job process and our SolidWorks, with all their descendants
  local roots="$(cat /proc/$cpid/winpid 2>/dev/null)"
  [ -f "$S/.sw_instance_pid" ] && roots="$roots $(awk '{print $1}' "$S/.sw_instance_pid")"
  powershell -NoProfile -c "\$all = Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,WorkingSetSize; \$ids = @($(echo $roots | sed 's/ /,/g')); \$q = \$ids; while (\$q.Count) { \$n = @(\$all | Where-Object { \$q -contains \$_.ParentProcessId } | ForEach-Object { \$_.ProcessId }); \$n = @(\$n | Where-Object { \$ids -notcontains \$_ }); \$ids += \$n; \$q = \$n }; [int]((\$all | Where-Object { \$ids -contains \$_.ProcessId } | Measure-Object WorkingSetSize -Sum).Sum / 1MB)"
}
while kill -0 $cpid 2>/dev/null; do
  sleep ${MEM_SAMPLE:-60}
  fr=$(free); used=$(ownmb); used=${used:-0}; [ "$used" -gt $peak ] && peak=$used      # own process tree only (r1e_solve3)
  echo "mem $(date +%H:%M) $folder used ${used} MB free ${fr} MB" >> cad/_wip/r1d_ring_ds_mem.log
  if [ "$used" -gt ${MEMSTOP_USED:-12288} ] || [ "${fr:-99999}" -lt ${MEMSTOP_FREE:-4096} ]; then
    echo "MEM_STOP $folder $(date +%H:%M) used ${used} MB free ${fr} MB: ending our session" >> $L
    break
  fi
done
endjob
wait $cpid 2>/dev/null
echo "job $folder ended $(date +%H:%M); peak used ${peak} MB; Intel-solver lines $(cat $D/*BenchMark-Solver.txt 2>/dev/null | grep -c INTEL-SOLVER)" >> $L
[ "$FEA_MESH_ONLY" = 1 ] && exit 0
if ls $D/org16_$CASE.npz >/dev/null 2>&1; then
  python $R/scripts/fea/r1c/capped.py --mb 6144 -- python cad/scripts/fea/r1c/hub_r1c.py $D/org16_$CASE.npz $D/HUB_GROOVE_r1d.STL > $D/post.txt 2>&1
  cp $D/org16_$CASE.npz.r1c.json $RV/$folder.json; cp $D/post.txt $RV/$folder.post.txt; grep -E "mesh|solve |reaction|displacement|solver" $D/run.log | tail -8 >> $RV/$folder.post.txt
  echo "SOLVED $folder $(date +%H:%M) $(grep -E 'solve ' $D/run.log | tail -1) $(grep SANITY $D/post.txt)" >> $L
  until mkdir cad/_wip/.r1d_git_lock 2>/dev/null; do sleep 5; done
  git add $RV >/dev/null 2>&1; git commit -q -m "cad: R1e hub-seat $CASE result ($folder)" >/dev/null 2>&1
  for t in 1 2 3; do git push -q origin left-arm-organic-r1 >/dev/null 2>&1 && break; sleep 10; done; rmdir cad/_wip/.r1d_git_lock
else
  echo "SOLVE_FAILED $folder $(date +%H:%M) $(grep -E 'solve |never registered|Error|existing study' $D/run.log | tail -2 | tr '\n' ' ' | cut -c1-200)" >> $L
fi
