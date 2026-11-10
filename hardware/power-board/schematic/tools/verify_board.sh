#!/bin/bash
# verify_board.sh [board.kicad_pcb] : the full check set on a routed board (default: ../layout/marengo_pdu_revb.kicad_pcb).
# Copies the board next to a copy of the schematic and the project rules in a temp dir, so KiCad's schematic-parity check
# can read the netlist (run in layout/ it only prints "Failed to fetch schematic netlist" and checks nothing), refills
# the zones with the project rules there, and runs: DRC with parity, tools/open_nets.py, tools/route_checks.py, tools/check.py.
# Exit 1 if parity was skipped, on any parity item, clearance/short/courtyard violation, or a failed route_checks or
# check.py. Open connections are reported, not failed: OPEN_MAX=<n> makes more than n an error.
# The board file itself is not changed. KEEP=<dir> keeps the work files there.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }   # a Windows path for the Windows Pythons
ROOT=$(wp "$(dirname "$0")/.."); LAYOUT=$(wp "$ROOT/../layout")
B=${1:-$LAYOUT/marengo_pdu_revb.kicad_pcb}; B=$(wp "$(dirname "$B")")/$(basename "$B")
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
W=${KEEP:-$(mktemp -d)}; mkdir -p "$W"; W=$(cd "$W" && (pwd -W 2>/dev/null || pwd))
cp "$B" "$W/verify.kicad_pcb" && cp "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/verify.kicad_pro" && cp "$LAYOUT/marengo_pdu_revb.kicad_dru" "$W/verify.kicad_dru" \
  && cp "$ROOT/marengo_pdu_revb.kicad_sch" "$W/verify.kicad_sch" && cp "$ROOT/marengo_pdu_revb.kicad_sch" "$W/marengo_pdu_revb.kicad_sch" \
  && cp "$ROOT/marengo_revb.kicad_sym" "$ROOT/sym-lib-table" "$ROOT/fp-lib-table" "$W/" && cp -r "$ROOT/marengo_revb.pretty" "$W/" || { echo 'copying the project files failed'; exit 1; }
"$KC" pcb drc --refill-zones --save-board --format json --schematic-parity -o "$W/drc.json" "$W/verify.kicad_pcb" > "$W/drc.log" 2>&1
[ -s "$W/drc.json" ] || { cat "$W/drc.log"; echo 'DRC wrote no report'; exit 1; }
if grep -qi 'failed to fetch schematic' "$W/drc.log"; then cat "$W/drc.log"; echo 'FAIL: the schematic parity check did not run'; exit 1; fi
fail=0
"$PY" - "$W/drc.json" "${OPEN_MAX:-}" <<'PYEOF' || fail=1
import json,collections,sys
d=json.load(open(sys.argv[1])); v=collections.Counter(x['type'] for x in d['violations'] if not x['type'].startswith('silk'))
par=d.get('schematic_parity',[]); un=len(d['unconnected_items'])
print('DRC',dict(v),'unconnected',un,'parity',len(par))
for x in par[:20]: print('   parity:',x['type'],x['description'][:110],x['items'][0]['description'][:40] if x['items'] else '')
hard=[k for k in v if k in ('clearance','shorting_items','courtyards_overlap','hole_clearance','hole_to_hole','tracks_crossing','copper_edge_clearance','zones_intersect')]
bad=bool(hard) or bool(par) or (sys.argv[2]!='' and un>int(sys.argv[2]))
if hard: print('FAIL: DRC',{k:v[k] for k in hard})
if par: print('FAIL: schematic parity',len(par))
sys.exit(1 if bad else 0)
PYEOF
"$PY" "$ROOT/tools/open_nets.py" "$W/drc.json" "$W/open_nets.csv" || fail=1
"$KP" "$ROOT/tools/route_checks.py" "$W/verify.kicad_pcb" > "$W/checks.txt" 2>&1; rc=$?
grep -v 'memory leak\|GetWidth called\|image handler' "$W/checks.txt" | grep -v '^    (' || true
[ "$rc" = 0 ] || { echo "FAIL: route_checks (exit $rc)"; fail=1; }
"$KC" sch export netlist --format kicadsexpr -o "$W/net.net" "$ROOT/marengo_pdu_revb.kicad_sch" >/dev/null 2>&1
"$PY" -I "$ROOT/tools/check.py" "$ROOT/tools" "$W/net.net" | grep -E '^FAIL|^FAILS|^audited'
"$PY" -I "$ROOT/tools/check.py" "$ROOT/tools" "$W/net.net" | grep -q '^FAILS 0' || { echo 'FAIL: check.py'; fail=1; }
echo "work files: $W"
[ "$fail" = 0 ] && echo 'verify_board: PASS' || { echo 'verify_board: FAIL'; exit 1; }
