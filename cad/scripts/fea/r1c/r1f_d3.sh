#!/bin/bash
# R1f on hub rev D3 (shoulder thread 22ead5b; 2026-11-12). One process; every SolidWorks step under the one-job lock
# (cad/_wip/.fea_job_lock; 180 s since the last job; >= 16 GB free):
#   1. the R1f halves (web from offset 26.0), slice, gate        (r1f_build.sh)
#   2. closing path: D3 + the 0.70 ring + four 0.45 lug plates against the R1f halves
#   3. our FEA hub with the D3 lugs (hub_seat.py d3hub), checked by section against the D3 STL
#   4. the hub-seat model: the 0 gap arm (shim lumped), R1f pocket / webs / 0.5 slot, D3 hub, inserts and bolts
#   5. YAW +17, YAW -17, STOP_0, STOP_124, G90 on the global 4.0 mesh, one at a time (r1e_solve1.sh)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
LK=cad/_wip/.fea_job_lock
STAMP=cad/_wip/.fea_job_last_end
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
SWI="C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py"
D3=$R/_wip/shoulder_hub_d3_22ead5b/shoulder_hub_left_revD3_candidate.STL
X=$R/_wip/r1d_r1f_print
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
lock() { until mkdir $LK 2>/dev/null; do sleep 15; done; echo "$1 $$" > $LK/owner
  until ! python "$SWI" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
  if [ -f $STAMP ]; then while [ $(( $(date +%s) - $(cat $STAMP) )) -lt 180 ]; do sleep 10; done; fi
  until [ "$(free)" -ge 16000 ]; do sleep 60; done; }
unlock() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; date +%s > $STAMP; grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK; }
trap 'grep -q " $$\$" $LK/owner 2>/dev/null && rm -rf $LK' EXIT
echo "R1F_D3 start $(date +%H:%M)" >> $L
# 1
bash cad/scripts/fea/r1c/r1f_build.sh
grep -q "BUILD_FAILED" <(tail -3 cad/_wip/r1f_build.log) && { echo "R1F_D3 STOP: halves build failed" >> $L; exit 1; }
echo "R1F_D3 halves: $(grep SLICED cad/_wip/r1f_build.log | tail -1)" >> $L
# 2 closing path
mkdir -p $X/checks
$PYC -c "
import trimesh, numpy as np
HX, CZ = 170.49, 5.985875
h = trimesh.load(r'$D3')
a = trimesh.creation.annulus(36.2, 38.4, 0.70, sections=256); a.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])); a.apply_translation((HX, 302.0 - 0.35, CZ))
pl = []
for side in (-1, 1):
    for z0, z1 in ((11.0, 11.45), (0.55, 1.0)):      # 0.45 plates on the lug faces (planes Z 1.0 / 11.0), X offset 18.96-34.2, Y 288.2-294.6
        b = trimesh.creation.box(extents=(34.2 - 18.96, 294.6 - 288.2, z1 - z0)); b.apply_translation((HX + side * (34.2 + 18.96) / 2, (294.6 + 288.2) / 2, (z0 + z1) / 2)); pl.append(b)
trimesh.util.concatenate([h, a] + pl).export(r'$X/checks/hub_d3_ring070_plates045.STL')
print('hub + ring + plates written')
" >> $L 2>&1
(cd cad/_wip/organic-arm/cad && ARM_EXPORTS=$X/exports FIT_JSON=$X/checks/rs02_fit.json HUB_STL=$X/checks/hub_d3_ring070_plates045.STL CLOSE_JSON=$X/checks/close_path_d3.json PYTHONPATH=. $PYC ../../../scripts/fea/r1c/close_path_r1c.py > $X/checks/close_path_d3.log 2>&1)
echo "R1F_D3 CLOSE_CHECKED $(grep -E 'final overlap|path_collisions' $X/checks/close_path_d3.log | grep -E 'hub|final' | tr -s ' ' | cut -c1-260 | tr '\n' ' ')" >> $L
$PYC $R/scripts/fea/r1c/d3_check.py $D3 $R/_wip/shoulder_hub_bc16e97/shoulder_hub_left_revD_candidate.STL $X/exports $X/checks/d3_fit.json > $X/checks/d3_fit.log 2>&1
echo "R1F_D3 fit: $(tail -8 $X/checks/d3_fit.log | tr '\n' ' ' | cut -c1-400)" >> $L
# 3 FEA hub
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5
S=$R/_wip/arm-sw-d3hub
lock d3hub
ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py d3hub HUB_GROOVE_RING.SLDPRT HUB_D3.SLDPRT > cad/_wip/r1f_d3hub.log 2>&1
unlock "$S"
grep -q "saved HUB_D3.SLDPRT" cad/_wip/r1f_d3hub.log || { echo "R1F_D3 STOP: d3hub failed $(tail -3 cad/_wip/r1f_d3hub.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "R1F_D3 FEA hub built: $(grep -E 'D3 ' cad/_wip/r1f_d3hub.log | tr '\n' ' ' | cut -c1-200)" >> $L
$PYC $R/scripts/fea/r1c/d3_check.py $R/_sim/ua2/HUB_D3.STL $D3 $X/exports $X/checks/d3_feahub_vs_d3.json > $X/checks/d3_feahub_vs_d3.log 2>&1
echo "R1F_D3 FEA hub vs D3: $(head -2 $X/checks/d3_feahub_vs_d3.log | tr '\n' ' ' | cut -c1-300)" >> $L
# 4 hub-seat model
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_d3i.SLDPRT
S=$R/_wip/arm-sw-d3build
lock d3build
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_d3i.SLDPRT
ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1f_d3_hs.log 2>&1
unlock "$S"
grep -q "  inserts True" cad/_wip/r1f_d3_hs.log || { echo "R1F_D3 STOP: hub-seat build failed $(tail -3 cad/_wip/r1f_d3_hs.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "R1F_D3 BUILT d3i $(date +%H:%M) $(grep -E 'R1F_' cad/_wip/r1f_d3_hs.log | tr '\n' ' ' | cut -c1-200)" >> $L
# 5 cases
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3.SLDPRT HUBSTL=HUB_D3.STL DS_SOLVER=1 FEA_SAVE_DISP=1
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=d3i CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1f_d3_yawp HS_LC2_fine 0.5
job r1f_d3_yawm HS_LC2M_fine 0.5
job r1f_d3_stop0 HS_STOP_0_fine 0.5
job r1f_d3_stop124 HS_STOP_124_fine 0.5
job r1f_d3_g90 HS_G90_fine 0.05
echo "R1F_D3_DONE $(date)" >> $L
