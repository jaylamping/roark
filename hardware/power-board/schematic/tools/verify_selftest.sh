#!/bin/bash
# verify_selftest.sh [work dir] : show that the checks can fail. Builds deliberately broken copies of the routed board
# (tools/mutate.py) and of the rule and BOM files in a scratch dir, runs each check on its broken input and expects the
# failure it was built to cause; then the same checks must pass on the real board (tools/verify_board.sh, run last).
# Nothing in the repository is changed. Exit 1 if a check passes a broken input. About 10 minutes.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
ROOT=$(wp "$(dirname "$0")/.."); LAYOUT=$(wp "$ROOT/../layout"); PB=$(wp "$ROOT/.."); T="$ROOT/tools"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KCLI="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KCLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
W=${1:-$(mktemp -d)}; mkdir -p "$W"; W=$(wp "$W")
q() { grep -v 'memory leak\|GetWidth called\|image handler'; }
bad=0
expect() {   # expect <label> <file> <regex>...: every regex must match a line of the file
  local label=$1 f=$2; shift 2
  for rx in "$@"; do
    if grep -Eq -- "$rx" "$f"; then echo "   caught: $label: $(grep -E -m1 -- "$rx" "$f" | cut -c1-150)"
    else echo "   NOT CAUGHT: $label (no line matches: $rx)"; bad=1; fi
  done
}
# the real board, refilled with the project rules, is the base of every broken copy
KEEP="$W/real" bash "$T/verify_board.sh" > "$W/real.txt" 2>&1; real=$?
BASE="$W/real/verify.kicad_pcb"
[ -s "$BASE" ] || { cat "$W/real.txt"; echo 'no base board'; exit 1; }

echo '--- route_checks.py on the "rules" copy'
"$KP" "$T/mutate.py" "$BASE" "$W/rules.kicad_pcb" rules 2>&1 | q
"$KP" "$T/route_checks.py" "$W/rules.kicad_pcb" > "$W/rules.txt" 2>&1; rc=$?
[ "$rc" != 0 ] && echo "   route_checks exit $rc" || { echo '   NOT CAUGHT: route_checks exit 0'; bad=1; }
expect 'checks 1/2: a 0.2 mm pair, at U8 with no courtyard relaxation' "$W/rules.txt" "'/EN_A', 'track'.*'GND', 'U8\.2'.*<0\.2 mm"
expect 'check 3: Kelvin floor' "$W/rules.txt" "\('/SHL3', '.*paired, floor 56"
expect 'check 4: 54 V-riding net under the latch block' "$W/rules.txt" "'In2\.Cu', '/GATE', 'track'"
expect 'check 7: excepted via pinned to its position' "$W/rules.txt" "\('/G2', \(150\.2, 160\.19\), 'not a listed exception'\)"
expect 'check 8: PRE_G is a gate net; GATE_A via off its position' "$W/rules.txt" "\('/PRE_G', 3, 'vias, allowed', 2\)" "\('/GATE_A', 3, 'vias; not at a listed position:', \[\(168\.55, 165\.1\)\]\)"
expect 'check 9: stale E-stop guard' "$W/rules.txt" "stale ESTOP_GUARD_U8_1"
expect 'check 10: latch supply near a leakage-sensitive net' "$W/rules.txt" "^10\. .*: [1-9][0-9]* item pairs"

echo '--- the copper checks on the "copper" copy'
"$KP" "$T/mutate.py" "$BASE" "$W/copper.kicad_pcb" copper 2>&1 | q
"$KP" "$T/joint_check.py" "$W/copper.kicad_pcb" > "$W/c1.txt" 2>&1 && { echo '   NOT CAUGHT: joint_check exit 0'; bad=1; }
expect 'joint_check: tangent joint' "$W/c1.txt" "WEAK /G_L2 F\.Cu 0\.0 "
MODE=check "$KP" "$T/port_template.py" "$W/copper.kicad_pcb" > "$W/c2.txt" 2>&1 && { echo '   NOT CAUGHT: port_template check exit 0'; bad=1; }
expect 'port_template MODE=check' "$W/c2.txt" "port 2 missing: /G_L2"
MODE=check "$KP" "$T/u8_block.py" "$W/copper.kicad_pcb" > "$W/c3.txt" 2>&1 && { echo '   NOT CAUGHT: u8_block check exit 0'; bad=1; }
expect 'u8_block MODE=check' "$W/c3.txt" "U8 block missing: /FLT_A"
"$KP" "$T/pour_width.py" "$W/copper.kicad_pcb" > "$W/c4.txt" 2>&1 && { echo '   NOT CAUGHT: pour_width exit 0'; bad=1; }
expect 'pour_width: rise over the limit, one more via in the band' "$W/c4.txt" "VBUS stem.*FAIL" "VBUS band.*FAIL"

