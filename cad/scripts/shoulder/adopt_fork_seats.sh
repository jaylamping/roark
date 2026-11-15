#!/bin/bash
# Adopt the fork revision of 2026-11-15 as THE fork front and fork rear, in one step:
#   fork front: washer seats for the RS02's five M3 (flat to r 3.5 on an 8.0 mm floor, R 1 into the pocket wall, R 2.5 at
#               the two screws under the cheek), round key tunnel in place of the square-ended slot, skirt 3.00 mm longer;
#   fork rear:  the 6808's housing at dia 52.0 (a hand-push fit with no play; final size from the seat coupon).
# The candidates it must reproduce: cad/exports/shoulder/shoulder_fork_{front,rear}_left_seats_candidate.STL.
#   bash cad/scripts/shoulder/adopt_fork_seats.sh            the adoption
#   DRY=1 bash cad/scripts/shoulder/adopt_fork_seats.sh      a trial: steps 1 and 2 into a scratch look folder, nothing real changes
# What it does:
#   1. Rebuilds both parts from scratch in one hidden instance (build_parts.py fork_front fork_rear, with the switches
#      below), with a claim. The real parts are overwritten here.
#   2. Collapses the fork front STL's sliver facet (stl_sliver_fix.py) and checks both STLs against the candidates: the same
#      file, or the same surface within 0.01 mm.
#   3. Replaces the four exports, records them, removes the candidate files and their manifest entries, layout check.
#   4. Runs the clearance sweep on the real set. No SolidWorks may be in set-up beside it.
# Every way out prints its reason and a last line: ADOPTED, or NOT ADOPTED with what (if anything) was changed.
# After it: switch the defaults in dims.py to these values, rebuild and save the assembly (build_asm.py, hidden, as at the
# adoptions of 2026-11-14; it also brings hub rev E1 into the assembly file), then commit as Joey.
export PYTHONDONTWRITEBYTECODE=1
export RS02_SEAT_FIX=1 RS02_SEAT_DEPTH=2.0 RS02_SEAT_R_CHEEK=2.5 KEY_ROUND=1 SKIRT_DROP=3.0 BRG_SEAT_R=26.0
REPO=/j/code/roark-wt/shoulder-study
cd $REPO/cad/scripts/shoulder || { echo "NOT ADOPTED: $REPO/cad/scripts/shoulder not found. Nothing was changed."; exit 1; }
PY=C:/joe/code/_venvs/shoulder/Scripts/python
W=../../_wip/shoulder-pass1
L=$W/queue5.log
CL="$PY $REPO/tools/pc/claims.py"
LK="$PY $REPO/cad/_wip/shoulder-pass1/solve_lock.py"
WP=$(cat /proc/$$/winpid)
REAL="cad/shoulder/left/shoulder_fork_front_left.SLDPRT cad/shoulder/left/shoulder_fork_rear_left.SLDPRT"
CHANGED="Nothing was changed."
DONE=
finish() {
  $LK drop $WP > /dev/null 2>&1
  $CL release shoulder-study-fea > /dev/null 2>&1
  [ -n "$DONE" ] || echo "NOT ADOPTED. $CHANGED"
}
trap finish EXIT
stop() { echo "STOPPED: $1"; exit 1; }
if [ -n "$DRY" ]; then echo 'TRIAL RUN (DRY=1): the rebuild goes into a scratch look folder; the real parts, the exports and the manifest are not touched.'; fi
for k in front rear; do
  [ -f ../../exports/shoulder/shoulder_fork_${k}_left_seats_candidate.STL ] || stop "no candidate export for the fork $k"
done
echo 'waiting for the solve lock (a running solve finishes first; this can take up to 20 minutes) ...'
$LK take "shoulder fork seats adoption" $WP || stop 'could not take the solve lock'

