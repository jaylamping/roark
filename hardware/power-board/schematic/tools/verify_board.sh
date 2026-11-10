#!/bin/bash
# verify_board.sh [board.kicad_pcb] : the full check set on a routed board (default: ../layout/marengo_pdu_revb.kicad_pcb).
# Copies the board next to a copy of the schematic and the project rules in a temp dir, so KiCad's schematic-parity check
# can read the netlist (run in layout/ it only prints "Failed to fetch schematic netlist" and checks nothing), refills
# the zones with the project rules there, and runs:
#   kicad-cli DRC with parity   every violation type fails, except the ones in ALLOW below
#   tools/open_nets.py          more than OPEN_MAX open connections fails (default 0)
#   tools/route_checks.py       spacing by domain, latch block, E-stop vias and guards, excepted vias, Kelvin floors
#   tools/joint_check.py        every joint has 0.1 mm of real copper overlap
#   tools/port_template.py, tools/u8_block.py, tools/latch_block.py and tools/lay_path.py @hand_laid.specs with MODE=check
#                               the designed blocks' and the hand-laid copper equal the scripts
#   tools/pour_width.py         60 A pours: temperature rise at the narrowest cut, vias in the VBUS band
#   tools/heatsink_pads.py MODE=check   the bare B.Mask openings under the FET tabs are the generated set
#   tools/fab_check.py          the order package in ../fab against the board file it must have been made from (fails
#                               when ../fab/gerbers is missing; the default board only)
#   tools/check.py              the netlist, and the project's ESTOP / HV54 net classes against tools/domains.py
#   tools/bom_check.py          the BOM files and the kit's J24 / J1 pinout rows against the two netlists
# Exit 1 on any failure, and also when kicad-cli exits non-zero, when the DRC report is missing, older than this run or
# has no schematic_parity key, or when the parity check was skipped.
# The board file itself is not changed. KEEP=<dir> keeps the work files there.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }   # a Windows path for the Windows Pythons
ROOT=$(wp "$(dirname "$0")/.."); LAYOUT=$(wp "$ROOT/../layout"); PB=$(wp "$ROOT/..")
B=${1:-$LAYOUT/marengo_pdu_revb.kicad_pcb}; B=$(wp "$(dirname "$B")")/$(basename "$B")
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KCLI="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KCLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
KC=${KC:-$KCLI}   # KC=<program>: tools/verify_selftest.sh puts a failing stand-in here for the DRC run only
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
q() { grep -v 'memory leak\|GetWidth called\|image handler'; }
W=${KEEP:-$(mktemp -d)}; mkdir -p "$W"; W=$(cd "$W" && (pwd -W 2>/dev/null || pwd))
rm -f "$W/drc.json" "$W/net.net" "$W/buck.net"; : > "$W/.start"
cp "$B" "$W/verify.kicad_pcb" && cp "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/verify.kicad_pro" && cp "$LAYOUT/marengo_pdu_revb.kicad_dru" "$W/verify.kicad_dru" \
  && cp "$ROOT/marengo_pdu_revb.kicad_sch" "$W/verify.kicad_sch" && cp "$ROOT/marengo_pdu_revb.kicad_sch" "$W/marengo_pdu_revb.kicad_sch" \
  && cp "$ROOT/marengo_revb.kicad_sym" "$ROOT/sym-lib-table" "$ROOT/fp-lib-table" "$W/" && cp -r "$ROOT/marengo_revb.pretty" "$W/" || { echo 'copying the project files failed'; exit 1; }
fail=0
# MARENGO_HV_EXTRA (tools/domains.py) is a what-if for route_checks.py: a board checked under it is not the board's verdict
[ -z "${MARENGO_HV_EXTRA:-}" ] || { echo "FAIL: MARENGO_HV_EXTRA is set ($MARENGO_HV_EXTRA): unset it to verify the board"; exit 1; }
"$KC" pcb drc --refill-zones --save-board --severity-all --format json --schematic-parity -o "$W/drc.json" "$W/verify.kicad_pcb" > "$W/drc.log" 2>&1; rc=$?
[ "$rc" = 0 ] || { cat "$W/drc.log"; echo "FAIL: kicad-cli pcb drc exited $rc"; fail=1; }
[ -s "$W/drc.json" ] || { cat "$W/drc.log"; echo 'FAIL: DRC wrote no report'; exit 1; }
[ "$W/drc.json" -nt "$W/.start" ] || { echo 'FAIL: the DRC report is older than this run'; exit 1; }
if grep -qi 'failed to fetch schematic' "$W/drc.log"; then cat "$W/drc.log"; echo 'FAIL: the schematic parity check did not run'; exit 1; fi
"$PY" - "$W/drc.json" "${OPEN_MAX:-0}" <<'PYEOF' || fail=1
import json,collections,sys
# DRC violation types that do not fail the board. Everything else does, whatever KiCad adds later.
ALLOW={
 'silk_overlap':        'cosmetic: reference texts overlap on the dense blocks; the assembly drawing carries the references',
 'silk_over_copper':    'cosmetic: the fab clips silkscreen at pads',
 'silk_edge_clearance': 'cosmetic: connector outlines drawn to the board edge',
}
d=json.load(open(sys.argv[1])); v=collections.Counter(x['type'] for x in d['violations'])
if 'schematic_parity' not in d: print('FAIL: the DRC report has no schematic_parity key (parity was not checked)'); sys.exit(1)
par=d['schematic_parity']; un=len(d['unconnected_items'])
hard={k:n for k,n in v.items() if k not in ALLOW}
print('DRC violations',dict(hard),'allowed',{k:n for k,n in v.items() if k in ALLOW},'unconnected',un,'parity',len(par))
for x in d['violations']:
    if x['type'] in hard: print('   ',x['type'],x['description'][:100],[(i['description'][:50],i['pos']['x'],i['pos']['y']) for i in x['items']][:2])
