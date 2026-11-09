#!/bin/bash
# Rebuild the rev B5 board from the netlist: placement, power stage, spacing, GND fanout, signal routing, import, checks.
# Usage: tools/build_board.sh <work dir> [from-stage]   (stages: place power route import; default place; STOP=power ends
# after the base board)
# The work dir needs net.net (kicad-cli sch export netlist). Each stage's output is the next one's input:
#   place  -> placed.kicad_pcb          (tools/place.py)
#   power  -> base.kicad_pcb            (route_power, hv_spacing, gnd_fanout, route_u1) + copper.json
#   route  -> routed.kicad_pcb + drc.json + open_nets.csv + checks.txt (tools/route_stages.sh, a few hours)
#   import -> the same checks on an existing routed.kicad_pcb (route_stages.sh with CHECKS_ONLY=1)
set -uo pipefail
W=$(cd "$1" && (pwd -W 2>/dev/null || pwd)); FROM=${2:-place}   # pwd -W: a Windows path for the Windows Pythons
ROOT=$(cd "$(dirname "$0")/.." && pwd); LAYOUT="$ROOT/../layout"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python  # a python3 that fails (the Windows Store stub) falls back
export MSYS_NO_PATHCONV=1
q() { grep -v 'memory leak'; }
cd "$ROOT"
run() { case "$FROM" in place) return 0;; power) [ "$1" != place ];; route) [ "$1" = route ] || [ "$1" = import ];; import) [ "$1" = import ];; esac; }
if run place; then
  "$KP" tools/place.py "$W/net.net" "$W/placed.kicad_pcb" "$W/place.json" 2>&1 | q | grep -E 'overlaps|missing|room|gap in'
fi
if run power; then
  "$KP" tools/route_power.py "$W/placed.kicad_pcb" "$W/base.kicad_pcb" 2>&1 | q | tail -1
  "$KP" tools/hv_spacing.py "$W/base.kicad_pcb" > "$W/hv_spacing.txt" 2>&1 || echo "hv_spacing exit $?"; grep -E '^moved|^left|guard|removed' "$W/hv_spacing.txt" | cut -c1-160
  "$KP" tools/gnd_fanout.py "$W/base.kicad_pcb" 2>&1 | q | cut -c1-160 | tail -1
  "$KP" tools/route_u1.py "$W/base.kicad_pcb" 2>&1 | q | tail -1
  "$KP" tools/route_export.py "$W/base.kicad_pcb" "$W/copper.json" 2>&1 | q | tail -1
  [ -s "$W/copper.json" ] || { echo 'power stage failed'; exit 1; }
  [ "${STOP:-}" = power ] && exit 0   # STOP=power: build the base board only
fi
# The signal routing is staged (tools/route_stages.sh: five locked stages on base.kicad_pcb, route_fixes, patch_route,
# DRC with parity, open nets, route_checks); a single grid_route.py pass over every net doesn't reach the committed board.
if run route || run import; then
  [ "$FROM" = import ] && export CHECKS_ONLY=1   # import: only check the work dir's routed.kicad_pcb
  bash tools/route_stages.sh "$W" || exit $?
fi
