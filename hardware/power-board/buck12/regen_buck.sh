#!/bin/bash
# Regenerate the buck board sheet and run ERC, the netlist checks (check_buck.py) and the wire scan. Usage: buck12/regen_buck.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
[ -x "$K" ] || K="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
PY="python3 -X utf8"; $PY -c "" 2>/dev/null || PY="python -X utf8"
TMP=$(mktemp -d); cd "$ROOT"
$PY gen_buck.py "$ROOT"
"$K" sch erc --severity-all --format report -o "$TMP/erc.rpt" buck12.kicad_sch >/dev/null 2>&1
grep -E 'ERC messages' "$TMP/erc.rpt"; grep -E '^\[' "$TMP/erc.rpt" | sort | uniq -c || true
"$K" sch export netlist --format kicadsexpr -o "$TMP/net.net" buck12.kicad_sch >/dev/null 2>&1
$PY check_buck.py ../schematic/tools "$TMP/net.net" | grep -E '^FAIL|^FAILS|^audited'
$PY ../schematic/tools/wirescan.py "$ROOT" | grep -v PWR_FLAG || true