for x in par[:20]: print('   parity:',x['type'],x['description'][:110],x['items'][0]['description'][:40] if x['items'] else '')
if hard: print('FAIL: DRC',hard)
if par: print('FAIL: schematic parity',len(par))
if un>int(sys.argv[2]): print(f'FAIL: {un} open connections (OPEN_MAX={sys.argv[2]})')
sys.exit(1 if hard or par or un>int(sys.argv[2]) else 0)
PYEOF
"$PY" "$ROOT/tools/open_nets.py" "$W/drc.json" "$W/open_nets.csv" || { echo 'FAIL: open_nets.py'; fail=1; }
"$KP" "$ROOT/tools/route_checks.py" "$W/verify.kicad_pcb" > "$W/checks.txt" 2>&1; rc=$?
q < "$W/checks.txt" | grep -v '^    (' || true
[ "$rc" = 0 ] || { grep '^    (' "$W/checks.txt" | head -40; echo "FAIL: route_checks (exit $rc)"; fail=1; }
run() {   # run <label> <command...>: print the tool's output, fail on a non-zero exit
  local label=$1; shift
  "$@" > "$W/tool.txt" 2>&1; local rc=$?
  q < "$W/tool.txt"
  [ "$rc" = 0 ] || { echo "FAIL: $label (exit $rc)"; fail=1; }
}
run joint_check "$KP" "$ROOT/tools/joint_check.py" "$W/verify.kicad_pcb"
MODE=check run 'port template copper differs from port_copper.py' "$KP" "$ROOT/tools/port_template.py" "$W/verify.kicad_pcb"
MODE=check run 'U8 block copper differs from u8_block.py' "$KP" "$ROOT/tools/u8_block.py" "$W/verify.kicad_pcb"
MODE=check run 'latch block copper differs from latch_block.py' "$KP" "$ROOT/tools/latch_block.py" "$W/verify.kicad_pcb"
MODE=check run 'hand-laid copper differs from hand_laid.specs' "$KP" "$ROOT/tools/lay_path.py" "$W/verify.kicad_pcb" "@$ROOT/tools/hand_laid.specs"
run pour_width "$KP" "$ROOT/tools/pour_width.py" "$W/verify.kicad_pcb"
MODE=check run 'heatsink pad openings differ from heatsink_pads.py' "$KP" "$ROOT/tools/heatsink_pads.py" "$W/verify.kicad_pcb"
# the order package in ../fab was made from this very board file (default board only; a missing package fails)
[ "$B" = "$LAYOUT/marengo_pdu_revb.kicad_pcb" ] && run 'the order package in fab/ does not match the board: run tools/fab_package.sh' "$KP" "$ROOT/tools/fab_check.py" "$B" "$PB/fab"
"$KCLI" sch export netlist --format kicadsexpr -o "$W/net.net" "$ROOT/marengo_pdu_revb.kicad_sch" > "$W/net.log" 2>&1; rc=$?
if [ "$rc" != 0 ] || [ ! -s "$W/net.net" ]; then cat "$W/net.log"; echo "FAIL: netlist export (exit $rc)"; fail=1
else
  "$PY" -I "$ROOT/tools/check.py" "$ROOT/tools" "$W/net.net" "$LAYOUT/marengo_pdu_revb.kicad_pro" > "$W/check.txt" 2>&1; rc=$?
  grep -E '^FAIL|^FAILS|^audited|Error|Traceback' "$W/check.txt"
  { [ "$rc" = 0 ] && grep -q '^FAILS 0' "$W/check.txt"; } || { echo "FAIL: check.py (exit $rc)"; fail=1; }
  "$KCLI" sch export netlist --format kicadsexpr -o "$W/buck.net" "$PB/buck12/marengo_buck12.kicad_sch" > "$W/bucknet.log" 2>&1 || { cat "$W/bucknet.log"; echo 'FAIL: buck netlist export'; fail=1; }
  run bom_check "$PY" -I "$ROOT/tools/bom_check.py" "$ROOT/tools" "$W/net.net" "$PB" "$W/buck.net"
fi
echo "work files: $W"
[ "$fail" = 0 ] && echo 'verify_board: PASS' || { echo 'verify_board: FAIL'; exit 1; }
