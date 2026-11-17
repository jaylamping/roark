#!/bin/bash
# Adopt the fork rear's two wiring changes (OPEN_ASSUMPTIONS items 47 and 51; Joey: "Yes, take both", 2026-11-15) as THE
# fork rear:
#   the opening between the signal and the power channel 18 mm high, with a sloped wall end (was 6 mm);
#   a tie bar, 2 x 2 mm, across the power channel at the underside;
#   the 6808's housing at dia 52.1 (was 52.0): the size that fitted on the printed seat test rings (Joey, 2026-11-15).
# The outside, the lip behind the bearing, the joint face and the screw positions do not change. The fork front is not touched.
# The candidate it must reproduce: cad/exports/shoulder/shoulder_fork_rear_left_wiring_candidate.STL.
#   bash cad/scripts/shoulder/adopt_fork_rear_wiring.sh            the adoption
#   DRY=1 bash cad/scripts/shoulder/adopt_fork_rear_wiring.sh      a trial: steps 1 and 2 into a scratch look folder, nothing real changes
#   SKIP_SWEEP="reason" bash cad/scripts/shoulder/adopt_fork_rear_wiring.sh      the adoption without step 4; it prints that the sweep is owed and why
# What it does:
#   1. Rebuilds the fork rear from scratch in one hidden instance (build_parts.py fork_rear, with the switches below),
#      with a claim. The real part is overwritten here.
#   2. Checks the STL against the candidate: the same file, or the same surface within 0.01 mm.
#   3. Replaces the two exports, records them, removes the candidate files and their manifest entries, layout check.
#   4. Runs the clearance sweep on the real set. No SolidWorks may be in set-up beside it.
# Every way out prints its reason and a last line: ADOPTED, or NOT ADOPTED with what (if anything) was changed.
# After it: switch the defaults in dims.py (FR_JOIN_H 18.0, FR_TIE_BAR on; BRG_SEAT_R is 26.05 already), rebuild and save the assembly, commit as Joey.
# Run on joey-vm on 2026-11-17 with SKIP_SWEEP (no torso_frame.step there); the defaults in dims.py are switched.
export PYTHONDONTWRITEBYTECODE=1
export FR_JOIN_H=18.0 FR_TIE_BAR=1 BRG_SEAT_R=26.05
REPO=${REPO:-/j/code/roark-wt/shoulder-study}      # REPO, PY, RPY and WT_WIN: set them in the environment on a machine other than holly-pc
cd $REPO/cad/scripts/shoulder || { echo "NOT ADOPTED: $REPO/cad/scripts/shoulder not found. Nothing was changed."; exit 1; }
PY=${PY:-C:/joe/code/_venvs/shoulder/Scripts/python}
RPY=${RPY:-C:/Users/holly/AppData/Local/Programs/Python/Python312/python.exe}
WT_WIN=${WT_WIN:-'J:\code\roark-wt\shoulder-study'}
W=../../_wip/shoulder-pass1
L=$W/queue5.log
CL="$PY $REPO/tools/pc/claims.py"
LK="$PY $REPO/cad/_wip/shoulder-pass1/solve_lock.py"
WP=$(cat /proc/$$/winpid)
REAL="cad/shoulder/left/shoulder_fork_rear_left.SLDPRT"
CAND=shoulder_fork_rear_left_wiring_candidate
CHANGED="Nothing was changed."
DONE=
finish() {
  $LK drop $WP > /dev/null 2>&1
  $CL release shoulder-study-fea > /dev/null 2>&1
  [ -n "$DONE" ] || echo "NOT ADOPTED. $CHANGED"
}
trap finish EXIT
stop() { echo "STOPPED: $1"; exit 1; }
if [ -n "$DRY" ]; then echo 'TRIAL RUN (DRY=1): the rebuild goes into a scratch look folder; the real part, the exports and the manifest are not touched.'; fi
[ -f ../../exports/shoulder/$CAND.STL ] || stop "no candidate export ($CAND.STL)"
echo 'waiting for the solve lock (a running solve finishes first; this can take up to 30 minutes) ...'
$LK take "shoulder fork rear wiring adoption" $WP || stop 'could not take the solve lock'

