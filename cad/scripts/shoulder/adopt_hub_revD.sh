#!/bin/bash
# Adopt hub rev D3b (rev D: full-ring groove, full-ring inward fill, the two Ø3.8 locating holes, R1.2 Z-facing lug roots;
# plus D3b: both lugs grown to one straight outer face at X offset 34.4 for the arm's collar pockets (the yaw torque path), R0.8
# outward roots, square spigot edge over the lug bands, the spigot skin remade for a clean mesh) as THE hub part, in one step.
# (D2d's local bore and backing are not part of it: D3 alone carries the yaw and stop cases with >= 30% margin.)
# PREPARED, NOT RUN: run only when the arm thread confirms rev D3b (its final cases on the candidate).
#   bash cad/scripts/shoulder/adopt_hub_revD.sh
# What it does:
#   1. dims.HUB_GROOVE_RING defaults to on (HUB_GROOVE_RING=0 still builds rev C+) and dims.HUB_D3 to on (HUB_D3=0 builds rev D).
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
b = "HUB_D3 = bool(os.environ.get('HUB_D3')) and HUB_GROOVE_RING      # on rev D, with or without D2"
assert b in s, 'D3 switch line not found'
s = s.replace(b, "HUB_D3 = os.environ.get('HUB_D3', '1') != '0' and HUB_GROOVE_RING      # rev D3 adopted")
io.open(p, 'w', encoding='utf8').write(s)
print('dims: HUB_GROOVE_RING and HUB_D3 on by default')
PYEOF

# 2. real hub, own instance, port-cap warm-up
until ! $PY $ST --status 2>/dev/null | grep -qE "busy|HALF" && [ "$(powershell -NoProfile -c "[math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)")" -ge 22 ]; do sleep 30; done
SW_STATE_NAME=.sw_instance_pid_adoptD $PY capped.py --mb 6144 -- $PY -u build_parts.py port_cap hub > $W/build_adopt_revD.txt 2>&1   # under the 6 GB job cap
grep -q "GROOVE_RING" $W/build_adopt_revD.txt || { echo 'rev D groove not in the build log: stopping'; exit 1; }
grep -q "LUG_ZROOTS: R1.2" $W/build_adopt_revD.txt || { echo 'R1.2 Z-root fillet not in the build log: stopping'; exit 1; }
for f_ in "D3_LUG_EXT: added" "LUG_ROOTS: R0.8" "SKIN_RESURF: added" "GROOVE_RING_2: cut" "D3_EDGE_A: added" "D3_EDGE_B: added"; do
  grep -q "$f_" $W/build_adopt_revD.txt || { echo "rev D3b feature missing from the build log ($f_): stopping"; exit 1; }
done
grep "integrity:" $W/build_adopt_revD.txt | tail -1 | grep -q "PASS" || { echo "the hub STL failed the integrity check: stopping"; exit 1; }
grep -q "== shoulder_hub_left" $W/build_adopt_revD.txt || { echo 'hub build did not finish: stopping'; exit 1; }

# 3. exports
cd $REPO
cp cad/_wip/shoulder-pass1/step/hub.step cad/exports/shoulder/shoulder_hub_left.STEP
cp cad/_wip/shoulder-pass1/stl/hub.STL cad/exports/shoulder/shoulder_hub_left.STL
for f in STEP STL; do
  C:/Users/holly/AppData/Local/Programs/Python/Python312/python.exe tools/cad/record_export.py \
    exports/shoulder/shoulder_hub_left.$f shoulder/left/shoulder_hub_left.SLDPRT --settings "rev D3b: full-ring groove and fill, 2 x Ø3.8 locating holes, R1.2 Z lug roots, lugs to X 34.4 with R0.8 outward roots (yaw torque path)"
done
git rm -q --ignore-unmatch cad/exports/shoulder/shoulder_hub_left_revD_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revD_candidate.STL \
  cad/exports/shoulder/shoulder_hub_left_revD2_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revD2_candidate.STL \
  cad/exports/shoulder/shoulder_hub_left_revD3_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revD3_candidate.STL \
  cad/exports/shoulder/shoulder_hub_left_revD3b_candidate.STEP cad/exports/shoulder/shoulder_hub_left_revD3b_candidate.STL
$PY - <<'PYEOF'
import json, io
p = 'cad/manifests/exports.json'; d = json.load(io.open(p, encoding='utf8'))
def drop(x):
    if isinstance(x, dict):
        return {k: drop(v) for k, v in x.items() if not any(c_ in k for c_ in ('revD_candidate', 'revD2_candidate', 'revD3_candidate', 'revD3b_candidate'))}
    if isinstance(x, list):
        return [drop(v) for v in x if not any(c_ in json.dumps(v) for c_ in ('revD_candidate', 'revD2_candidate', 'revD3_candidate', 'revD3b_candidate'))]
    return x
json.dump(drop(d), io.open(p, 'w', encoding='utf8'), indent=2)
print('manifest: candidate entries removed')
PYEOF

# 4. check
$PY tools/cad/check_cad_layout.py $REPO/cad
echo 'Rev D3b adopted in the working tree. Next: re-run the clearance sweep (the hub outline does not change), commit as Joey, push.'
