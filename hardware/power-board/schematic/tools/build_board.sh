#!/bin/bash
# Rebuild the rev B5 board from the netlist: placement, power stage, spacing, GND fanout, staged signal routing, the
# designed blocks, the hand-laid copper, the finishing router, the generated guards and heatsink pads, the checks.
# Usage: tools/build_board.sh <work dir> [from-stage]   (stages: place power route blocks finish verify; default place;
# STOP=power ends after the base board)
# The work dir needs net.net (kicad-cli sch export netlist). Each stage's output is the next one's input:
#   place  -> placed.kicad_pcb          tools/place.py (takes the blocks' part positions from port_template.py, u8_block.py)
#   power  -> base.kicad_pcb            route_power (with vbus_copper), hv_spacing (with estop_guards), gnd_fanout, route_u1
#   route  -> routed.kicad_pcb          tools/route_stages.sh, a few hours; its route_checks run is a report here
#   blocks -> blocks.kicad_pcb          port_template.py (rip and stamp the six ports), u8_block.py and latch_block.py (the
#                                       same for U8 and the latch supply),
#                                       then lay_path.py @hand_laid.specs (exit 1 if a spec is blocked)
#   finish -> finished.kicad_pcb        finish_route.py round by round until a round closes nothing, joint_fix.py,
#                                       bat_copper.py, estop_guards.py, a kicad-cli refill, heatsink_pads.py
#   verify -> tools/verify_board.sh on finished.kicad_pcb: the build's exit code
# The copper between the blocks comes from the routers, whose result depends on the order of the runs: a rebuild gives
# the same blocks and hand-laid copper but not the same copper in between, and may leave connections open that the
# committed board has closed by rip-up and re-route (tools/rrr.sh, rip_window.py). verify_board.sh says so.
# A full rebuild (2026-11-10, about 70 minutes) reproduces the placement, pours, blocks, hand-laid copper and generated
# items, and ends with 68 connections open on 27 nets and verify_board.sh failing: LAYOUT_RULES.md, "Exceptions and
# hand-laid copper".
# Every stage deletes its outputs before it runs, so a file left by an earlier build can't stand in for one that failed,
# and every tool's exit code is checked (pipefail, and step() below runs the tool before filtering its output).
set -uo pipefail
W=$(cd "$1" && (pwd -W 2>/dev/null || pwd)); FROM=${2:-place}   # pwd -W: a Windows path for the Windows Pythons
ROOT=$(cd "$(dirname "$0")/.." && pwd); LAYOUT="$ROOT/../layout"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python  # a python3 that fails (the Windows Store stub) falls back
export MSYS_NO_PATHCONV=1
q() { grep -v 'memory leak\|GetWidth called\|image handler'; }
die() { echo "$*"; exit 1; }
step() {   # step <label> <output board or -> <lines> <command...>: run, show the last <lines> lines, fail on a non-zero exit
           # or (with an output board) when the board was not written; the output is deleted first
  local label=$1 out=$2 n=$3; shift 3
  [ "$out" = - ] || rm -f "$out"
  "$@" > "$W/step.log" 2>&1; local rc=$?
  q < "$W/step.log" | tail -n "$n" | cut -c1-200
  [ "$rc" = 0 ] || die "$label failed (exit $rc)"
  [ "$out" = - ] || [ -s "$out" ] || die "$label wrote no board"
}
cd "$ROOT"
ORDER='place power route blocks finish verify'
case " $ORDER " in *" $FROM "*) ;; *) die "unknown stage $FROM (stages: $ORDER)";; esac
run() {   # run <stage>: true when the stage is at or after the from-stage
  local seen=0 s
  for s in $ORDER; do [ "$s" = "$FROM" ] && seen=1; [ "$s" = "$1" ] && { [ "$seen" = 1 ]; return; }; done
  return 1
}
refill() {   # refill <in board> <out board>: kicad-cli's fill with the project rules (the .kicad_dru clearances)
  cp "$1" "$W/fill.kicad_pcb" && cp "$LAYOUT/power_board_revb.kicad_pro" "$W/fill.kicad_pro" && cp "$LAYOUT/power_board_revb.kicad_dru" "$W/fill.kicad_dru" || die 'copying the project files failed'
  rm -f "$W/fill.json"
  "$KC" pcb drc --refill-zones --save-board --severity-all --format json -o "$W/fill.json" "$W/fill.kicad_pcb" > "$W/fill.log" 2>&1 || { cat "$W/fill.log"; die 'kicad-cli refill failed'; }
  [ -s "$W/fill.json" ] || die 'kicad-cli refill wrote no report'
  cp "$W/fill.kicad_pcb" "$2"
}
if run place; then
  rm -f "$W/place.json"
  step place "$W/placed.kicad_pcb" 0 "$KP" tools/place.py "$W/net.net" "$W/placed.kicad_pcb" "$W/place.json"
  q < "$W/step.log" | grep -E 'overlaps|missing|room|gap in'
fi
if run power; then
  rm -f "$W/copper.json" "$W/hv_spacing.txt"
  step route_power "$W/base.kicad_pcb" 1 "$KP" tools/route_power.py "$W/placed.kicad_pcb" "$W/base.kicad_pcb"
  step hv_spacing - 0 "$KP" tools/hv_spacing.py "$W/base.kicad_pcb"   # works on base.kicad_pcb in place
  cp "$W/step.log" "$W/hv_spacing.txt"; grep -E '^moved|^left|guard|removed' "$W/hv_spacing.txt" | cut -c1-160
  step gnd_fanout - 1 "$KP" tools/gnd_fanout.py "$W/base.kicad_pcb"
  step route_u1 - 1 "$KP" tools/route_u1.py "$W/base.kicad_pcb"
  step route_export - 1 "$KP" tools/route_export.py "$W/base.kicad_pcb" "$W/copper.json"
  [ -s "$W/copper.json" ] || die 'power stage wrote no copper.json'
  [ "${STOP:-}" = power ] && exit 0   # STOP=power: build the base board only
