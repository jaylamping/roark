#!/bin/bash
# Adopt hub rev E1 as THE hub part, in one step. Rev E1 = rev D3c7 with, at the top (hub_candidate2.py):
#   - the centre 2 mm taller (cable gap under the RS02 7.5 mm; the hub and the arm sit 2 mm lower on the yaw axis),
#   - the six through-slits in the top (r 19.0-19.5) filled,
#   - the inner pocket filled solid, the centre plate 4 mm thicker, the six boss tubes dia 10.8,
#   - the cable slot 4.5 x 11 as a dog-leg clear of the step ring, with rounded mouth, knee and corners,
#   - R 2 from the step wall into the dish floor.
# The candidate it must reproduce: cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STL (its SHA-256 is read below).
# PREPARED, NOT RUN: run only on the coordinator's word, after the arm thread's go.
#   bash cad/scripts/shoulder/adopt_hub_revE1.sh
# What it does:
#   1. Keeps the present real hub part (rev D3c7) in cad/_archive/hub_revD3c7/ (not in git), the source of the rebuild.
#   2. Rebuilds the real part from that copy in its own hidden instance (hub_candidate2.py, HUB_ADOPT=1), with a claim.
#   3. Checks the rebuilt STL against the candidate: the same file, or the same surface within 0.01 mm.
#   4. Replaces cad/exports/shoulder/shoulder_hub_left.STEP/.STL, records them, removes the candidate files and their
#      manifest entries, runs the layout check.
#   5. Runs the clearance sweep with the arm 2 mm lower (UA_SHIFT_Y=-2). No SolidWorks may be in set-up beside it.
# The commit is left to the operator (as Joey, with CAD_WRITER set). The print file is made separately (hub_plate.py).
set -e
REPO=/j/code/roark-wt/shoulder-study
cd $REPO/cad/scripts/shoulder
PY=C:/joe/code/_venvs/shoulder/Scripts/python
W=../../_wip/shoulder-pass1
L=$W/queue5.log
CL="$PY $REPO/tools/pc/claims.py"
CAND=../../exports/shoulder/shoulder_hub_left_revE1_candidate.STL
[ -f $CAND ] || { echo 'no rev E1 candidate export: stopping'; exit 1; }

# 1. the source part
mkdir -p ../../_archive/hub_revD3c7
[ -f ../../_archive/hub_revD3c7/shoulder_hub_left.SLDPRT ] || cp ../../shoulder/left/shoulder_hub_left.SLDPRT ../../_archive/hub_revD3c7/
$PY - <<'PYEOF' || { echo 'the archived part is not rev D3c7 (63202 mm3 expected in its last build log): stopping'; exit 1; }
import os, sys
sys.exit(0 if os.path.getsize('../../_archive/hub_revD3c7/shoulder_hub_left.SLDPRT') > 500000 else 1)
PYEOF

# 2. the real part, hidden, with a claim
until [ "$(powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)")" -ge 10 ]; do sleep 60; done
$CL claim shoulder-study-fea --worktree 'J:\code\roark-wt\shoulder-study' --status "adoption: hub rev E1" > /dev/null 2>&1
trap '$CL release shoulder-study-fea > /dev/null 2>&1' EXIT
echo "adoption of hub rev E1: build start $(date +%T)" >> $L
unset LOOK
SW_VISIBLE=0 HUB_ADOPT=1 TOP_RAISE=2.0 SW_STATE_NAME=.sw_instance_pid_adoptE1 $PY capped.py --mb 6144 -- $PY -u hub_candidate2.py > $W/build_adopt_revE1.txt 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  SP=$(cut -d" " -f1 $W/.sw_instance_pid_adoptE1 2>/dev/null)
  $CL beat shoulder-study-fea ${SP:+--sw-pid $SP} > /dev/null 2>&1
  sleep 5
done
wait $pid
for f_ in "POCKET_FILL_A1: added" "POCKET_FILL_B2: added" "NEW_WIN: cut" "WIN_MOUTH" "SLIT_FILL: added" "PLATE_THICK: added" "TUBE_THICK: added" "TOP_RAISE: added" "STEP_FILLET: added" "moved -2.0 in Y"; do
  grep -q "$f_" $W/build_adopt_revE1.txt || { echo "feature missing from the build log ($f_): stopping"; exit 1; }
