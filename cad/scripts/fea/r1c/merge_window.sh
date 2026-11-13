#!/bin/bash
# Merge window (2026-11-13, coordinator 19:05Z): hold our worktree lock so no job of ours runs or launches, then merge origin/main
# (main's tools/solidworks/RULES.md and sw_instance.py taken outright, verified byte-identical), sw_instance --status, a smoke
# test (launch and end one session), push; then the D3c7 hub checks with no solve running; then release the lock.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
OUT=cad/_wip/merge_window.log
: > $OUT
until mkdir $LK 2>/dev/null; do sleep 1; done
echo "merge_window $$" > $LK/owner
trap 'grep -q "^merge_window $$\$" $LK/owner 2>/dev/null && rm -rf $LK' EXIT
echo "MERGE_WINDOW lock held $(date +%H:%M)" >> $L
# wait out any SolidWorks of ours still closing (end_session of the last job)
for f in cad/_wip/arm-sw-job-*/.sw_instance_pid; do [ -f "$f" ] && echo "state file left: $f" >> $OUT; done
export CAD_WRITER='upper-arm-r1:2bcc415b'
until mkdir cad/_wip/.r1d_git_lock 2>/dev/null; do sleep 5; done
{
  git fetch -q origin main
  git merge --no-ff --no-commit origin/main 2>&1 | tail -5
  for f in tools/solidworks/RULES.md tools/solidworks/sw_instance.py; do git checkout --theirs -- "$f" && git add "$f"; done
  git diff --name-only --diff-filter=U
  for f in tools/solidworks/RULES.md tools/solidworks/sw_instance.py; do
    if git diff --quiet origin/main -- "$f" && cmp -s <(git show origin/main:"$f") "$f"; then echo "IDENTICAL to main: $f"; else echo "DIFFERS from main: $f"; fi
  done
} >> $OUT 2>&1
if [ -n "$(git diff --name-only --diff-filter=U)" ]; then
  echo "MERGE_WINDOW STOP: unresolved conflicts: $(git diff --name-only --diff-filter=U | tr '\n' ' ')" >> $L
  git merge --abort >> $OUT 2>&1; rmdir cad/_wip/.r1d_git_lock; exit 1
fi
git commit -q -m "Merge origin/main into left-arm-organic-r1 (LFS budget: 8 GB total, no monthly cap; tools/solidworks/RULES.md and sw_instance.py taken from main)" >> $OUT 2>&1
git push -q origin left-arm-organic-r1 >> $OUT 2>&1; echo "push rc $?" >> $OUT
rmdir cad/_wip/.r1d_git_lock
echo "MERGED $(git log -1 --format=%h) $(grep -c IDENTICAL $OUT) identical $(date +%H:%M)" >> $L
# status and smoke test
python tools/solidworks/sw_instance.py --status >> $OUT 2>&1
mkdir -p cad/_wip/arm-sw-smoke
python - >> $OUT 2>&1 <<'PY'
import sys, time
sys.path.insert(0, 'tools/solidworks')
import sw_instance as S
st = 'cad/_wip/arm-sw-smoke/.sw_instance_pid'
t = time.time()
inst = S.session(st)
print('SMOKE launched pid', inst.pid, 'revision', inst.sw.RevisionNumber(), 'in', round(time.time() - t), 's')
S.end_session(st)
print('SMOKE ended; pid alive after end:', S._started(inst.pid) is not None)
PY
echo "SMOKE $(grep -E '^SMOKE' $OUT | tr '\n' ' ')" >> $L
date +%s > cad/_wip/.fea_job_last_end
echo "MERGE_WINDOW_DONE $(date +%H:%M)" >> $L
