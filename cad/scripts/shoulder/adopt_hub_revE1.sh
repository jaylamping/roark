#!/bin/bash
# Adopt hub rev E1 as THE hub part, in one step. Rev E1 = rev D3c7 with, at the top (hub_candidate2.py):
#   - the centre 3 mm taller (cable gap under the RS02 8.5 mm; the hub and the arm sit 3 mm lower on the yaw axis),
#   - the six through-slits in the top (r 19.0-19.5) filled,
#   - the inner pocket filled solid, the centre plate 4 mm thicker, the six boss tubes dia 10.8 with R 4 into the plate (its 1 mm step filled),
#   - the six head seats at Y 298.86 in the arm's coordinates (grip 24.0: M4 x 30 with one flat washer goes 5.2 mm into
#     the RS02, whose holes bottom at 6.5 to 7 mm, Joey 2026-11-15),
#   - the cable slot 4.5 x 11 as a dog-leg clear of the step ring, with rounded mouth and knee,
#   - R 2 from the step wall into the dish floor.
# The candidate it must reproduce: cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STL.
#   bash cad/scripts/shoulder/adopt_hub_revE1.sh            the adoption
#   DRY=1 bash cad/scripts/shoulder/adopt_hub_revE1.sh      a trial: steps 1 to 3 into a scratch folder, nothing real changes
# What it does:
#   1. Keeps the present real hub part (rev D3c7) in cad/_archive/hub_revD3c7/ (not in git), the source of the rebuild.
#   2. Rebuilds the real part from that copy in its own hidden instance (hub_candidate2.py, HUB_ADOPT=1), with a claim.
#   3. Checks the rebuilt STL against the candidate: the same file, or the same surface within 0.01 mm.
#   4. Replaces cad/exports/shoulder/shoulder_hub_left.STEP/.STL, records them, removes the candidate files and their
#      manifest entries, runs the layout check.
#   5. Runs the clearance sweep with the arm 3 mm lower (UA_SHIFT_Y=-3). No SolidWorks may be in set-up beside it.
# Every way out prints its reason and a last line: ADOPTED, or NOT ADOPTED with what (if anything) was changed.
# The commit is left to the operator (as Joey, with CAD_WRITER set). The print file is made separately (hub_plate.py).
export PYTHONDONTWRITEBYTECODE=1      # a __pycache__ under cad/scripts fails the layout check
REPO=/j/code/roark-wt/shoulder-study
cd $REPO/cad/scripts/shoulder || { echo "NOT ADOPTED: $REPO/cad/scripts/shoulder not found. Nothing was changed."; exit 1; }
PY=C:/joe/code/_venvs/shoulder/Scripts/python
W=../../_wip/shoulder-pass1
L=$W/queue5.log
CL="$PY $REPO/tools/pc/claims.py"
CAND=../../exports/shoulder/shoulder_hub_left_revE1_candidate.STL
SEAT=298.86
LK="$PY $REPO/cad/_wip/shoulder-pass1/solve_lock.py"
WP=$(cat /proc/$$/winpid)
CHANGED="Nothing was changed."
DONE=
finish() {
  $LK drop $WP > /dev/null 2>&1
  $CL release shoulder-study-fea > /dev/null 2>&1
  [ -n "$DONE" ] || echo "NOT ADOPTED. $CHANGED"
}
trap finish EXIT
stop() { echo "STOPPED: $1"; exit 1; }
if [ -n "$DRY" ]; then echo 'TRIAL RUN (DRY=1): the rebuild goes into a scratch folder; the real part, the exports and the manifest are not touched.'; fi

# Safe to start while this thread's solves are running: it takes the workstation's solve lock first, which waits for a
# running solve (and its queue's current batch) to finish and holds the next one off until the adoption is done.
echo 'waiting for the solve lock (a running solve finishes first; this can take up to 20 minutes) ...'
$LK take "shoulder hub E1 adoption" $WP || stop 'could not take the solve lock'
[ -f $CAND ] || stop 'no rev E1 candidate export (cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STL)'

