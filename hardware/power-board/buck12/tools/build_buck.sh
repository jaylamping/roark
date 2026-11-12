#!/bin/bash
# build_buck.sh <work dir> : build the buck board from its netlist, as the committed board was made.
#   1. tools/place_buck.py     every part at its listed position, holes, bare test pads (on an emptied copy of the main
#                              board, for the stackup and design settings)
#   2. tools/copper_buck.py    the designed copper: pours, planes, vias, the hand-laid gate drive, meters and current paths
#   3. a kicad-cli refill with the project rules, then ../../schematic/tools/finish_route.py on the hard nets first (the
#      ones a later round can box in), then round by round on everything until a round closes nothing
#   4. ../../schematic/tools/finish_ground_islands.py: a GND via in every F.Cu GND fill island
#   5. a final refill and DRC with schematic parity: <work dir>/final/buck12.kicad_pcb, and buck12/tools/verify_buck.sh
#      on it
# The routers' copper between the designed items can differ between runs, as on the main board; the designed copper does not.
# Every step deletes its output first and stops on a non-zero exit.
set -uo pipefail
W=$(mkdir -p "$1" && cd "$1" && (pwd -W 2>/dev/null || pwd))
B=$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd)); T=$(cd "$B/../schematic/tools" && (pwd -W 2>/dev/null || pwd))
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1 FINE=U1
# the routers treat the buck's 54 V copper (tools/hv_buck.py, the one list) as the 54 V list (domains.py's what-if switch),
# so SP_EN, an E-stop-class net, keeps hv_buck.SP_MIN (1.7 mm: the main board's 1.5 mm rule plus etch tolerance) to it
# (tools/spacing_buck.py checks the result)
PB_HV_EXTRA=$("$PY" "$B/tools/hv_buck.py") && [ -n "$PB_HV_EXTRA" ] || { echo 'hv_buck.py gave no net list'; exit 1; }
PB_ESTOP_GAP=$("$PY" -c "import sys;sys.path.insert(0,sys.argv[1]);import hv_buck;print(hv_buck.SP_MIN)" "$B/tools") || { echo 'hv_buck.py gave no SP_MIN'; exit 1; }
export PB_HV_EXTRA PB_ESTOP_GAP
q() { grep -v 'memory leak\|GetWidth called\|image handler\|Exception ignored\|OSError'; }
die() { echo "$*"; exit 1; }
step() {   # step <label> <output or -> <command...>
  local label=$1 out=$2; shift 2
  [ "$out" = - ] || rm -f "$out"
  "$@" > "$W/step.log" 2>&1; local rc=$?
  q < "$W/step.log" | tail -2 | cut -c1-200
  [ "$rc" = 0 ] || die "$label failed (exit $rc)"
  [ "$out" = - ] || [ -s "$out" ] || die "$label wrote no output"
}
drc() {   # drc <board> <dir>: refill and DRC with parity in a project copy; <dir>/buck12.kicad_pcb is the refilled board
  rm -rf "$2"; mkdir -p "$2"
  cp "$1" "$2/buck12.kicad_pcb" && cp "$B/layout/buck12.kicad_pro" "$B/buck12.kicad_sch" "$B/buck12.kicad_sym" "$B/sym-lib-table" "$B/fp-lib-table" "$2/" && cp -r "$B/buck12.pretty" "$2/" || die 'copying the project failed'
  "$KC" pcb drc --refill-zones --save-board --severity-all --format json --schematic-parity -o "$2/drc.json" "$2/buck12.kicad_pcb" > "$2/drc.log" 2>&1 || die "kicad-cli drc failed: $(cat "$2/drc.log")"
  [ -s "$2/drc.json" ] || die 'no DRC report'
}
opens() { "$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))['unconnected_items']))" "$1/drc.json"; }
"$KC" sch export netlist --format kicadsexpr -o "$W/net.net" "$B/buck12.kicad_sch" > /dev/null 2>&1 || die 'netlist export failed'
step place "$W/placed.kicad_pcb" "$KP" "$B/tools/place_buck.py" "$W/net.net" "$B/../layout/power_board_revb.kicad_pcb" "$W/placed.kicad_pcb"
step copper "$W/copper.kicad_pcb" "$KP" "$B/tools/copper_buck.py" "$W/placed.kicad_pcb" "$W/copper.kicad_pcb"
drc "$W/copper.kicad_pcb" "$W/d0"; echo "designed copper: $(opens "$W/d0") connections open"
HARD='/(SS|SP_EN|COMP|I2C_SDA)$'
(cd "$T" && step 'hard nets' "$W/r0.kicad_pcb" env SECONDS=120 WINDOW=14 "$KP" finish_route.py "$W/d0/buck12.kicad_pcb" "$W/r0.kicad_pcb" "$W/d0/drc.json" "$HARD") || exit 1
cur="$W/r0.kicad_pcb"; last=-1
for r in 1 2 3 4 5 6; do
  drc "$cur" "$W/d$r"; open=$(opens "$W/d$r"); echo "round $r: $open open"
  [ "$open" = 0 ] && break; [ "$open" = "$last" ] && break; last=$open
  (cd "$T" && step "route round $r" "$W/r$r.kicad_pcb" env SECONDS=40 COMPONENTS=1 "$KP" finish_route.py "$W/d$r/buck12.kicad_pcb" "$W/r$r.kicad_pcb" "$W/d$r/drc.json") || exit 1
  cur="$W/r$r.kicad_pcb"
done
# the islands step starts from the last round's board, refilled (when the loop ran out of rounds, $cur is newer than d$r)
drc "$cur" "$W/dlast"; echo "after routing: $(opens "$W/dlast") open"
(cd "$T" && step islands "$W/islands.kicad_pcb" "$KP" finish_ground_islands.py "$W/dlast/buck12.kicad_pcb" "$W/islands.kicad_pcb") || exit 1
drc "$W/islands.kicad_pcb" "$W/final"; echo "final: $(opens "$W/final") connections open"
bash "$B/tools/verify_buck.sh" "$W/final/buck12.kicad_pcb"
