#!/bin/bash
# fab_check_buck.sh : ../../schematic/tools/fab_check.py on the buck board's order package (../fab) against the committed board
# file: the same comparisons as for the main board (file set and layer functions, six copper layers, the 60 x 85 mm outline,
# drill hits per tool, B.Mask with no opening drawn on the board, the position file's X, Y, rotation and side, both BOMs, the
# zip, the board file's hash). Exit 1 on any difference or a missing file.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
B=$(wp "$(dirname "$0")/.."); T=$(wp "$B/../schematic/tools")
KP="/c/Program Files/KiCad/10.0/bin/python.exe"
[ -x "$KP" ] || KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
export MSYS_NO_PATHCONV=1 FAB_STEM=marengo_buck12 FAB_OUTLINE=60x85 FAB_BMASK_OPENINGS=0
"$KP" "$T/fab_check.py" "${1:-$B/layout/marengo_buck12.kicad_pcb}" "${2:-$B/fab}" 2>&1 | grep -v 'memory leak\|GetWidth called\|image handler'
exit "${PIPESTATUS[0]}"