fi
# The signal routing is staged (tools/route_stages.sh: five locked stages on base.kicad_pcb, route_fixes, patch_route,
# DRC with parity, open nets, route_checks); a single grid_route.py pass over every net doesn't reach the committed board.
# Its route_checks run can't pass before the blocks are laid, so here it only reports (CHECKS_REPORT=1).
if run route; then
  rm -f "$W/routed.kicad_pcb"
  CHECKS_REPORT=1 bash tools/route_stages.sh "$W" || exit $?
  [ -s "$W/routed.kicad_pcb" ] || die 'route stage wrote no routed.kicad_pcb'
fi
if run blocks; then
  [ -s "$W/routed.kicad_pcb" ] || die "no routed.kicad_pcb in $W"
  rm -f "$W/b1.kicad_pcb" "$W/b1b.kicad_pcb" "$W/b2.kicad_pcb" "$W/blocks.kicad_pcb" "$W/hand_laid.txt"
  step port_template "$W/b1.kicad_pcb" 8 "$KP" tools/port_template.py "$W/routed.kicad_pcb" "$W/b1.kicad_pcb"
  step u8_block "$W/b1b.kicad_pcb" 2 "$KP" tools/u8_block.py "$W/b1.kicad_pcb" "$W/b1b.kicad_pcb"
  step latch_block "$W/b2.kicad_pcb" 2 "$KP" tools/latch_block.py "$W/b1b.kicad_pcb" "$W/b2.kicad_pcb"
  # the pours refill round the hand-laid copper, so a pour is not an obstacle for it (SOFTZ=1); router copper in its
  # way is ripped for finish_route.py to lay again (RIP=1): the routers' result differs from run to run
  SOFTZ=1 LOCK=1 RIP=1 "$KP" tools/lay_path.py "$W/b2.kicad_pcb" "$W/blocks.kicad_pcb" @tools/hand_laid.specs > "$W/hand_laid.txt" 2>&1; rc=$?
  q < "$W/hand_laid.txt" | cut -c1-200
  [ "$rc" = 0 ] && [ -s "$W/blocks.kicad_pcb" ] || die "hand-laid copper blocked (lay_path exit $rc): fix tools/hand_laid.specs or what blocks it"
fi
if run finish; then
  [ -s "$W/blocks.kicad_pcb" ] || die "no blocks.kicad_pcb in $W"
  rm -f "$W/f.kicad_pcb" "$W/f2.kicad_pcb" "$W/f3.kicad_pcb" "$W/finished.kicad_pcb" "$W"/finish[0-9]*.txt
  cp "$W/blocks.kicad_pcb" "$W/f.kicad_pcb"; last=-1
  for round in 1 2 3 4 5 6 7 8; do
    refill "$W/f.kicad_pcb" "$W/f.kicad_pcb"
    open=$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))['unconnected_items']))" "$W/fill.json")
    echo "finish round $round: $open open"
    [ "$open" = 0 ] && break; [ "$open" = "$last" ] && break; last=$open
    rm -f "$W/f2.kicad_pcb"
    COMPONENTS=1 "$KP" tools/finish_route.py "$W/f.kicad_pcb" "$W/f2.kicad_pcb" "$W/fill.json" > "$W/finish$round.txt" 2>&1 || { tail -5 "$W/finish$round.txt"; die 'finish_route failed'; }
    [ -s "$W/f2.kicad_pcb" ] || die 'finish_route wrote no board'
    q < "$W/finish$round.txt" | tail -1 | cut -c1-200; cp "$W/f2.kicad_pcb" "$W/f.kicad_pcb"
  done
  # joint_fix.py exits 1 when joints are left that it could not fix: the build goes on, and verify_board.sh's
  # joint_check fails the board on them (JOINTS_STRICT=1 stops here instead)
  rm -f "$W/f2.kicad_pcb"
  "$KP" tools/joint_fix.py "$W/f.kicad_pcb" "$W/f2.kicad_pcb" > "$W/step.log" 2>&1; rc=$?
  q < "$W/step.log" | tail -1; [ -s "$W/f2.kicad_pcb" ] || die "joint_fix wrote no board (exit $rc)"
  [ "$rc" = 0 ] || { [ "${JOINTS_STRICT:-0}" = 1 ] && die "joint_fix left joints (exit $rc)"; echo "joint_fix left joints (exit $rc): verify_board.sh's joint_check will say which"; }
  step bat_copper "$W/f3.kicad_pcb" 1 "$KP" tools/bat_copper.py "$W/f2.kicad_pcb" "$W/f3.kicad_pcb"
  step estop_guards "$W/f4.kicad_pcb" 1 "$KP" tools/estop_guards.py "$W/f3.kicad_pcb" "$W/f4.kicad_pcb"
  rm -f "$W/f.kicad_pcb"; refill "$W/f4.kicad_pcb" "$W/f.kicad_pcb"; [ -s "$W/f.kicad_pcb" ] || die 'refill wrote no board'
  step heatsink_pads "$W/finished.kicad_pcb" 1 "$KP" tools/heatsink_pads.py "$W/f.kicad_pcb" "$W/finished.kicad_pcb"
fi
if run verify; then
  [ -s "$W/finished.kicad_pcb" ] || die "no finished.kicad_pcb in $W"
  rm -rf "$W/verify"
  KEEP="$W/verify" bash tools/verify_board.sh "$W/finished.kicad_pcb"
fi
