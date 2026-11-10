#!/bin/bash
# Rebuild the rev B5 board from the netlist: placement, power stage, spacing, GND fanout, staged signal routing, the
# designed blocks, the hand-laid copper, the finishing router, the generated guards and heatsink pads, the checks.
# Usage: tools/build_board.sh <work dir> [from-stage]   (stages: place power route blocks finish verify; default place;
# STOP=power ends after the base board)
# The work dir needs net.net (kicad-cli sch export netlist). Each stage's output is the next one's input:
#   place  -> placed.kicad_pcb          tools/place.py (takes the blocks' part positions from port_template.py, u8_block.py)
#   power  -> base.kicad_pcb            route_power (with vbus_copper), hv_spacing (with estop_guards), gnd_fanout, route_u1
#   route  -> routed.kicad_pcb          tools/route_stages.sh, a few hours; its route_checks run is a report here
#   blocks -> blocks.kicad_pcb          port_template.py (rip and stamp the six ports), u8_block.py (the same for U8),
#                                       then lay_path.py @hand_laid.specs (exit 1 if a spec is blocked)
#   finish -> finished.kicad_pcb        finish_route.py round by round until a round closes nothing, joint_fix.py,
#                                       estop_guards.py, a kicad-cli refill, heatsink_pads.py
#   verify -> tools/verify_board.sh on finished.kicad_pcb: the build's exit code
# The copper between the blocks comes from the routers, whose result depends on the order of the runs: a rebuild gives
# the same blocks and hand-laid copper but not the same copper in between, and may leave connections open that the
# committed board has closed by rip-up and re-route (tools/rrr.sh, rip_window.py). verify_board.sh says so.
# The blocks, finish and verify stages were added on 2026-11-10 from the steps the routed board was made with; a full
# rebuild through them has not been run yet.
set -uo pipefail
W=$(cd "$1" && (pwd -W 2>/dev/null || pwd)); FROM=${2:-place}   # pwd -W: a Windows path for the Windows Pythons
ROOT=$(cd "$(dirname "$0")/.." && pwd); LAYOUT="$ROOT/../layout"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python  # a python3 that fails (the Windows Store stub) falls back
export MSYS_NO_PATHCONV=1
q() { grep -v 'memory leak\|GetWidth called\|image handler'; }
die() { echo "$*"; exit 1; }
cd "$ROOT"
ORDER='place power route blocks finish verify'
case " $ORDER " in *" $FROM "*) ;; *) die "unknown stage $FROM (stages: $ORDER)";; esac
run() {   # run <stage>: true when the stage is at or after the from-stage
  local seen=0 s
  for s in $ORDER; do [ "$s" = "$FROM" ] && seen=1; [ "$s" = "$1" ] && { [ "$seen" = 1 ]; return; }; done
  return 1
}
refill() {   # refill <in board> <out board>: kicad-cli's fill with the project rules (the .kicad_dru clearances)
  cp "$1" "$W/fill.kicad_pcb" && cp "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/fill.kicad_pro" && cp "$LAYOUT/marengo_pdu_revb.kicad_dru" "$W/fill.kicad_dru" || die 'copying the project files failed'
  rm -f "$W/fill.json"
  "$KC" pcb drc --refill-zones --save-board --severity-all --format json -o "$W/fill.json" "$W/fill.kicad_pcb" > "$W/fill.log" 2>&1 || { cat "$W/fill.log"; die 'kicad-cli refill failed'; }
  [ -s "$W/fill.json" ] || die 'kicad-cli refill wrote no report'
  cp "$W/fill.kicad_pcb" "$2"
}
if run place; then
  "$KP" tools/place.py "$W/net.net" "$W/placed.kicad_pcb" "$W/place.json" 2>&1 | q | grep -E 'overlaps|missing|room|gap in'
  [ -s "$W/placed.kicad_pcb" ] || die 'place stage failed'