# 1. the part, hidden, with a claim
echo 'step 1 of 4: rebuilding the fork rear in a hidden SolidWorks (about 2 minutes) ...'
until [ "$(powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)")" -ge 10 ]; do echo '  waiting for 10 GB of free memory'; sleep 60; done
$CL claim shoulder-study-fea --worktree "$WT_WIN" --status "adoption: fork rear wiring${DRY:+ (trial)}" > /dev/null 2>&1
echo "adoption of the fork rear wiring${DRY:+ (trial)}: build start $(date +%T)" >> $L
unset LOOK
if [ -n "$DRY" ]; then
  BL=$W/build_adopt_fork_rear_wiring_trial.txt; ST=.sw_instance_pid_adoptFRdry; SD=$W/stl_look_adoptfr; PD=$W/step_look_adoptfr
  export LOOK=adoptfr
else
  BL=$W/build_adopt_fork_rear_wiring.txt; ST=.sw_instance_pid_adoptFR; SD=$W/stl; PD=$W/step
  CHANGED="The real fork rear may have been rewritten: restore it with  git -C $REPO checkout -- $REAL  (the exports and the manifest were not touched)."
fi
rm -f $BL
SW_VISIBLE=0 SW_STATE_NAME=$ST $PY capped.py --mb 6144 -- $PY -u build_parts.py fork_rear > $BL 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  SP=$(cut -d" " -f1 $W/$ST 2>/dev/null)
  $CL beat shoulder-study-fea ${SP:+--sw-pid $SP} > /dev/null 2>&1
  sleep 5
done
wait $pid; rc=$?
[ $rc -eq 0 ] || { echo "the build's last lines ($BL):"; tail -4 $BL; stop "the build ended with exit code $rc"; }
for f_ in "SEAT: cut 19093" "CH_JOIN: cut 161" "TIE_BAR: added 34" "== shoulder_fork_rear_left: 1 bodies"; do
  grep -q "$f_" $BL || stop "missing from the build log ($f_)"
done

# 2. the rebuilt part must be the candidate
echo 'step 2 of 4: comparing the rebuilt part with the candidate'
F2=$(ls $SD | grep -i '^fork_rear\.stl$')
[ -n "$F2" ] || stop "the rebuilt STL is not in $SD"
SD=$SD F2=$F2 CAND=$CAND $PY capped.py --mb 6144 -- $PY - <<'PYEOF' || stop 'the rebuilt part is not the candidate'
import hashlib, os, sys
import trimesh
a, b = os.path.join(os.environ['SD'], os.environ['F2']), '../../exports/shoulder/%s.STL' % os.environ['CAND']
ha, hb = (hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in (a, b))
print(f'  fork rear: rebuilt   {ha}'); print(f'  fork rear: candidate {hb}')
if ha == hb:
    print('    the same file')
    sys.exit(0)
ma, mb = trimesh.load(a), trimesh.load(b)
worst = 0.0
for src, dst in ((ma, mb), (mb, ma)):
    pts, _ = trimesh.sample.sample_surface(src, 40000, seed=1)
    worst = max(worst, max(trimesh.proximity.closest_point(dst, pts[i:i + 4000])[1].max() for i in range(0, len(pts), 4000)))
print('    files differ; largest surface offset %.4f mm, volume %.0f against %.0f mm3' % (worst, ma.volume, mb.volume))
sys.exit(1 if worst > 0.01 else 0)
PYEOF
if [ -n "$DRY" ]; then
  DONE=1
  echo "adoption of the fork rear wiring (trial): passed $(date +%T)" >> $L
  echo 'TRIAL PASSED: the rebuild reproduces the candidate. Nothing real was changed.'
  echo 'Not covered by the trial: writing the real part, replacing the exports, the manifest, the layout check and the sweep.'
  exit 0
fi

