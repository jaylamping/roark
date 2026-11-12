#!/bin/bash
# R1e print geometry (WIP only, 2026-11-12): play-free joint by a printed shim ring. Halves with the flank line-to-line (gap 0),
# no ribs, the slot edge break 1.2 x 1.6, the end face lowered 0.70 (nominal shim) and 0.1 x 2 mm lead-ins at the ridge ends.
# Then slice (crown blocker), mesh gate, closing path against hub bc16e97 with a 0.70 ring on its disc, and the hub-end coupon
# cut at Y 284. Waits for the 0 gap FEA model build (both use the shared rebuild log). Python checks under capped.py.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1e_print.log
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
if [ "$R1E_SKIP_BUILD" != 1 ]; then
until grep -qE "BUILT ringg00zi|HUB_BUILD_FAILED ringg00zi|BUILD_FAILED ringg00" cad/_wip/r1d_combined.log; do sleep 30; done
sleep 60
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
waitfree
echo "start $(date)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_WIP_TAG=_r1e_print ARM_FLANK_GAP=0 ARM_RIB_PROUD=0
export ARM_SLOT_BREAK=1.2,1.6 ARM_END_DROP=0.70 ARM_SEAM_LEADIN=0.1,2.0
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:front parts:back"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1e_build_print.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED $(grep 'STOP at' cad/_wip/organic-arm/rebuild_ua.log | tail -1)" >> $L; exit 1; }
fi
[ "$R1E_SKIP_BUILD" = 1 ] && export ARM_R1C=1 ARM_R1D=1 ARM_FLANK_GAP=0 CAD_WRITER='upper-arm-r1:2bcc415b'
echo "BUILT r1e halves $(date +%H:%M) $(grep -E 'END_DROP|SEAM_LEADIN|SLOT_BREAK0F' cad/_wip/r1e_build_print.log | tr '\n' ' ' | cut -c1-240)" >> $L
X=$R/_wip/r1d_r1e_print      # the WIP folder of ARM_WIP_TAG _r1e_print (master WIP = _wip/r1d<tag>)
mkdir -p $X/exports $X/checks
cp -p cad/exports/upper-arm/upper_arm_organic_rs02_ring_left.STL $X/exports/
(cd cad/scripts/arm && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print ARM_PRINT_SUFFIX=_r1e ARM_PRINT_HUBBAND_Y0=274.0 ARM_PRINT_FLANK_BLOCKER=1 ARM_FLANK_GAP=0 $PYC organic_print.py back front > $X/slice.log 2>&1)
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports ARM_PRINT_OUT=$X/print $PYC print_check.py back front > $X/print_check.log 2>&1)
echo "SLICED+GATED $(grep -E '"job"' $X/print_check.log | sed -E 's/.*"job": "([a-z]+)", "mesh_gate": "([A-Z]+)".*"time_s": ([0-9]+), "grams": ([0-9.]+).*/\1 \2 \3s \4g/' | tr '\n' ' ')" >> $L
# hub bc16e97 with a 0.70 shim ring on its disc (r 36.2-38.4, Y 301.30-302.00), as one mesh for the closing path
$PYC -c "
import trimesh
h = trimesh.load(r'$R/_wip/shoulder_hub_bc16e97/shoulder_hub_left_revD_candidate.STL')
a = trimesh.creation.annulus(36.2, 38.4, 0.70, sections=256); a.apply_transform(trimesh.transformations.rotation_matrix(-1.5707963, [1, 0, 0])); a.apply_translation((170.49, 302.0 - 0.35, 5.985875))
trimesh.util.concatenate([h, a]).export(r'$X/checks/hub_bc16e97_with_shim070.STL')
print(a.bounds)
" >> $L 2>&1
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports FIT_JSON=$X/checks/rs02_fit.json HUB_STL=$X/checks/hub_bc16e97_with_shim070.STL CLOSE_JSON=$X/checks/close_path_bc16e97.json PYTHONPATH=. $PYC ../../../scripts/fea/r1c/close_path_r1c.py > $X/checks/close_path_bc16e97.log 2>&1)
echo "CLOSE_CHECKED $(grep -E 'final overlap|path_collisions' $X/checks/close_path_bc16e97.log | grep -E 'hub|final' | tr -s ' ' | cut -c1-220 | tr '\n' ' ')" >> $L
# coupon (1): the hub end cut at Y 284
C=$R/_wip/r1e_coupon
$PYC cad/scripts/fea/r1c/coupon_cut.py $X/exports $C/exports 284 > $C.json 2>&1
(cd cad/scripts/arm && ARM_EXPORTS=$C/exports ARM_PRINT_OUT=$C/print ARM_PRINT_SUFFIX=_r1e_coupon ARM_PRINT_HUBBAND_Y0=274.0 ARM_PRINT_FLANK_BLOCKER=1 ARM_FLANK_GAP=0 $PYC organic_print.py back front > $C/slice.log 2>&1)
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$C/exports ARM_PRINT_OUT=$C/print $PYC print_check.py back front > $C/print_check.log 2>&1)
echo "COUPON $(grep -E '"job"' $C/print_check.log | sed -E 's/.*"job": "([a-z]+)", "mesh_gate": "([A-Z]+)".*"time_s": ([0-9]+), "grams": ([0-9.]+).*/\1 \2 \3s \4g/' | tr '\n' ' ')" >> $L
echo "R1E_PRINT_DONE $(date)" >> $L
