#!/bin/bash
# fab_package_buck.sh : write the buck board's order package into ../fab/ from the committed board file
# (../layout/marengo_buck12.kicad_pcb), plotted from a copy kicad-cli has refilled with the project's rules, as the main
# board's ../../schematic/tools/fab_package.sh does, then checked by tools/fab_check_buck.sh:
#   gerbers/   12 Gerber files (6 copper, 2 mask, 2 silkscreen, top paste, outline) and 2 Excellon drill files
#   marengo_buck12-gerbers.zip     the same 14 files
#   marengo_buck12-pos.csv         positions of the fitted parts (top side)
#   bom-jlc.csv                    Comment, Designator, Footprint, Quantity from ../bom-buck12.csv
#   bom-digikey.csv                the buck rows of ../../kit-2sets.csv, with manufacturer and DigiKey part numbers
#   BOARD.sha256, CHECK.txt        the board file's hash; fab_check's result
# Nothing is ordered or uploaded; the board file is not changed.
set -uo pipefail
wp() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
B=$(wp "$(dirname "$0")/.."); PB=$(wp "$B/.."); BRD="$B/layout/marengo_buck12.kicad_pcb"; OUT="$B/fab"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
[ -x "$KP" ] || { KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3; KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
export MSYS_NO_PATHCONV=1
rm -rf "$OUT/gerbers"; mkdir -p "$OUT/gerbers"
RF=$(mktemp -d); RF=$(cd "$RF" && (pwd -W 2>/dev/null || pwd)); trap 'rm -rf "$RF"' EXIT
cp "$BRD" "$RF/marengo_buck12.kicad_pcb" && cp "$B/layout/marengo_buck12.kicad_pro" "$RF/" && cp "$B/fp-lib-table" "$RF/" && cp -r "$B/marengo_buck12.pretty" "$RF/" || { echo 'copying the board failed'; exit 1; }
"$KC" pcb drc --refill-zones --save-board --format json -o "$RF/drc.json" "$RF/marengo_buck12.kicad_pcb" > "$RF/drc.log" 2>&1; rc=$?
{ [ "$rc" = 0 ] && [ -s "$RF/drc.json" ]; } || { cat "$RF/drc.log"; echo "refill failed (kicad-cli exit $rc)"; exit 1; }
P="$RF/marengo_buck12.kicad_pcb"
LAYERS=F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,Edge.Cuts
"$KC" pcb export gerbers -l "$LAYERS" --subtract-soldermask --no-netlist -o "$OUT/gerbers/" "$P" > "$OUT/export.log" 2>&1 || { cat "$OUT/export.log"; echo 'gerber export failed'; exit 1; }
"$KC" pcb export drill --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 -o "$OUT/gerbers/" "$P" >> "$OUT/export.log" 2>&1 || { cat "$OUT/export.log"; echo 'drill export failed'; exit 1; }
rm -f "$OUT"/gerbers/*-drl_map.gbr "$OUT"/gerbers/*.gbrjob
"$KC" pcb export pos --format csv --units mm --side front --exclude-dnp -o "$OUT/marengo_buck12-pos.csv" "$P" >> "$OUT/export.log" 2>&1 || { cat "$OUT/export.log"; echo 'position export failed'; exit 1; }
rm -f "$OUT/export.log"
for f in "$OUT"/gerbers/*.g*; do sed -e '/^%TF.CreationDate/d' -e 's/ date [0-9T: +-]*[*]$/*/' "$f" > "$f.sedtmp" && mv "$f.sedtmp" "$f" || exit 1; done
for f in "$OUT"/gerbers/*.drl; do sed -e 's/ date [0-9T: +-]*$//' -e '/TF.CreationDate/d' "$f" > "$f.sedtmp" && mv "$f.sedtmp" "$f" || exit 1; done
"$PY" - "$PB" "$OUT" <<'PYEOF'
import csv,sys,zipfile,os,glob
PB,out=sys.argv[1],sys.argv[2]
rows=list(csv.reader(open(PB+'/buck12/bom-buck12.csv',encoding='utf-8')))[1:]
w=csv.writer(open(out+'/bom-jlc.csv','w',newline='',encoding='utf-8'),lineterminator='\n'); w.writerow(['Comment','Designator','Footprint','Quantity'])
for refs,val,fp,qty,dnp in rows:
    if not dnp: w.writerow([val,refs,fp.split(':')[-1],qty])
kit=[r for r in csv.reader(open(PB+'/kit-2sets.csv',encoding='utf-8')) if r and r[0]=='buck']
w=csv.writer(open(out+'/bom-digikey.csv','w',newline='',encoding='utf-8'),lineterminator='\n'); w.writerow(['Quantity','Value / MPN','Reference designators','Footprint','Manufacturer','Manufacturer PN','DigiKey PN','Supplier note'])
for r in kit: w.writerow([r[7],r[2],r[1],r[3]]+(r[8:12]+['','','',''])[:4])
z=out+'/marengo_buck12-gerbers.zip'
if os.path.exists(z): os.remove(z)
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
    for g in sorted(glob.glob(out+'/gerbers/*')):
        zi=zipfile.ZipInfo(os.path.basename(g),date_time=(2026,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED
        f.writestr(zi,open(g,'rb').read())
print('wrote',len(glob.glob(out+'/gerbers/*')),'gerber and drill files, the zip, the position file and two BOM files')
PYEOF
"$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(),' buck12/layout/marengo_buck12.kicad_pcb')" "$BRD" > "$OUT/BOARD.sha256"
bash "$B/tools/fab_check_buck.sh" > "$OUT/CHECK.txt" 2>&1; rc=$?; cat "$OUT/CHECK.txt"; exit $rc