done
grep "integrity:" $W/build_adopt_revE1.txt | tail -1 | grep -q "PASS" || { echo 'the hub STL failed the integrity check: stopping'; exit 1; }
grep -q "== shoulder_hub_left" $W/build_adopt_revE1.txt || { echo 'hub build did not finish: stopping'; exit 1; }

# 3. the rebuilt hub must be the candidate the arm thread checked
$PY capped.py --mb 6144 -- $PY - <<'PYEOF' || { echo 'the rebuilt hub is not the rev E1 candidate: stopping'; exit 1; }
import hashlib, sys
import trimesh
a, b = '../../_wip/shoulder-pass1/stl/hub.stl', '../../exports/shoulder/shoulder_hub_left_revE1_candidate.STL'
ha, hb = (hashlib.sha256(open(f, 'rb').read()).hexdigest() for f in (a, b))
print('rebuilt', ha); print('candidate', hb)
if ha != hb:
    ma, mb = trimesh.load(a), trimesh.load(b)
    worst = 0.0
    for src, dst in ((ma, mb), (mb, ma)):
        pts, _ = trimesh.sample.sample_surface(src, 60000, seed=1)
        worst = max(worst, max(trimesh.proximity.closest_point(dst, pts[i:i + 5000])[1].max() for i in range(0, len(pts), 5000)))
    print('files differ; largest surface offset %.4f mm, volume %.0f against %.0f mm3' % (worst, ma.volume, mb.volume))
    sys.exit(0 if worst <= 0.01 else 1)
PYEOF

# 4. exports
cd $REPO
cp cad/_wip/shoulder-pass1/step/hub.step cad/exports/shoulder/shoulder_hub_left.STEP
cp cad/_wip/shoulder-pass1/stl/hub.stl cad/exports/shoulder/shoulder_hub_left.STL
for f in STEP STL; do
  C:/Users/holly/AppData/Local/Programs/Python/Python312/python.exe tools/cad/record_export.py \
    exports/shoulder/shoulder_hub_left.$f shoulder/left/shoulder_hub_left.SLDPRT --settings "rev E1: centre 2 mm taller, top slits filled, pocket solid, plate and boss tubes thicker, dog-leg cable slot 4.5 x 11; hub_candidate2.py on the rev D3c7 part" > /dev/null
done
git rm -q --ignore-unmatch cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revE1_candidate.STL \
  cad/exports/shoulder/shoulder_hub_left_revE1_candidate_armframe.STEP cad/exports/shoulder/shoulder_hub_left_revE1_candidate_armframe.STL
rm -f cad/exports/shoulder/shoulder_hub_left_revE1_candidate*.ST*
$PY - <<'PYEOF'
import json, io
p = 'cad/manifests/exports.json'; d = json.load(io.open(p, encoding='utf8'))
def drop(x):
    if isinstance(x, dict):
        return {k: drop(v) for k, v in x.items() if 'revE1_candidate' not in k}
    if isinstance(x, list):
        return [drop(v) for v in x if 'revE1_candidate' not in json.dumps(v)]
    return x
json.dump(drop(d), io.open(p, 'w', encoding='utf8'), indent=2)
print('manifest: candidate entries removed')
PYEOF
$PY tools/cad/check_cad_layout.py $REPO/cad

# 5. the sweep with the arm 2 mm lower
cd $REPO/cad/scripts/shoulder
echo "adoption of hub rev E1: clearance sweep start $(date +%T)" >> $L
UA_SHIFT_Y=-2.0 CLEAR_JSON=clearance_adopt_hubE1.json $PY capped.py --mb 6144 -- $PY check_clearance.py > $W/clearance_adopt_hubE1.txt 2>&1
echo "adoption of hub rev E1: sweep done $(date +%T) exit $?" >> $L
echo 'Rev E1 adopted in the working tree. Next: read the sweep, make the print file, commit as Joey, push.'