echo '--- verify_board.sh: DRC types outside the allow-list, and a kicad-cli that fails or reports nothing'
"$KP" "$T/mutate.py" "$BASE" "$W/dangle.kicad_pcb" dangle 2>&1 | q
KEEP="$W/dangle" bash "$T/verify_board.sh" "$W/dangle.kicad_pcb" > "$W/d1.txt" 2>&1 && { echo '   NOT CAUGHT: verify_board passed a dangling track'; bad=1; }
expect 'DRC type outside the allow-list' "$W/d1.txt" "FAIL: DRC \{'track_dangling': 1\}" "verify_board: FAIL"
# stand-ins for kicad-cli: one exits 3 after writing a report, one writes a report without the parity key, one writes nothing
mkdir -p "$W/stub"
printf '#!/bin/bash\nfor a in "$@"; do case "$p" in -o) out=$a;; esac; p=$a; done\necho "{\\"violations\\":[],\\"unconnected_items\\":[],\\"schematic_parity\\":[]}" > "$out"\nexit 3\n' > "$W/stub/exit3.sh"
printf '#!/bin/bash\nfor a in "$@"; do case "$p" in -o) out=$a;; esac; p=$a; done\necho "{\\"violations\\":[],\\"unconnected_items\\":[]}" > "$out"\nexit 0\n' > "$W/stub/nokey.sh"
printf '#!/bin/bash\nexit 0\n' > "$W/stub/silent.sh"
chmod +x "$W/stub/"*.sh
KC="$W/stub/exit3.sh" KEEP="$W/s1" bash "$T/verify_board.sh" > "$W/s1.txt" 2>&1 && { echo '   NOT CAUGHT: kicad-cli exit 3'; bad=1; }
expect 'kicad-cli exits non-zero' "$W/s1.txt" "FAIL: kicad-cli pcb drc exited 3"
KC="$W/stub/nokey.sh" KEEP="$W/s2" bash "$T/verify_board.sh" > "$W/s2.txt" 2>&1 && { echo '   NOT CAUGHT: no parity key'; bad=1; }
expect 'report without the parity key' "$W/s2.txt" "no schematic_parity key"
mkdir -p "$W/s3"; echo '{"violations":[],"unconnected_items":[],"schematic_parity":[]}' > "$W/s3/drc.json"   # an old report lying in the work dir
KC="$W/stub/silent.sh" KEEP="$W/s3" bash "$T/verify_board.sh" > "$W/s3.txt" 2>&1 && { echo '   NOT CAUGHT: stale report'; bad=1; }
expect 'no fresh report (an old one in the work dir is not used)' "$W/s3.txt" "FAIL: DRC wrote no report"

echo '--- check.py and bom_check.py on broken rule and BOM files'
"$PY" - "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/noestop.kicad_pro" <<'PYEOF'
import json,sys
d=json.load(open(sys.argv[1])); p=d['net_settings']['netclass_patterns']
d['net_settings']['netclass_patterns']=[x for x in p if x['pattern']!='/SP_ENR']; json.dump(d,open(sys.argv[2],'w'))
PYEOF
"$PY" -I "$T/check.py" "$T" "$W/real/net.net" "$W/noestop.kicad_pro" > "$W/k1.txt" 2>&1 && { echo '   NOT CAUGHT: check.py exit 0'; bad=1; }
expect 'check.py: ESTOP class against domains.py' "$W/k1.txt" "^FAIL .kicad_pro net class ESTOP equals tools/domains.py: missing \['/SP_ENR'\]"
mkdir -p "$W/baddru"; cp "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/baddru/x.kicad_pro"
sed 's/(constraint clearance (min 1.5mm))$/(constraint clearance (min 1.5mm)/' "$LAYOUT/marengo_pdu_revb.kicad_dru" > "$W/baddru/x.kicad_dru"   # two parentheses lost
"$PY" -I "$T/check.py" "$T" "$W/real/net.net" "$W/baddru/x.kicad_pro" > "$W/k3.txt" 2>&1 && { echo '   NOT CAUGHT: check.py passed a malformed rules file'; bad=1; }
expect 'check.py: a rules file that does not parse (kicad-cli drops it silently)' "$W/k3.txt" "^FAIL .kicad_dru is well formed"
mkdir -p "$W/pb/buck12"; cp "$PB/bom-rev-B.csv" "$PB/kit-2sets.csv" "$W/pb/"; cp "$PB/buck12/bom-buck12.csv" "$W/pb/buck12/"
sed -i 's/6 +3V3_PI, 7-8 GND, 9 SP_EN, 10 GND, 11 SCL, 12 SDA/6 GND, 7 +3V3_PI, 8 SDA, 9 GND, 10 SCL, 11 SP_EN, 12 GND/' "$W/pb/bom-rev-B.csv" "$W/pb/kit-2sets.csv" "$W/pb/buck12/bom-buck12.csv"
"$PY" -I "$T/bom_check.py" "$T" "$W/real/net.net" "$W/pb" "$W/real/buck.net" > "$W/k2.txt" 2>&1 && { echo '   NOT CAUGHT: bom_check exit 0'; bad=1; }
expect 'bom_check: the old J24 pinout rows' "$W/k2.txt" "^FAIL bom-rev-B.csv" "^FAIL kit-2sets.csv main J24" "^FAIL bom-buck12.csv" "^FAIL kit-2sets.csv buck J1"

echo '--- the real board'
tail -1 "$W/real.txt"
[ "$real" = 0 ] || { grep FAIL "$W/real.txt"; bad=1; }
echo "work files: $W"
[ "$bad" = 0 ] && echo 'verify_selftest: every broken input was caught, the real board passes' || { echo 'verify_selftest: FAIL'; exit 1; }
