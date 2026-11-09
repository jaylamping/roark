#!/bin/bash
# Signal routing in locked stages on top of the base board (tools/build_board.sh STOP=power), each stage's copper fixed
# for the next: 1 critical nets (Kelvin pairs, gate drives, UVLO), 2 low-voltage supply rails (0.4 mm trunks, 12 V 0.6 mm),
# 3 the I2C bus, VCTL and RUN_P, 4 the port meter and eFuse nets, 5 everything else (sequential, rip-up, TMAX). Stages 3-5
# may put vias through the L6 VBUS pour under the meter block (SOFTV; the pour refills round them at full clearance).
# Then tools/route_fixes.py, tools/patch_route.py (short connections, exact geometry; the U8 latch block and the Kelvin
# pairs are left for hand finishing), DRC with the project rules, route_checks and the open-net list.
# Usage: tools/route_stages.sh <work dir>   (needs base.kicad_pcb and net.net; coated rules, tools/domains.py)
set -uo pipefail
W=$(cd "$1" && (pwd -W 2>/dev/null || pwd)); ROOT=$(cd "$(dirname "$0")/.." && pwd); LAYOUT="$ROOT/../layout"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
export MSYS_NO_PATHCONV=1; cd "$ROOT"; q() { grep -v 'memory leak\|GetWidth called'; }
CRIT='/(SH\w*_[PN]|UVLO|GATE|GATE_A|GA1|GA2|G1|G2|G1PD_A|BRK_GATE|PRE_G|CL_G|G_L\d|GPU_L\d|GPD_L\d)$'
BUS='/(I2C_SCL|I2C_SDA|VCTL|RUN_P)$'
MET='/(EN_L\d|CSP_L\d|CSN_L\d|INP_L\d|V_L\d|ISCP_L\d|IWRN_L\d|TMR_L\d|GC_L\d|FLT_L\d|D_L\d|BST_L\d|PORT_FLT_N|PG_L\d)$'
RAILS='/(\+3V3_PI|VCTL|\+12V|\+12V_JET|\+12V_PI|\+12V_FAN|SPARE_SW|SPARE_ON|SP_SW1)$'
stage() {   # stage <name> <in board> <out board> [ONLY regex] [FONLY regex] [TMAX] [SOFTV regex]
  "$KP" tools/route_export.py "$W/$2" "$W/$1.copper.json" 2>&1 | q | tail -1
  ONLY="${4:-}" FONLY="${5:-^\$}" TMAX="${6:-2400}" SOFTV="${7:-}" NEG=0 python -u tools/grid_route.py "$W/$1.copper.json" "$W/$1.json" > "$W/$1.log" 2>&1
  grep -E '^done|Traceback' "$W/$1.log" | cut -c1-300
  "$KP" tools/route_import.py "$W/$2" "$W/$1.json" "$W/$3" 2>&1 | q | head -1 | cut -c1-200
}
[ -n "${ONLY_STAGE:-}" ] || {
  stage crit base.kicad_pcb s1.kicad_pcb "$CRIT" "$CRIT"
  stage rails s1.kicad_pcb s2.kicad_pcb "$RAILS" '^$'
  stage bus s2.kicad_pcb s3.kicad_pcb "$BUS" '^$' 900 '/VBUS$'
  stage met s3.kicad_pcb s4.kicad_pcb "$MET" '^$' 1800 '/VBUS$'
  stage rest s4.kicad_pcb s5.kicad_pcb '' '^$' "${TMAX:-2400}" '/VBUS$'
  "$KP" tools/route_fixes.py "$W/s5.kicad_pcb" "$W/s6.kicad_pcb" 2>&1 | q | tail -1
  cp "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/s6.kicad_pro"; cp "$LAYOUT/marengo_pdu_revb.kicad_dru" "$W/s6.kicad_dru"
  "$KC" pcb drc --format json -o "$W/s6.drc.json" "$W/s6.kicad_pcb" >/dev/null 2>&1
  SKIP='/(EN_A|FLT_A|BST_A|CSN_A|CSP_A|MID|L_B|SH\w*_[PN])$' "$KP" tools/patch_route.py "$W/s6.kicad_pcb" "$W/routed.kicad_pcb" "$W/s6.drc.json" 2>&1 | q | grep '^patch_route' | cut -c1-300
}
cp "$LAYOUT/marengo_pdu_revb.kicad_pro" "$W/routed.kicad_pro"; cp "$LAYOUT/marengo_pdu_revb.kicad_dru" "$W/routed.kicad_dru"
"$KC" pcb drc --format json --schematic-parity -o "$W/drc.json" "$W/routed.kicad_pcb" >/dev/null 2>&1
python -c "import json,collections,sys;d=json.load(open(sys.argv[1]));print('DRC',dict(collections.Counter(v['type'] for v in d['violations'] if not v['type'].startswith('silk'))),'unconnected',len(d['unconnected_items']),'parity',len(d.get('schematic_parity',[])))" "$W/drc.json"
python tools/open_nets.py "$W/drc.json" "$W/open_nets.csv"
"$KP" tools/route_checks.py "$W/routed.kicad_pcb" 2>&1 | q > "$W/checks.txt"; grep -v '^    (' "$W/checks.txt"
