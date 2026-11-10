#!/bin/bash
# fab_package.sh : write the order package for the main board into ../fab/ from the committed board file
# (../layout/marengo_pdu_revb.kicad_pcb, as refilled by tools/verify_board.sh) and check it against the board:
#   gerbers/   12 Gerber files (6 copper, 2 mask, 2 silkscreen, top paste, outline) and 2 Excellon drill files
#   marengo_pdu_revb-gerbers.zip   the same 14 files, for the fab's upload form
#   marengo_pdu_revb-pos.csv       positions of the fitted parts (top side; mm, board origin as in the Gerbers)
#   bom-jlc.csv                    Comment, Designator, Footprint, Quantity: one line per value and footprint, fitted parts
#   bom-digikey.csv                Quantity (for two sets with spares), Value / MPN, Reference designators: from ../kit-2sets.csv
#   BOARD.sha256                   the hash of the board file the package was made from
#   CHECK.txt                      tools/fab_check.py's comparison of the files with the board
# Nothing is ordered or uploaded. Run tools/verify_board.sh first: this script does not refill or change the board.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
ROOT=$(wp "$(dirname "$0")/.."); PB=$(wp "$ROOT/.."); B="$PB/layout/marengo_pdu_revb.kicad_pcb"; OUT="$PB/fab"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
rm -rf "$OUT/gerbers"; mkdir -p "$OUT/gerbers"
LAYERS=F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,Edge.Cuts
"$KC" pcb export gerbers -l "$LAYERS" --subtract-soldermask --no-netlist -o "$OUT/gerbers/" "$B" > "$OUT/export.log" 2>&1 || { cat "$OUT/export.log"; echo 'gerber export failed'; exit 1; }
"$KC" pcb export drill --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 -o "$OUT/gerbers/" "$B" >> "$OUT/export.log" 2>&1 || { cat "$OUT/export.log"; echo 'drill export failed'; exit 1; }
rm -f "$OUT"/gerbers/*-drl_map.gbr "$OUT"/gerbers/*.gbrjob
"$KC" pcb export pos --format csv --units mm --side front --exclude-dnp -o "$OUT/marengo_pdu_revb-pos.csv" "$B" >> "$OUT/export.log" 2>&1 || { cat "$OUT/export.log"; echo 'position export failed'; exit 1; }
rm -f "$OUT/export.log"
# the files carry no creation date, so a re-run on an unchanged board gives identical files
sed -i -e '/^%TF.CreationDate/d' -e 's/ date [0-9T: +-]*[*]$/*/' "$OUT"/gerbers/*.g*
sed -i -e 's/ date [0-9T: +-]*$//' -e '/TF.CreationDate/d' "$OUT"/gerbers/*.drl
"$PY" - "$PB" <<'PYEOF'
import csv,sys,zipfile,os,glob
PB=sys.argv[1]; out=PB+'/fab'
rows=list(csv.reader(open(PB+'/bom-rev-B.csv',encoding='utf-8')))[1:]
w=csv.writer(open(out+'/bom-jlc.csv','w',newline='',encoding='utf-8'),lineterminator='\n'); w.writerow(['Comment','Designator','Footprint','Quantity'])
for refs,val,fp,qty,dnp in rows:
    if not dnp: w.writerow([val,refs,fp.split(':')[-1],qty])
kit=[r for r in csv.reader(open(PB+'/kit-2sets.csv',encoding='utf-8')) if r and r[0] in ('main','assembly')]
w=csv.writer(open(out+'/bom-digikey.csv','w',newline='',encoding='utf-8'),lineterminator='\n'); w.writerow(['Quantity','Value / MPN','Reference designators','Footprint'])
for r in kit: w.writerow([r[7],r[2],r[1],r[3]])
z=out+'/marengo_pdu_revb-gerbers.zip'
if os.path.exists(z): os.remove(z)
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
    for g in sorted(glob.glob(out+'/gerbers/*')):
        zi=zipfile.ZipInfo(os.path.basename(g),date_time=(2026,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED   # fixed date: the zip changes only when a file does
        f.writestr(zi,open(g,'rb').read())
print('wrote',len(glob.glob(out+'/gerbers/*')),'gerber and drill files, the zip, the position file and two BOM files')
PYEOF
"$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(),' layout/marengo_pdu_revb.kicad_pcb')" "$B" > "$OUT/BOARD.sha256"
"$KP" "$ROOT/tools/fab_check.py" "$B" "$OUT" > "$OUT/CHECK.txt" 2>&1; rc=$?
grep -v 'memory leak\|GetWidth called\|image handler' "$OUT/CHECK.txt" > "$OUT/CHECK.tmp"; mv "$OUT/CHECK.tmp" "$OUT/CHECK.txt"; cat "$OUT/CHECK.txt"
exit $rc
