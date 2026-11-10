#!/bin/bash
# verify_buck.sh [board.kicad_pcb] : the buck board's check set (default: ../layout/marengo_buck12.kicad_pcb). Copies the
# board next to the schematic and the project in a temp dir, refills the zones with the project rules there, and runs:
#   kicad-cli DRC with parity     every violation type fails, except the cosmetic silkscreen ones in ALLOW; any parity issue
#                                 and any open connection fail; a report that is missing, dated before the run or has no parity key fails
#   tools/spacing_buck.py         SP_EN (E-stop class on the main board) 1.7 mm (the 1.5 mm rule plus etch tolerance) from the
#                                 54 V copper (tools/hv_buck.py); no other E-stop net here; fails when it compared nothing
#   tools/kelvin_buck.py          both Kelvin pairs traced sense pad to meter pin, on one inner layer, paired over their floor
#   tools/holes_buck.py           a copper keep-out on every layer round each M3 hole, and no copper inside it
#   ../../schematic/tools/joint_check.py   every joint has 0.1 mm of real copper overlap
#   tools/copper_buck.py MODE=check        the designed copper equals the script
#   tools/pour_buck.py            the 12 A, 5 A and input paths under their temperature-rise limits
#   tools/fab_check_buck.sh       the order package in ../fab against this board file (default board only; missing fails)
#   ../../schematic/tools/bom_check.py      the BOM files and the kit against both netlists
# Exit 1 on any failure. KEEP=<dir> keeps the work files. KC=<program> replaces kicad-cli for the DRC run (self-test).
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
B=$(wp "$(dirname "$0")/.."); PB=$(wp "$B/.."); T="$PB/schematic/tools"
BRD=${1:-$B/layout/marengo_buck12.kicad_pcb}; BRD=$(wp "$(dirname "$BRD")")/$(basename "$BRD")
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KCLI="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KCLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
KC=${KC:-$KCLI}
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
q() { grep -v 'memory leak\|GetWidth called\|image handler'; }
W=${KEEP:-$(mktemp -d)}; mkdir -p "$W"; W=$(wp "$W")
rm -f "$W/drc.json"; START=$("$PY" -c "import time;print(int(time.time()))")
cp "$BRD" "$W/marengo_buck12.kicad_pcb" && cp "$B/layout/marengo_buck12.kicad_pro" "$B/marengo_buck12.kicad_sch" "$B/marengo_buck12.kicad_sym" "$B/sym-lib-table" "$B/fp-lib-table" "$W/" \
  && cp -r "$B/marengo_buck12.pretty" "$W/" || { echo 'copying the project failed'; exit 1; }
fail=0
"$KC" pcb drc --refill-zones --save-board --severity-all --format json --schematic-parity -o "$W/drc.json" "$W/marengo_buck12.kicad_pcb" > "$W/drc.log" 2>&1; rc=$?
[ "$rc" = 0 ] || { cat "$W/drc.log"; echo "FAIL: kicad-cli pcb drc exited $rc"; fail=1; }
[ -s "$W/drc.json" ] || { cat "$W/drc.log"; echo 'FAIL: DRC wrote no report'; exit 1; }
if grep -qi 'failed to fetch schematic' "$W/drc.log"; then cat "$W/drc.log"; echo 'FAIL: the schematic parity check did not run'; exit 1; fi
"$PY" - "$W/drc.json" "$START" <<'PYEOF' || fail=1
import json,collections,sys,datetime
ALLOW={'silk_overlap':'cosmetic','silk_over_copper':'cosmetic: the fab clips silkscreen at pads','silk_edge_clearance':'cosmetic'}
d=json.load(open(sys.argv[1]))
if 'schematic_parity' not in d: print('FAIL: the DRC report has no schematic_parity key'); sys.exit(1)
# the report must be this run's: its own date (local time, to the second) is not before the run started
try: made=datetime.datetime.fromisoformat(d['date']).timestamp()
except Exception: print('FAIL: the DRC report has no readable date'); sys.exit(1)
if made<int(sys.argv[2])-2: print(f"FAIL: the DRC report is older than this run (dated {d['date']})"); sys.exit(1)
v=collections.Counter(x['type'] for x in d['violations']); hard={k:n for k,n in v.items() if k not in ALLOW}
par=d['schematic_parity']; un=len(d['unconnected_items'])
print('DRC violations',hard,'allowed',{k:n for k,n in v.items() if k in ALLOW},'unconnected',un,'parity',len(par))
for x in d['violations']:
    if x['type'] in hard: print('   ',x['type'],x['description'][:100],[(i['description'][:50],i['pos']['x'],i['pos']['y']) for i in x['items']][:2])
for x in par[:20]: print('   parity:',x['type'],x['description'][:110])
if hard: print('FAIL: DRC',hard)
if par: print('FAIL: schematic parity',len(par))
if un: print(f'FAIL: {un} open connections')
sys.exit(1 if hard or par or un else 0)
PYEOF
run() { local label=$1; shift; "$@" > "$W/tool.txt" 2>&1; local rc=$?; q < "$W/tool.txt"; [ "$rc" = 0 ] || { echo "FAIL: $label (exit $rc)"; fail=1; }; }
run spacing_buck "$KP" "$B/tools/spacing_buck.py" "$W/marengo_buck12.kicad_pcb"
run kelvin_buck "$KP" "$B/tools/kelvin_buck.py" "$W/marengo_buck12.kicad_pcb"
run holes_buck "$KP" "$B/tools/holes_buck.py" "$W/marengo_buck12.kicad_pcb"
run joint_check "$KP" "$T/joint_check.py" "$W/marengo_buck12.kicad_pcb"
MODE=check run 'designed copper differs from copper_buck.py' "$KP" "$B/tools/copper_buck.py" "$W/marengo_buck12.kicad_pcb"
run pour_buck "$KP" "$B/tools/pour_buck.py" "$W/marengo_buck12.kicad_pcb"
[ "$BRD" = "$B/layout/marengo_buck12.kicad_pcb" ] && run 'the buck order package in fab/ does not match the board: run tools/fab_package_buck.sh' bash "$B/tools/fab_check_buck.sh"
"$KCLI" sch export netlist --format kicadsexpr -o "$W/buck.net" "$B/marengo_buck12.kicad_sch" > /dev/null 2>&1 && "$KCLI" sch export netlist --format kicadsexpr -o "$W/main.net" "$PB/schematic/marengo_pdu_revb.kicad_sch" > /dev/null 2>&1 \
  && run bom_check "$PY" -I "$T/bom_check.py" "$T" "$W/main.net" "$PB" "$W/buck.net" || { echo 'FAIL: netlist export'; fail=1; }
echo "work files: $W"
[ "$fail" = 0 ] && echo 'verify_buck: PASS' || { echo 'verify_buck: FAIL'; exit 1; }