# 1. the source part
echo 'step 1 of 5: keeping the rev D3c7 part as the source'
mkdir -p ../../_archive/hub_revD3c7
[ -f ../../_archive/hub_revD3c7/shoulder_hub_left.SLDPRT ] || cp ../../shoulder/left/shoulder_hub_left.SLDPRT ../../_archive/hub_revD3c7/ || stop 'could not copy the hub part to cad/_archive/hub_revD3c7'
[ "$(stat -c %s ../../_archive/hub_revD3c7/shoulder_hub_left.SLDPRT)" -gt 500000 ] || stop 'the archived part is too small to be the rev D3c7 hub (an LFS pointer?)'

# 2. the real part, hidden, with a claim
echo 'step 2 of 5: rebuilding the hub in a hidden SolidWorks (about 2 minutes) ...'
until [ "$(powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)")" -ge 10 ]; do echo '  waiting for 10 GB of free memory'; sleep 60; done
$CL claim shoulder-study-fea --worktree 'J:\code\roark-wt\shoulder-study' --status "adoption: hub rev E1${DRY:+ (trial)}" > /dev/null 2>&1
echo "adoption of hub rev E1${DRY:+ (trial)}: build start $(date +%T)" >> $L
unset LOOK NO_MOVE
if [ -n "$DRY" ]; then
  BL=$W/build_adopt_revE1_trial.txt; ST=.sw_instance_pid_adoptE1dry; OUTSTL=$W/stl_look_adoptdry/hub.stl
  export LOOK=adoptdry HUB_SRC_ARCHIVE=1
else
  BL=$W/build_adopt_revE1.txt; ST=.sw_instance_pid_adoptE1; OUTSTL=$W/stl/hub.stl
  export HUB_ADOPT=1
  CHANGED="The real hub part may have been rewritten: restore it with  git -C $REPO checkout -- cad/shoulder/left/shoulder_hub_left.SLDPRT  (the exports and the manifest were not touched)."
fi
rm -f $BL
SW_VISIBLE=0 TOP_RAISE=3.0 SEAT_Y=$SEAT SW_STATE_NAME=$ST $PY capped.py --mb 6144 -- $PY -u hub_candidate2.py > $BL 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  SP=$(cut -d" " -f1 $W/$ST 2>/dev/null)
  $CL beat shoulder-study-fea ${SP:+--sw-pid $SP} > /dev/null 2>&1
  sleep 5
done
wait $pid; rc=$?
[ $rc -eq 0 ] || { echo "the build's last lines ($BL):"; tail -4 $BL; stop "the hub build ended with exit code $rc"; }
for f_ in "POCKET_FILL_A1: added" "POCKET_FILL_B2: added" "NEW_WIN: cut" "WIN_MOUTH" "SLIT_FILL: added" "PLATE_THICK: added" "TUBE_THICK: added" "PLATE_STEP_FILL: added" "TUBE_FILLET: added 1159" "TOP_RAISE: added" "STEP_FILLET: added" "moved -3.0 in Y" "seat-face hole edges: none" "head seats at Y $SEAT"; do
  grep -q "$f_" $BL || stop "feature missing from the build log ($f_)"
done
grep "integrity:" $BL | tail -1 | grep -q "PASS" || stop 'the hub STL failed the integrity check'
grep -q "== shoulder_hub_left" $BL || stop 'the hub build did not finish'

# 3. the rebuilt hub must be the candidate that was checked
echo 'step 3 of 5: comparing the rebuilt hub with the candidate'
OUTSTL=$OUTSTL $PY capped.py --mb 6144 -- $PY - <<'PYEOF' || stop 'the rebuilt hub is not the rev E1 candidate'
import hashlib, os, sys
import trimesh
a, b = os.environ['OUTSTL'], '../../exports/shoulder/shoulder_hub_left_revE1_candidate.STL'
ha, hb = (hashlib.sha256(open(f, 'rb').read()).hexdigest() for f in (a, b))
print('  rebuilt  ', ha); print('  candidate', hb)
if ha != hb:
    ma, mb = trimesh.load(a), trimesh.load(b)
    worst = 0.0
    for src, dst in ((ma, mb), (mb, ma)):
        pts, _ = trimesh.sample.sample_surface(src, 60000, seed=1)
        worst = max(worst, max(trimesh.proximity.closest_point(dst, pts[i:i + 5000])[1].max() for i in range(0, len(pts), 5000)))
    print('  files differ; largest surface offset %.4f mm, volume %.0f against %.0f mm3' % (worst, ma.volume, mb.volume))
    sys.exit(0 if worst <= 0.01 else 1)
