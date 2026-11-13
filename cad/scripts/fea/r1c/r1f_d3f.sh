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
echo "R1F_D3 cases (post control coarsened, bearing faces 0.8) start $(date +%H:%M)" >> $L
# (steps 1-3 done: FEA hub HUB_D3 built (R1.2 roots only to r 31.5, the new stretch stayed sharp); steps 1 and 2 done by hand on 2026-11-12: halves PASS; closing path with D3 + ring 0 path collisions, CLOSE_EXTRA_PLANES=301.3, CLOSE_FORCE_CONTAINS=1)
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
# FEA: the lug plates lumped into our faces (coordinator 2026-11-13): our post / web / pocket faces line-to-line with the lug Z
# faces (ARM_SLOT_CL=0), frictionless no-penetration in the lug set (HS_D3=1 puts the D3 lug faces there); the printed halves keep 0.5
export ARM_R1C=1 ARM_R1D=1 ARM_SLOT_BREAK=1.2,1.6 ARM_LUG_POCKET=1 ARM_SLOT_CL=0 HS_D3=1
# 5 cases
# probe: the post / web bearing faces merged into faces larger than the post control's 150 mm2 limit (they meshed at 4.0);
# take the first area limit whose mesh stays under NMAX nodes
NMAX=${NMAX:-410000}
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=${HS_POST_MESH:-0.8} R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3.SLDPRT HUBSTL=HUB_D3.STL DS_SOLVER=1 FEA_SAVE_DISP=1
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=HUB_D3.SLDPRT
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
AM=""
export HS_LUGFACE_MESH=0.8
for a in 1.0 1.2; do      # the general post / lug / fin control coarsened; the lug bearing faces stay 0.8
  FOLDER=r1f_d3_probe MTAG=d3i0 CASE=HS_LC2_fine PADE=0.5 FEA_MESH_ONLY=1 HS_POST_MESH=$a bash cad/scripts/fea/r1c/r1e_solve1.sh >/dev/null 2>&1
  n=$(grep -oE "mesh 0 nodes [0-9]+" cad/_sim/r1f_d3_probe/run.log | grep -oE "[0-9]+$")
  echo "PROBE d3i0 post mesh $a, lug faces 0.8: nodes ${n:-?} $(grep -E ' control ' cad/_sim/r1f_d3_probe/run.log | tr '
' ' ' | cut -c1-160)" >> $L
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then AM=$a; break; fi
done
if [ -z "$AM" ]; then AM=0.8; NMAX=460000; echo "R1F_D3: no coarsening fits; running at post 0.8 (449,696 nodes) under the memory watch" >> $L; fi
export HS_POST_MESH=$AM
export HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=${HS_POST_MESH:-0.8} R1C_RING=1 R1C_INSERTS=1 R1C_D3=1 HS_GLOBAL_EL=4.0
export HUBFILE=HUB_D3.SLDPRT HUBSTL=HUB_D3.STL DS_SOLVER=1 FEA_SAVE_DISP=1
job() {
  rm -f cad/_wip/hs_root_mesh/$1.txt
  FOLDER=$1 MTAG=d3i0 CASE=$2 PADE=$3 bash cad/scripts/fea/r1c/r1e_solve1.sh
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
job r1f_d3_yawp HS_LC2_fine 0.5
job r1f_d3_yawm HS_LC2M_fine 0.5
job r1f_d3_stop0 HS_STOP_0_fine 0.5
job r1f_d3_stop124 HS_STOP_124_fine 0.5
job r1f_d3_g90 HS_G90_fine 0.05
echo "R1F_D3_DONE $(date)" >> $L
