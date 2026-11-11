#!/bin/bash
# gate_trial.sh <in.kicad_pcb> <out.kicad_pcb> <workdir> <tap net regex> <gate nets regex>
# One port's ordered rip-up: rip_nets.py removes the gate-drive nets of that port completely (locked or not), the tap is
# routed first (finish_route.py), then the gate nets (or the groups in ORDER, each with finish_shove.py after), then every
# other open connection,
# and lock_nets.py locks the new gate routes again and prints old vs new length and layers. Each step runs on a
# kicad-cli refilled board. The caller keeps the result only if the open count drops and every check passes.
set -u; export MSYS_NO_PATHCONV=1
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
T=$(cd "$(dirname "$0")" && pwd -W); R=$(cd "$T/../.." && pwd -W)/layout
IN=$1; OUT=$2; W=$3; TAP=$4; GATE=$5; mkdir -p $W
drc(){ cp "$1" $R/_trial.kicad_pcb; cp $R/marengo_pdu_revb.kicad_pro $R/_trial.kicad_pro; cp $R/marengo_pdu_revb.kicad_dru $R/_trial.kicad_dru
  "$KC" pcb drc --refill-zones --save-board --format json -o "$2" $R/_trial.kicad_pcb >/dev/null 2>&1; cp $R/_trial.kicad_pcb "$1"
  python -c "import json;print(len(json.load(open('$2'))['unconnected_items']))"; }
echo "before $(drc $IN $W/d0.json)"
"$KP" $T/rip_nets.py $IN $W/a.kicad_pcb "$GATE" $W/old.json 2>&1 | grep ripped | cut -c1-300
echo "ripped $(drc $W/a.kicad_pcb $W/d1.json)"
# ORDER: "tap" (default) routes the tap, then the ripped nets; a regex list "R1;R2;..." routes those groups in turn,
# with finish_shove.py for whatever a group leaves open (for example "^/GPU_L2\$;^/V_L2\$;^/(GPD_L2|BST_L2)\$")
ORDER=${ORDER:-"$TAP;$GATE"}; cur=$W/a.kicad_pcb; d=$W/d1.json; i=0
IFS=';' read -ra GRP <<< "$ORDER"
for gg in "${GRP[@]}"; do i=$((i+1)); g=${gg%%@*}; fc=1; [ "$gg" != "$g" ] && fc=${gg#*@}   # "regex@k": FCOST=k for that group
  FCOST=$fc WINDOW=12 SECONDS=60 "$KP" -u $T/finish_route.py $cur $W/s$i.kicad_pcb $d "$g" 2>&1 | grep -E "^(CLOSED|LEFT)"
  echo "step $i $(drc $W/s$i.kicad_pcb $W/s$i.json)"
  ATTEMPTS=2 "$KP" -u $T/finish_shove.py $W/s$i.kicad_pcb $W/s${i}b.kicad_pcb $W/s$i.json "$g" 2>&1 | grep -E "^(CLOSED)" | sed 's/^/shove /'
  echo "step ${i}b $(drc $W/s${i}b.kicad_pcb $W/s${i}b.json)"
  cur=$W/s${i}b.kicad_pcb; d=$W/s${i}b.json
done
cp $cur $W/c.kicad_pcb; cp $d $W/d3.json
SECONDS=25 "$KP" -u $T/finish_route.py $W/c.kicad_pcb $W/e.kicad_pcb $W/d3.json 2>&1 | grep -cE "^CLOSED" | sed 's/^/rest closed /'
echo "rest $(drc $W/e.kicad_pcb $W/d4.json)"
"$KP" $T/lock_nets.py $W/e.kicad_pcb $OUT "$GATE" $W/old.json 2>&1 | grep -vE "image handler|swig"
echo "after $(drc $OUT $W/d5.json)"
rm -f $R/_trial.* $R/~_trial*