# 1. the parts, hidden, with a claim
echo 'step 1 of 4: rebuilding the fork front and the fork rear in a hidden SolidWorks (about 3 minutes) ...'
until [ "$(powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)")" -ge 10 ]; do echo '  waiting for 10 GB of free memory'; sleep 60; done
$CL claim shoulder-study-fea --worktree 'J:\code\roark-wt\shoulder-study' --status "adoption: fork seats${DRY:+ (trial)}" > /dev/null 2>&1
echo "adoption of the fork seats${DRY:+ (trial)}: build start $(date +%T)" >> $L
unset LOOK
if [ -n "$DRY" ]; then
  BL=$W/build_adopt_fork_seats_trial.txt; ST=.sw_instance_pid_adoptFKdry; SD=$W/stl_look_adoptfk; PD=$W/step_look_adoptfk
  export LOOK=adoptfk
else
  BL=$W/build_adopt_fork_seats.txt; ST=.sw_instance_pid_adoptFK; SD=$W/stl; PD=$W/step
  CHANGED="The real fork parts may have been rewritten: restore them with  git -C $REPO checkout -- $REAL  (the exports and the manifest were not touched)."
fi
rm -f $BL
SW_VISIBLE=0 SW_STATE_NAME=$ST $PY capped.py --mb 6144 -- $PY -u build_parts.py fork_front fork_rear > $BL 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  SP=$(cut -d" " -f1 $W/$ST 2>/dev/null)
  $CL beat shoulder-study-fea ${SP:+--sw-pid $SP} > /dev/null 2>&1
  sleep 5
done
wait $pid; rc=$?
[ $rc -eq 0 ] || { echo "the build's last lines ($BL):"; tail -4 $BL; stop "the build ended with exit code $rc"; }
for f_ in "SKIRT_EXT: added 1406" "KEY_SLOT: cut 375" "RS02_CB0: cut 83" "RS02_CB3: cut 540" "RS02_CB4: cut 459" "== shoulder_fork_front_left" "== shoulder_fork_rear_left"; do
  grep -q "$f_" $BL || stop "missing from the build log ($f_)"
done

# 2. the rebuilt parts must be the candidates
echo 'step 2 of 4: comparing the rebuilt parts with the candidates'
F1=$(ls $SD | grep -i '^fork_front\.stl$'); F2=$(ls $SD | grep -i '^fork_rear\.stl$')
[ -n "$F1" ] && [ -n "$F2" ] || stop "the rebuilt STLs are not in $SD"
$PY stl_sliver_fix.py $SD/$F1 $SD/$F1 || stop 'the fork front STL could not be cleaned of its sliver facet'
SD=$SD F1=$F1 F2=$F2 $PY capped.py --mb 6144 -- $PY - <<'PYEOF' || stop 'a rebuilt part is not its candidate'
import hashlib, os, sys
import trimesh
bad = False
for k, f in (('front', os.environ['F1']), ('rear', os.environ['F2'])):
    a, b = os.path.join(os.environ['SD'], f), f'../../exports/shoulder/shoulder_fork_{k}_left_seats_candidate.STL'
    ha, hb = (hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in (a, b))
    print(f'  fork {k}: rebuilt   {ha}'); print(f'  fork {k}: candidate {hb}')
    if ha == hb:
        print('    the same file')
        continue
    ma, mb = trimesh.load(a), trimesh.load(b)
    worst = 0.0
    for src, dst in ((ma, mb), (mb, ma)):
        pts, _ = trimesh.sample.sample_surface(src, 40000, seed=1)
        worst = max(worst, max(trimesh.proximity.closest_point(dst, pts[i:i + 4000])[1].max() for i in range(0, len(pts), 4000)))
    print('    files differ; largest surface offset %.4f mm, volume %.0f against %.0f mm3' % (worst, ma.volume, mb.volume))
    bad = bad or worst > 0.01
sys.exit(1 if bad else 0)
PYEOF
if [ -n "$DRY" ]; then
  DONE=1
  echo "adoption of the fork seats (trial): passed $(date +%T)" >> $L
  echo 'TRIAL PASSED: the rebuild reproduces both candidates. Nothing real was changed.'
  echo 'Not covered by the trial: writing the real parts, replacing the exports, the manifest, the layout check and the sweep.'
  exit 0
fi