# 3. exports
echo 'step 3 of 4: replacing the exports and their records'
CHANGED="The real fork rear IS the new revision now, but the exports or the manifest may be half done: see the message above; restore everything with  git -C $REPO checkout -- $REAL cad/exports/shoulder cad/manifests/exports.json"
cd $REPO
s=$(ls cad/_wip/shoulder-pass1/stl | grep -i '^fork_rear\.stl$'); p=$(ls cad/_wip/shoulder-pass1/step | grep -i '^fork_rear\.step$')
cp cad/_wip/shoulder-pass1/step/$p cad/exports/shoulder/shoulder_fork_rear_left.STEP || stop 'could not replace shoulder_fork_rear_left.STEP'
cp cad/_wip/shoulder-pass1/stl/$s cad/exports/shoulder/shoulder_fork_rear_left.STL || stop 'could not replace shoulder_fork_rear_left.STL'
for f in STEP STL; do
  $RPY tools/cad/record_export.py \
    exports/shoulder/shoulder_fork_rear_left.$f shoulder/left/shoulder_fork_rear_left.SLDPRT --settings "adopted 2026-11-15 (channel opening 18 mm with sloped wall end; tie bar at the underside; 6808 housing dia 52.1 from the seat test rings): build_parts.py fork_rear with FR_JOIN_H=18.0 FR_TIE_BAR=1 BRG_SEAT_R=26.05" > /dev/null || stop "record_export.py failed for shoulder_fork_rear_left.$f"
done
git rm -q -f --ignore-unmatch cad/exports/shoulder/$CAND.STEP cad/exports/shoulder/$CAND.STL || stop 'git rm of the candidate exports failed'
rm -f cad/exports/shoulder/$CAND.ST*
$PY - <<'PYEOF' || stop 'could not remove the candidate entries from cad/manifests/exports.json'
import json, io
p = 'cad/manifests/exports.json'; d = json.load(io.open(p, encoding='utf8'))
def drop(x):
    if isinstance(x, dict):
        return {k: drop(v) for k, v in x.items() if 'wiring_candidate' not in k}
    if isinstance(x, list):
        return [drop(v) for v in x if 'wiring_candidate' not in json.dumps(v)]
    return x
json.dump(drop(d), io.open(p, 'w', encoding='utf8'), indent=2)
print('  manifest: candidate entries removed')
PYEOF
rm -rf cad/scripts/shoulder/__pycache__
$PY tools/cad/check_cad_layout.py $REPO/cad || stop 'the layout check reports errors (listed above)'

# 4. the sweep on the real set
if [ -n "$SKIP_SWEEP" ]; then
  DONE=1
  echo "adoption of the fork rear wiring: clearance sweep SKIPPED ($SKIP_SWEEP) $(date +%T)" >> $REPO/cad/_wip/shoulder-pass1/queue5.log
  echo "step 4 of 4: clearance sweep SKIPPED: $SKIP_SWEEP"
  echo "ADOPTED WITHOUT THE SWEEP: the fork rear is the new revision in the working tree (part, exports, manifest). The clearance sweep is owed: cd $REPO/cad/scripts/shoulder && CLEAR_JSON=clearance_adopt_fork_rear_wiring.json $PY check_clearance.py. Not committed yet."
  exit 0
fi
echo 'step 4 of 4: clearance sweep (20 to 30 minutes, all cores) ...'
CHANGED="The fork rear IS adopted in the working tree (part, exports, manifest), but the clearance sweep did not finish: run it again with  cd $REPO/cad/scripts/shoulder && CLEAR_JSON=clearance_adopt_fork_rear_wiring.json $PY check_clearance.py"
cd $REPO/cad/scripts/shoulder
echo "adoption of the fork rear wiring: clearance sweep start $(date +%T)" >> $L
CLEAR_JSON=clearance_adopt_fork_rear_wiring.json $PY capped.py --mb 6144 -- $PY check_clearance.py > $W/clearance_adopt_fork_rear_wiring.txt 2>&1; rc=$?
echo "adoption of the fork rear wiring: sweep done $(date +%T) exit $rc" >> $L
[ $rc -eq 0 ] || { tail -4 $W/clearance_adopt_fork_rear_wiring.txt; stop "the clearance sweep ended with exit code $rc"; }
DONE=1
echo 'ADOPTED: the fork rear is the new revision in the working tree (part, exports, manifest), and the sweep ran. Not committed yet.'
