#!/bin/bash
# rrr.sh <in.kicad_pcb> <out.kicad_pcb> <workdir> <target net regex> X0 Y0 X1 Y1 [LAYERS]
#    or rrr.sh <in> <out> <workdir> <target net regex> probe NET PX PY   (rip what escape_probe.py names for that pad)
# One rip-up-and-re-route trial: rip_window.py, then finish_route.py on the target net first and every open connection
# after (finish_shove.py for what is left), each time on a fresh kicad-cli DRC with full-rule zone refill. Prints the
# open count before and after; the caller keeps the result only if it is lower and every check passes.
set -u; export MSYS_NO_PATHCONV=1
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
T=$(cd "$(dirname "$0")" && pwd -W); IN=$1; OUT=$2; W=$3; NET=$4; shift 4
R=$(cd "$T/../.." && pwd -W)/layout; mkdir -p $W
drc(){ cp "$1" $R/_trial.kicad_pcb; cp $R/marengo_pdu_revb.kicad_pro $R/_trial.kicad_pro; cp $R/marengo_pdu_revb.kicad_dru $R/_trial.kicad_dru
  "$KC" pcb drc --refill-zones --save-board --format json -o "$2" $R/_trial.kicad_pcb >/dev/null 2>&1; cp $R/_trial.kicad_pcb "$1"
  python -c "import json;print(len(json.load(open('$2'))['unconnected_items']))"; }
echo "before $(drc $IN $W/d0.json)"
if [ "$1" = probe ]; then
  RIP=$("$KP" $T/escape_probe.py $IN "$2" "$3" "$4" 2>&1 | grep "^RIP=" | cut -d= -f2)
  [ -z "$RIP" ] && { echo "no rippable escape"; exit 1; }
  "$KP" $T/rip_uuids.py $IN $W/a.kicad_pcb "$RIP" 2>&1 | grep ripped
else "$KP" $T/rip_window.py $IN $W/a.kicad_pcb "$@" 2>&1 | grep ripped; fi
echo "ripped $(drc $W/a.kicad_pcb $W/d1.json)"
MARGIN=.03 WINDOW=12 SECONDS=40 "$KP" -u $T/finish_route.py $W/a.kicad_pcb $W/b.kicad_pcb $W/d1.json "$NET" 2>&1 | grep -E "^(CLOSED|LEFT)"
echo "target $(drc $W/b.kicad_pcb $W/d2.json)"
MARGIN=.03 SECONDS=25 "$KP" -u $T/finish_route.py $W/b.kicad_pcb $W/c.kicad_pcb $W/d2.json 2>&1 | grep -cE "^CLOSED" | sed 's/^/re-routed /'
echo "rest $(drc $W/c.kicad_pcb $W/d3.json)"
MARGIN=.03 ATTEMPTS=2 "$KP" -u $T/finish_shove.py $W/c.kicad_pcb $OUT $W/d3.json 2>&1 | grep -cE "^CLOSED" | sed 's/^/shoved /'
echo "after $(drc $OUT $W/d4.json)"
rm -f $R/_trial.*