fi
if run power; then
  "$KP" tools/route_power.py "$W/placed.kicad_pcb" "$W/base.kicad_pcb" 2>&1 | q | tail -1
  "$KP" tools/hv_spacing.py "$W/base.kicad_pcb" > "$W/hv_spacing.txt" 2>&1 || echo "hv_spacing exit $?"; grep -E '^moved|^left|guard|removed' "$W/hv_spacing.txt" | cut -c1-160
  "$KP" tools/gnd_fanout.py "$W/base.kicad_pcb" 2>&1 | q | cut -c1-160 | tail -1
  "$KP" tools/route_u1.py "$W/base.kicad_pcb" 2>&1 | q | tail -1
  "$KP" tools/route_export.py "$W/base.kicad_pcb" "$W/copper.json" 2>&1 | q | tail -1
  [ -s "$W/copper.json" ] || die 'power stage failed'
  [ "${STOP:-}" = power ] && exit 0   # STOP=power: build the base board only
fi
# The signal routing is staged (tools/route_stages.sh: five locked stages on base.kicad_pcb, route_fixes, patch_route,
# DRC with parity, open nets, route_checks); a single grid_route.py pass over every net doesn't reach the committed board.
# Its route_checks run can't pass before the blocks are laid, so here it only reports (CHECKS_REPORT=1).
if run route; then
  CHECKS_REPORT=1 bash tools/route_stages.sh "$W" || exit $?
fi
if run blocks; then
  [ -s "$W/routed.kicad_pcb" ] || die "no routed.kicad_pcb in $W"
  rm -f "$W/b1.kicad_pcb" "$W/b2.kicad_pcb" "$W/blocks.kicad_pcb"
  "$KP" tools/port_template.py "$W/routed.kicad_pcb" "$W/b1.kicad_pcb" 2>&1 | q | tail -8; [ -s "$W/b1.kicad_pcb" ] || die 'port_template failed'
  "$KP" tools/u8_block.py "$W/b1.kicad_pcb" "$W/b2.kicad_pcb" 2>&1 | q | tail -2; [ -s "$W/b2.kicad_pcb" ] || die 'u8_block failed'
  # the pours refill round the hand-laid copper, so a pour is not an obstacle for it (SOFTZ=1)
  SOFTZ=1 LOCK=1 "$KP" tools/lay_path.py "$W/b2.kicad_pcb" "$W/blocks.kicad_pcb" @tools/hand_laid.specs > "$W/hand_laid.txt" 2>&1; rc=$?
  q < "$W/hand_laid.txt" | cut -c1-200
  [ "$rc" = 0 ] && [ -s "$W/blocks.kicad_pcb" ] || die "hand-laid copper blocked (lay_path exit $rc): fix tools/hand_laid.specs or what blocks it"
fi
if run finish; then
  [ -s "$W/blocks.kicad_pcb" ] || die "no blocks.kicad_pcb in $W"
  cp "$W/blocks.kicad_pcb" "$W/f.kicad_pcb"; last=-1
  for round in 1 2 3 4 5 6 7 8; do
    refill "$W/f.kicad_pcb" "$W/f.kicad_pcb"
    open=$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))['unconnected_items']))" "$W/fill.json")
    echo "finish round $round: $open open"
    [ "$open" = 0 ] && break; [ "$open" = "$last" ] && break; last=$open
    COMPONENTS=1 "$KP" tools/finish_route.py "$W/f.kicad_pcb" "$W/f2.kicad_pcb" "$W/fill.json" > "$W/finish$round.txt" 2>&1 || { tail -5 "$W/finish$round.txt"; die 'finish_route failed'; }
    q < "$W/finish$round.txt" | tail -1 | cut -c1-200; cp "$W/f2.kicad_pcb" "$W/f.kicad_pcb"
  done
  "$KP" tools/joint_fix.py "$W/f.kicad_pcb" "$W/f2.kicad_pcb" 2>&1 | q | tail -1; [ -s "$W/f2.kicad_pcb" ] || die 'joint_fix wrote no board'
  "$KP" tools/estop_guards.py "$W/f2.kicad_pcb" "$W/f.kicad_pcb" 2>&1 | q | tail -1
  refill "$W/f.kicad_pcb" "$W/f.kicad_pcb"
  "$KP" tools/heatsink_pads.py "$W/f.kicad_pcb" "$W/finished.kicad_pcb" 2>&1 | q | tail -1
  [ -s "$W/finished.kicad_pcb" ] || die 'finish stage failed'
fi
if run verify; then
  [ -s "$W/finished.kicad_pcb" ] || die "no finished.kicad_pcb in $W"
  KEEP="$W/verify" bash tools/verify_board.sh "$W/finished.kicad_pcb"
fi
