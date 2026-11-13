#!/bin/bash
# Review post-processing for one hub-seat result (2026-11-13): all-candidate-centre averages (hub_r1c R1C_ALL_CENTRES=1), the
# named-spot report, the per-post region report (yaw_report), and for the stops the lug force balance (fx_path). vm and the signed
# components (layer = signed across-layer tension, shear = magnitude) are reported separately by each script.
#   usage: bash post_r1g.sh FOLDER HOLE_R [PLATE_TOP]      (copies the reports to the review folder as FOLDER.*.txt)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
F=$1; HR=$2; PT=${3:-294.6}
D=cad/_sim/$F
RV=cad/reviews/upper-arm/20261111_r1c-delta/r1d/r1g
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
NPZ=$(ls $D/org16_*.npz | grep -v _disp | head -1)
DISP=${NPZ%.npz}_disp.npz
R1C_ALL_CENTRES=1 $PYC cad/scripts/fea/r1c/hub_r1c.py $NPZ $D/HUB_GROOVE_r1d.STL > $D/post_allc.txt 2>&1
$PYC cad/scripts/fea/r1c/spot_report.py $NPZ $D/post.txt $HR $PT > $D/spot_report.txt 2>&1
$PYC cad/scripts/fea/r1c/yaw_report.py $NPZ $D/post.txt > $D/region_report.txt 2>&1
[ -f "$DISP" ] && [[ "$NPZ" == *STOP* ]] && $PYC cad/scripts/fea/r1c/fx_path.py $NPZ $DISP $D/post.txt > $D/fx_path.txt 2>&1
for f in post_allc spot_report region_report fx_path; do [ -f $D/$f.txt ] && cp $D/$f.txt $RV/$F.$f.txt; done
echo "POST_DONE $F"
