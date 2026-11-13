#!/bin/bash
# Adopt hub rev D2d (rev D: full-ring groove, full-ring inward fill, the two Ø3.8 locating holes, R1.2 Z-facing lug roots;
# plus D2d: the local r 20 bore behind the -X lug, the cable-sector r 21 bore and the -X lug backing) as THE hub part, in one step.
# PREPARED, NOT RUN: run only when the arm thread confirms rev D2d (HUBL_YAW and its combined pass on the candidate).
#   bash cad/scripts/shoulder/adopt_hub_revD.sh
# What it does:
#   1. dims.HUB_GROOVE_RING defaults to on (HUB_GROOVE_RING=0 still builds rev C+) and dims.HUB_D2 to 'd' (HUB_D2= builds rev D).
#   2. Rebuilds the real hub in its own instance, warming up on the port cap first (a fresh instance hangs on the hub
#      STEP import otherwise). Launch only when --status is quiet.
#   3. Replaces the released exports cad/exports/shoulder/shoulder_hub_left.STEP/.STL with the rev D ones and records
#      them against the hub part; removes the candidate exports and their manifest entries.
#   4. Runs the layout check. The commit is left to the operator (as Joey, with CAD_WRITER set).
set -e
REPO=/j/code/roark-wt/shoulder-study
cd $REPO/cad/scripts/shoulder
PY=C:/joe/code/_venvs/shoulder/Scripts/python
ST=$REPO/tools/solidworks/sw_instance.py
W=../../_wip/shoulder-pass1

# 1. the switch
$PY - <<'PYEOF'
import io
p = 'dims.py'; s = io.open(p, encoding='utf8').read()
a = "HUB_GROOVE_RING = bool(os.environ.get('HUB_GROOVE_RING'))"
assert a in s, 'switch line not found'
s = s.replace(a, "HUB_GROOVE_RING = os.environ.get('HUB_GROOVE_RING', '1') != '0'   # rev D adopted")
b = "HUB_D2 = os.environ.get('HUB_D2', '') if HUB_GROOVE_RING else ''"
assert b in s, 'D2 switch line not found'
s = s.replace(b, "HUB_D2 = os.environ.get('HUB_D2', 'd') if HUB_GROOVE_RING else ''   # rev D2d adopted")
io.open(p, 'w', encoding='utf8').write(s)
print('dims: HUB_GROOVE_RING on and HUB_D2 = d by default')
PYEOF

# 2. real hub, own instance, port-cap warm-up
until ! $PY $ST --status 2>/dev/null | grep -qE "busy|HALF" && [ "$(powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)")" -ge 22 ]; do sleep 30; done
SW_STATE_NAME=.sw_instance_pid_adoptD $PY capped.py --mb 6144 -- $PY -u build_parts.py port_cap hub > $W/build_adopt_revD.txt 2>&1   # under the 6 GB job cap
grep -q "GROOVE_RING" $W/build_adopt_revD.txt || { echo 'rev D groove not in the build log: stopping'; exit 1; }
grep -q "LUG_ZROOTS: R1.2" $W/build_adopt_revD.txt || { echo 'R1.2 Z-root fillet not in the build log: stopping'; exit 1; }
for f_ in "D2_LOCAL: added" "D2_FILL_CS: added" "D2_BACK: added" "D2_DRIVER: cut"; do
  grep -q "$f_" $W/build_adopt_revD.txt || { echo "rev D2d feature missing from the build log ($f_): stopping"; exit 1; }
done
grep -q "== shoulder_hub_left" $W/build_adopt_revD.txt || { echo 'hub build did not finish: stopping'; exit 1; }

# 3. exports
cd $REPO
cp cad/_wip/shoulder-pass1/step/hub.step cad/exports/shoulder/shoulder_hub_left.STEP
cp cad/_wip/shoulder-pass1/stl/hub.STL cad/exports/shoulder/shoulder_hub_left.STL
for f in STEP STL; do
  C:/Users/holly/AppData/Local/Programs/Python/Python312/python.exe tools/cad/record_export.py \
    exports/shoulder/shoulder_hub_left.$f shoulder/left/shoulder_hub_left.SLDPRT --settings "rev D2d: full-ring groove and fill, 2 x Ø3.8 locating holes, R1.2 Z lug roots, local r 20 bore and backing at the -X lug"
done
git rm -q --ignore-unmatch cad/exports/shoulder/shoulder_hub_left_revD_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revD_candidate.STL \
  cad/exports/shoulder/shoulder_hub_left_revD2_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revD2_candidate.STL
$PY - <<'PYEOF'
import json, io
p = 'cad/manifests/exports.json'; d = json.load(io.open(p, encoding='utf8'))
def drop(x):
    if isinstance(x, dict):
        return {k: drop(v) for k, v in x.items() if 'revD_candidate' not in k and 'revD2_candidate' not in k}
    if isinstance(x, list):
        return [drop(v) for v in x if 'revD_candidate' not in json.dumps(v) and 'revD2_candidate' not in json.dumps(v)]
    return x
json.dump(drop(d), io.open(p, 'w', encoding='utf8'), indent=2)
print('manifest: candidate entries removed')
PYEOF

# 4. check
$PY tools/cad/check_cad_layout.py $REPO/cad
echo 'Rev D2d adopted in the working tree. Next: re-run the clearance sweep (the hub outline does not change), commit as Joey, push.'