else:
    print('  the same file')
PYEOF
if [ -n "$DRY" ]; then
  DONE=1
  echo "adoption of hub rev E1 (trial): passed $(date +%T)" >> $L
  echo 'TRIAL PASSED: the rebuild from the archived rev D3c7 part reproduces the candidate. Nothing real was changed.'
  echo 'Not covered by the trial: writing the real part, replacing the exports, the manifest, the layout check and the sweep.'
  exit 0
fi

# 4. exports
echo 'step 4 of 5: replacing the exports and their records'
CHANGED="The real hub part IS rev E1 now, but the exports or the manifest may be half done: see the message above; restore everything with  git -C $REPO checkout -- cad/shoulder/left/shoulder_hub_left.SLDPRT cad/exports/shoulder cad/manifests/exports.json"
cd $REPO
cp cad/_wip/shoulder-pass1/step/hub.step cad/exports/shoulder/shoulder_hub_left.STEP || stop 'could not replace shoulder_hub_left.STEP'
cp cad/_wip/shoulder-pass1/stl/hub.stl cad/exports/shoulder/shoulder_hub_left.STL || stop 'could not replace shoulder_hub_left.STL'
for f in STEP STL; do
  C:/Users/holly/AppData/Local/Programs/Python/Python312/python.exe tools/cad/record_export.py \
    exports/shoulder/shoulder_hub_left.$f shoulder/left/shoulder_hub_left.SLDPRT --settings "rev E1: centre 3 mm taller, top slits filled, pocket solid, plate and boss tubes thicker, head seats at Y 298.86 for M4 x 30 with one washer (5.2 mm into the RS02), dog-leg cable slot 4.5 x 11; hub_candidate2.py on the rev D3c7 part" > /dev/null || stop "record_export.py failed for shoulder_hub_left.$f"
done
git rm -q -f --ignore-unmatch cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STL \
  cad/exports/shoulder/shoulder_hub_left_revE1_candidate_armframe.STEP cad/exports/shoulder/shoulder_hub_left_revE1_candidate_armframe.STL || stop 'git rm of the candidate exports failed'
rm -f cad/exports/shoulder/shoulder_hub_left_revE1_candidate*.ST*
$PY - <<'PYEOF' || stop 'could not remove the candidate entries from cad/manifests/exports.json'
import json, io
p = 'cad/manifests/exports.json'; d = json.load(io.open(p, encoding='utf8'))
def drop(x):
    if isinstance(x, dict):
        return {k: drop(v) for k, v in x.items() if 'revE1_candidate' not in k}
    if isinstance(x, list):
        return [drop(v) for v in x if 'revE1_candidate' not in json.dumps(v)]
    return x
json.dump(drop(d), io.open(p, 'w', encoding='utf8'), indent=2)
print('  manifest: candidate entries removed')
PYEOF
rm -rf cad/scripts/shoulder/__pycache__
$PY tools/cad/check_cad_layout.py $REPO/cad || stop 'the layout check reports errors (listed above)'

# 5. the sweep with the arm 3 mm lower
echo 'step 5 of 5: clearance sweep with the arm 3 mm lower (20 to 30 minutes, all cores) ...'
CHANGED="Rev E1 IS adopted in the working tree (part, exports, manifest), but the clearance sweep did not finish: run it again with  cd $REPO/cad/scripts/shoulder && UA_SHIFT_Y=-3.0 CLEAR_JSON=clearance_adopt_hubE1.json $PY check_clearance.py"
cd $REPO/cad/scripts/shoulder
echo "adoption of hub rev E1: clearance sweep start $(date +%T)" >> $L
UA_SHIFT_Y=-3.0 CLEAR_JSON=clearance_adopt_hubE1.json $PY capped.py --mb 6144 -- $PY check_clearance.py > $W/clearance_adopt_hubE1.txt 2>&1; rc=$?
echo "adoption of hub rev E1: sweep done $(date +%T) exit $rc" >> $L
[ $rc -eq 0 ] || { tail -4 $W/clearance_adopt_hubE1.txt; stop "the clearance sweep ended with exit code $rc"; }
DONE=1
echo 'ADOPTED: rev E1 is the hub in the working tree (part, exports, manifest), and the sweep ran. Not committed yet.'