# 3. exports
echo 'step 3 of 4: replacing the exports and their records'
CHANGED="The real fork parts ARE the new revision now, but the exports or the manifest may be half done: see the message above; restore everything with  git -C $REPO checkout -- $REAL cad/exports/shoulder cad/manifests/exports.json"
cd $REPO
for k in front rear; do
  s=$(ls cad/_wip/shoulder-pass1/stl | grep -i "^fork_$k\.stl$"); p=$(ls cad/_wip/shoulder-pass1/step | grep -i "^fork_$k\.step$")
  cp cad/_wip/shoulder-pass1/step/$p cad/exports/shoulder/shoulder_fork_${k}_left.STEP || stop "could not replace shoulder_fork_${k}_left.STEP"
  cp cad/_wip/shoulder-pass1/stl/$s cad/exports/shoulder/shoulder_fork_${k}_left.STL || stop "could not replace shoulder_fork_${k}_left.STL"
  for f in STEP STL; do
    C:/Users/holly/AppData/Local/Programs/Python/Python312/python.exe tools/cad/record_export.py \
      exports/shoulder/shoulder_fork_${k}_left.$f shoulder/left/shoulder_fork_${k}_left.SLDPRT --settings "adopted 2026-11-15 (RS02 washer seats, round key tunnel, skirt +3.00; 6808 housing dia 52.0): build_parts.py fork_$k with RS02_SEAT_FIX=1 RS02_SEAT_R_CHEEK=2.5 KEY_ROUND=1 SKIRT_DROP=3.0 BRG_SEAT_R=26.0" > /dev/null || stop "record_export.py failed for shoulder_fork_${k}_left.$f"
  done
done
git rm -q -f --ignore-unmatch cad/exports/shoulder/shoulder_fork_front_left_seats_candidate.STEP cad/exports/shoulder/shoulder_fork_front_left_seats_candidate.STL \
  cad/exports/shoulder/shoulder_fork_rear_left_seats_candidate.STEP cad/exports/shoulder/shoulder_fork_rear_left_seats_candidate.STL || stop 'git rm of the candidate exports failed'
rm -f cad/exports/shoulder/shoulder_fork_*_left_seats_candidate.ST*
$PY - <<'PYEOF' || stop 'could not remove the candidate entries from cad/manifests/exports.json'
import json, io
p = 'cad/manifests/exports.json'; d = json.load(io.open(p, encoding='utf8'))
def drop(x):
    if isinstance(x, dict):
        return {k: drop(v) for k, v in x.items() if 'seats_candidate' not in k}
    if isinstance(x, list):
        return [drop(v) for v in x if 'seats_candidate' not in json.dumps(v)]
    return x
json.dump(drop(d), io.open(p, 'w', encoding='utf8'), indent=2)
print('  manifest: candidate entries removed')
PYEOF
rm -rf cad/scripts/shoulder/__pycache__
$PY tools/cad/check_cad_layout.py $REPO/cad || stop 'the layout check reports errors (listed above)'

# 4. the sweep on the real set
echo 'step 4 of 4: clearance sweep (20 to 30 minutes, all cores) ...'
CHANGED="The fork revision IS adopted in the working tree (parts, exports, manifest), but the clearance sweep did not finish: run it again with  cd $REPO/cad/scripts/shoulder && CLEAR_JSON=clearance_adopt_fork_seats.json $PY check_clearance.py"
cd $REPO/cad/scripts/shoulder
echo "adoption of the fork seats: clearance sweep start $(date +%T)" >> $L
CLEAR_JSON=clearance_adopt_fork_seats.json $PY capped.py --mb 6144 -- $PY check_clearance.py > $W/clearance_adopt_fork_seats.txt 2>&1; rc=$?
echo "adoption of the fork seats: sweep done $(date +%T) exit $rc" >> $L
[ $rc -eq 0 ] || { tail -4 $W/clearance_adopt_fork_seats.txt; stop "the clearance sweep ended with exit code $rc"; }
DONE=1
echo 'ADOPTED: the fork front and the fork rear are the new revision in the working tree (parts, exports, manifest), and the sweep ran. Not committed yet.'
