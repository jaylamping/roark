#!/bin/bash
# Hub D3c7 candidate (shoulder thread, local, not yet pushed; SHA-256 a73103ad...259b) against our halves, the final plates and the
# 0.70 ring (2026-11-13). Post-processing only, under capped.py. Outputs to cad/reviews/.../r1d/r1g/d3c7_*.
# Halves: the R1h back half if it has been built (cad/_wip/r1d_r1h_print/exports), otherwise the R1g halves (said in the output).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
RV=$R/reviews/upper-arm/20261111_r1c-delta/r1d/r1g
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
C7=$R/_wip/shoulder_hub_d3c7_local/hub_D3c7.STL
C4=$R/_wip/shoulder_hub_d3c4_a1057a9/shoulder_hub_left_revD3c4_candidate.STL
X=$R/_wip/r1d_r1g_print
H=$X/exports
if [ -f $R/_wip/r1d_r1h_print/exports/upper_arm_organic_back_left.STL ]; then H=$R/_wip/r1d_r1h_print/exports; fi
echo "halves: $H" > $RV/d3c7_halves_used.txt
sha256sum $C7 >> $RV/d3c7_halves_used.txt
# the final plates, Dia 3.4 holes (review 3, item 7: this line had HOLE_R 1.9, Dia 3.8, until 2026-11-14)
for t in 075:0.75 045:0.45; do $PYC $R/scripts/fea/r1c/plates_close_stl.py $X/checks/lug_plates_${t%%:*}_final.STL ${t#*:} 1.7 294.6 > /dev/null 2>&1; done
# 1, 2, 6 (+ the window, generic): hash, watertight, diff against D3c4, roots / plates proximity, bore fill
HUB_NEW=D3c7 HUB_OLD=D3c4 $PYC $R/scripts/fea/r1c/d3c4_check.py $C7 $C4 $H $X/checks/lug_plates_075_final.STL $RV/d3c7_check.json > $RV/d3c7_check.txt 2>&1
# 3: plate top and halves against the fillet, final plates 0.45 and 0.75
( for t in 045 075; do echo "### plates $t"; $PYC $R/scripts/fea/r1c/plate_fillet_gap.py $C7 $X/checks/lug_plates_${t}_final.STL $H 2>&1 | grep -v Warn; done ) > $RV/d3c7_plate_fillet_gap.txt
# 4: closing path on D3c7 + the 0.70 ring
$PYC -c "
import trimesh, numpy as np
HX,CZ=170.49,5.985875
h=trimesh.load(r'$C7')
a=trimesh.creation.annulus(36.2,38.4,0.70,sections=256); a.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0])); a.apply_translation((HX,302.0-0.35,CZ))
trimesh.util.concatenate([h,a]).export(r'$X/checks/hub_d3c7_with_shim070.STL')
" > /dev/null 2>&1
(cd cad/_wip/organic-arm/cad && CLOSE_EXTRA_PLANES=301.3 CLOSE_FORCE_CONTAINS=1 ARM_EXPORTS=$H FIT_JSON=$X/checks/rs02_fit.json HUB_STL=$X/checks/hub_d3c7_with_shim070.STL CLOSE_JSON=$RV/close_path_d3c7.json PYTHONPATH=. $PYC ../../../scripts/fea/r1c/close_path_r1c.py > $RV/close_path_d3c7.txt 2>&1)
# 5: the window footprint at 68 deg (Y 298: r 15.7-21.0, +-8 across) against our halves, and the 3.5 x 13 route from the as-built entry
$PYC $R/scripts/fea/r1c/cable_footprint_check.py $H $RV/d3c7_window68_footprint.txt $RV/d3c7_window68_footprint.png 68 16 15.7 21.0 > /dev/null 2>&1
mkdir -p $R/_wip/d3c7_route
SLACK_SKIP_LOOP=1 $PYC $R/scripts/fea/r1c/cable_slack.py $H $R/_wip/organic-arm/cad $R/_wip/d3c7_route 68 17.45 > $R/_wip/d3c7_route/out.txt 2>&1
cp $R/_wip/d3c7_route/cable_slack.json $RV/d3c7_route68_r17.45.json 2>/dev/null; cp $R/_wip/d3c7_route/cable_route_68_r17.4.png $RV/d3c7_route68_r17.45.png 2>/dev/null
# 5b: the shoulder's cable tie round the 98 deg boss tube, Y 300-304: the hub's material near theta 98 inside r 32, and our nearest part
$PYC -c "
import trimesh, numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
HX,CZ=170.49,5.985875
def sec(m,y):
    s=m.section(plane_origin=[0,y,0],plane_normal=[0,1,0]); g=Polygon()
    for e in ([] if s is None else s.discrete):
        if len(e)>=4: g=g.symmetric_difference(Polygon(e[:,[0,2]]).buffer(0))
    return g.buffer(0)
h=trimesh.load(r'$C7'); H=[trimesh.load(r'$H/upper_arm_organic_%s_left.STL'%n) for n in ('front','back')]
wedge=Polygon([(HX,CZ)]+[(HX+33*np.cos(np.radians(a)),CZ+33*np.sin(np.radians(a))) for a in np.arange(83,114,1)])
for y in (300.0,301.0,302.0,303.0,304.0):
    g=sec(h,y).intersection(wedge)
    ours=unary_union([sec(m,y) for m in H])
    if g.is_empty: print(f'Y {y}: no hub material at theta 83-113 inside r 33'); continue
    c=np.vstack([np.array(p.exterior.coords) for p in getattr(g,'geoms',[g])])
    r=np.hypot(c[:,0]-HX,c[:,1]-CZ)
    d=g.distance(ours) if not ours.is_empty else float('nan')
    print(f'Y {y}: hub material at theta 83-113, r {r.min():.1f}-{r.max():.1f} (the boss tube and what joins it); our nearest part {d:.2f} mm away')
" > $RV/d3c7_tie_boss98.txt 2>&1
echo "D3C7_CHECK_DONE"
