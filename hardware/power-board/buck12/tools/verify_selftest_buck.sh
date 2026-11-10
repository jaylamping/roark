#!/bin/bash
# verify_selftest_buck.sh [work dir] : show that the buck board's checks can fail. Builds broken copies of the board
# (tools/mutate_buck.py) and of the order package, runs verify_buck.sh / fab_check_buck.sh on each and expects the failure it
# was built to cause; then verify_buck.sh must pass on the real board. Nothing in the repository changes. About 10 minutes.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
B=$(wp "$(dirname "$0")/.."); BRD="$B/layout/marengo_buck12.kicad_pcb"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"
[ -x "$KP" ] || KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
W=${1:-$(mktemp -d)}; mkdir -p "$W"; W=$(wp "$W"); bad=0
q() { grep -v 'memory leak\|GetWidth called\|image handler'; }
expect() {   # expect <label> <file> <regex>...
  local label=$1 f=$2; shift 2
  for rx in "$@"; do
    if grep -Eq -- "$rx" "$f"; then echo "   caught: $label: $(grep -E -m1 -- "$rx" "$f" | cut -c1-150)"
    else echo "   NOT CAUGHT: $label (no line matches: $rx)"; bad=1; fi
  done
}
broken() {   # broken <kind> <label> <regex>...: verify_buck.sh must fail on the mutated board and print the regexes
  local kind=$1 label=$2; shift 2
  "$KP" "$B/tools/mutate_buck.py" "$BRD" "$W/$kind.kicad_pcb" "$kind" 2>&1 | q
  KEEP="$W/v_$kind" bash "$B/tools/verify_buck.sh" "$W/$kind.kicad_pcb" > "$W/$kind.txt" 2>&1 && { echo "   NOT CAUGHT: $label: verify_buck passed"; bad=1; }
  expect "$label" "$W/$kind.txt" "$@" "verify_buck: FAIL"
}
echo '--- verify_buck.sh on broken boards'
broken dangle 'DRC type outside the allow-list' "FAIL: DRC \{'track_dangling': 1\}"
broken parity 'schematic parity' "FAIL: schematic parity [1-9]"
broken spen 'SP_EN within 1.5 mm of the 54 V copper' "^SP_EN within 1.5 mm of 54 V copper: [1-9]" "FAIL: spacing_buck"
broken designed 'designed copper and the gate joint' "designed copper missing: /HO" "designed copper missing: /LO" "FAIL: designed copper differs"
broken slot 'pour width: a cut across +12V and VOUT' "\+12V, RS1 into the distribution pour.*FAIL" "VOUT, L2 to RS1.*FAIL"
echo '--- verify_buck.sh with a kicad-cli that fails or reports nothing'
mkdir -p "$W/stub"
printf '#!/bin/bash\nfor a in "$@"; do case "$p" in -o) out=$a;; esac; p=$a; done\necho "{\\"violations\\":[],\\"unconnected_items\\":[],\\"schematic_parity\\":[]}" > "$out"\nexit 3\n' > "$W/stub/exit3.sh"
printf '#!/bin/bash\nfor a in "$@"; do case "$p" in -o) out=$a;; esac; p=$a; done\necho "{\\"violations\\":[],\\"unconnected_items\\":[]}" > "$out"\nexit 0\n' > "$W/stub/nokey.sh"
printf '#!/bin/bash\nexit 0\n' > "$W/stub/silent.sh"; chmod +x "$W/stub/"*.sh
KC="$W/stub/exit3.sh" KEEP="$W/s1" bash "$B/tools/verify_buck.sh" > "$W/s1.txt" 2>&1 && { echo '   NOT CAUGHT: kicad-cli exit 3'; bad=1; }
expect 'kicad-cli exits non-zero' "$W/s1.txt" "FAIL: kicad-cli pcb drc exited 3"
KC="$W/stub/nokey.sh" KEEP="$W/s2" bash "$B/tools/verify_buck.sh" > "$W/s2.txt" 2>&1 && { echo '   NOT CAUGHT: no parity key'; bad=1; }
expect 'report without the parity key' "$W/s2.txt" "no schematic_parity key"
mkdir -p "$W/s3"; echo '{"violations":[],"unconnected_items":[],"schematic_parity":[]}' > "$W/s3/drc.json"
KC="$W/stub/silent.sh" KEEP="$W/s3" bash "$B/tools/verify_buck.sh" > "$W/s3.txt" 2>&1 && { echo '   NOT CAUGHT: stale report'; bad=1; }
expect 'no fresh report' "$W/s3.txt" "FAIL: DRC wrote no report"
echo '--- fab_check_buck.sh on broken order packages'
fabcopy() { rm -rf "$W/$1"; mkdir -p "$W/$1"; cp -r "$B/fab/." "$W/$1/"; }
fabcopy fab1
"$PY" - "$W/fab1/marengo_buck12-pos.csv" <<'PYEOF'
import sys; p=sys.argv[1]; L=open(p,encoding='utf-8').read().split('\n'); f=L[1].split(','); f[3]='%.6f'%(float(f[3])+0.5); L[1]=','.join(f)
open(p,'w',encoding='utf-8',newline='').write('\n'.join(L))
PYEOF
bash "$B/tools/fab_check_buck.sh" "$BRD" "$W/fab1" > "$W/f1.txt" 2>&1 && { echo '   NOT CAUGHT: a moved part'; bad=1; }
expect 'fab_check: position file off the board' "$W/f1.txt" "^FAIL position file: X, Y, rotation and side.*1 differ"
fabcopy fab2; rm -f "$W/fab2/gerbers/marengo_buck12-In2_Cu.g2"
bash "$B/tools/fab_check_buck.sh" "$BRD" "$W/fab2" > "$W/f2.txt" 2>&1 && { echo '   NOT CAUGHT: a missing Gerber'; bad=1; }
expect 'fab_check: a Gerber missing' "$W/f2.txt" "^FAIL gerbers/ holds the 12 Gerber and 2 drill files: missing \['marengo_buck12-In2_Cu.g2'\]"
fabcopy fab3; rm -rf "$W/fab3/gerbers"
bash "$B/tools/fab_check_buck.sh" "$BRD" "$W/fab3" > "$W/f3.txt" 2>&1 && { echo '   NOT CAUGHT: no gerbers/'; bad=1; }
expect 'fab_check: gerbers/ missing' "$W/f3.txt" "^FAIL .*gerbers exists"
echo '--- the real board'
KEEP="$W/real" bash "$B/tools/verify_buck.sh" > "$W/real.txt" 2>&1; real=$?
tail -1 "$W/real.txt"; [ "$real" = 0 ] || { grep FAIL "$W/real.txt"; bad=1; }
echo "work files: $W"
[ "$bad" = 0 ] && echo 'verify_selftest_buck: every broken input was caught, the real board passes' || { echo 'verify_selftest_buck: FAIL'; exit 1; }
