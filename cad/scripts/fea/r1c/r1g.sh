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
echo "R1G start $(date +%H:%M)" >> $L
# 1 halves
bash cad/scripts/fea/r1c/r1g_build.sh
grep -q "BUILD_FAILED" <(tail -3 cad/_wip/r1g_build.log) && { echo "R1G STOP: halves build failed" >> $L; exit 1; }
echo "R1G halves: $(grep SLICED cad/_wip/r1g_build.log | tail -1)" >> $L
# 2 FEA hub with the straight extended lug (D3b as described: outer face X offset 34.4 over Y 288-296, R1.2 Z roots, R0.8 outward root; their STL still owed)
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0.5 ARM_PLATE_LUMP=1 HS_D3=1
S=$R/_wip/arm-sw-d3shub
lock d3shub
ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py d3hub HUB_RING_ZF.SLDPRT HUB_D3S.SLDPRT > cad/_wip/r1g_d3shub.log 2>&1
unlock "$S"
grep -q "saved HUB_D3S.SLDPRT" cad/_wip/r1g_d3shub.log || { echo "R1G STOP: FEA hub failed $(tail -3 cad/_wip/r1g_d3shub.log | tr '
' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "R1G FEA hub: $(grep -E 'D3' cad/_wip/r1g_d3shub.log | tr '
' ' ' | cut -c1-200)" >> $L
# 3 closing path: R1g halves against our straight-lug hub + the 0.70 ring
X=$R/_wip/r1d_r1g_print
$PYC -c "
import trimesh, numpy as np
h = trimesh.load(r'$R/_sim/ua2/HUB_D3S.STL')
a = trimesh.creation.annulus(36.2, 38.4, 0.70, sections=256); a.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])); a.apply_translation((170.49, 302.0 - 0.35, 5.985875))
trimesh.util.concatenate([h, a]).export(r'$X/checks/hub_d3s_with_shim070.STL')
print('watertight', h.is_watertight)
" >> $L 2>&1
(cd cad/_wip/organic-arm/cad && CLOSE_EXTRA_PLANES=301.3 CLOSE_FORCE_CONTAINS=1 ARM_EXPORTS=$X/exports FIT_JSON=$X/checks/rs02_fit.json HUB_STL=$X/checks/hub_d3s_with_shim070.STL CLOSE_JSON=$X/checks/close_path_d3s.json PYTHONPATH=. $PYC ../../../scripts/fea/r1c/close_path_r1c.py > $X/checks/close_path_d3s.log 2>&1)
echo "R1G CLOSE_CHECKED $(grep -E 'final overlap|path_collisions' $X/checks/close_path_d3s.log | grep -E 'hub|final' | tr -s ' ' | cut -c1-200 | tr '
' ' ')" >> $L
# 4 hub-seat model: the 0 gap arm (shim lumped), R1g pocket / webs / 0.5 slot, the plates lumped inside their outline only
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3S.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_r1g.SLDPRT
S=$R/_wip/arm-sw-r1gbuild
lock r1gbuild
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_r1g.SLDPRT
ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1g_hs.log 2>&1
unlock "$S"
grep -q "  inserts True" cad/_wip/r1g_hs.log || { echo "R1G STOP: hub-seat build failed $(tail -3 cad/_wip/r1g_hs.log | tr '
' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "R1G BUILT model $(date +%H:%M) $(grep -E 'R1F_PLATE' cad/_wip/r1g_hs.log | tr '
' ' ' | cut -c1-200)" >> $L
# 5 cases
# probe: the post / web bearing faces merged into faces larger than the post control's 150 mm2 limit (they meshed at 4.0);
# take the first area limit whose mesh stays under NMAX nodes
NMAX=${NMAX:-410000}
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=${HS_POST_MESH:-0.8} R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3S.SLDPRT HUBSTL=HUB_D3S.STL DS_SOLVER=1 FEA_SAVE_DISP=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3S.SLDPRT
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
AM=""
export HS_LUGFACE_MESH=0.8
for a in 1.0 1.2; do      # the general post / lug / fin control coarsened; the lug bearing faces stay 0.8
  FOLDER=r1g_probe MTAG=r1g CASE=HS_LC2_fine PADE=0.5 FEA_MESH_ONLY=1 HS_POST_MESH=$a bash cad/scripts/fea/r1c/r1e_solve1.sh >/dev/null 2>&1
  n=$(grep -oE "mesh 0 nodes [0-9]+" cad/_sim/r1g_probe/run.log | grep -oE "[0-9]+$")
  echo "PROBE r1g post mesh $a, lug faces 0.8: nodes ${n:-?} $(grep -E ' control ' cad/_sim/r1g_probe/run.log | tr '
' ' ' | cut -c1-160)" >> $L
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then AM=$a; break; fi
done
if [ -z "$AM" ]; then AM=0.8; NMAX=460000; echo "R1G: no coarsening fits; running at post 0.8 (449,696 nodes) under the memory watch" >> $L; fi
export HS_POST_MESH=$AM
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=${HS_POST_MESH:-0.8} R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3S.SLDPRT HUBSTL=HUB_D3S.STL DS_SOLVER=1 FEA_SAVE_DISP=1
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=r1g CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1g_yawp HS_LC2_fine 0.5
job r1g_yawm HS_LC2M_fine 0.5
job r1g_stop0 HS_STOP_0_fine 0.5
job r1g_stop124 HS_STOP_124_fine 0.5
job r1g_g90 HS_G90_fine 0.05
echo "R1G_DONE $(date)" >> $L
