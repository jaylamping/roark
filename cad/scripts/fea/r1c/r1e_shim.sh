#!/bin/bash
# R1e shim-body model (2026-11-12, coordinator): the arm with its end face lowered 0.70 (gap 0, no ribs, slot break, inserts as
# built) and the printed PETG shim ring (r 36.2-38.4 x 0.70) as its own body: no-penetration against the end face, held on the
# disc by the touching-face bond. G90 and STOP_0 (0.3 on the lug roots for the stop). Waits for the 0 gap stop cases.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
until grep -q "R1E_GAP0_DONE" $L; do sleep 30; done
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_SLOT_BREAK=1.2,1.6 ARM_END_DROP=0.70 ARM_SEAM_LEADIN=0.1,2.0
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1 HS_SHIM=0.70
HUBF=HUB_RING_ZF.SLDPRT; HUBS=HUB_RING_ZF.STL
echo "R1E_SHIM start $(date +%H:%M)" >> $L
sleep 180; hung; waitfree
export ARM_WIP_TAG=_ring_g00d70 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00d70.SLDPRT HS_HUB_FILE=$HUBF HS_MODEL=UA_HUBSEAT_r1d_ringg00s70i.SLDPRT
if [ ! -f cad/_sim/ua2/UA_ORGANIC_BONDED_v32_ring_g00d70.SLDPRT ]; then
  bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1e_build_g00d70.log
  grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED ring_g00d70" >> $L; exit 1; }
  cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_ring_g00d70.SLDPRT cad/_sim/ua2/
  echo "BUILT arm ring_g00d70 (gap 0, end face -0.70) $(date +%H:%M) $(grep -E 'END_DROP' cad/_wip/r1e_build_g00d70.log | tail -1)" >> $L
  sleep 180; waitfree
fi
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_ringg00s70i.SLDPRT
ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_ringg00s70i.log 2>&1; fin "$R/_wip/arm-sw-hub"
grep -q "  shim True" cad/_wip/r1d_hub_ringg00s70i.log && grep -q "  inserts True" cad/_wip/r1d_hub_ringg00s70i.log || { echo "HUB_BUILD_FAILED ringg00s70i $(tail -2 cad/_wip/r1d_hub_ringg00s70i.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "BUILT ringg00s70i $(date +%H:%M)" >> $L
sleep 180
export R1C_SHIM=0.70
mkdir -p cad/_wip/hs_root_mesh; echo 0.3 > cad/_wip/hs_root_mesh/r1e_s70_stop.txt
solve() {
  hung
  FOLDER=$1 MTAG=ringg00s70i CASE=$2 PADE=$3 HUBFILE=$HUBF HUBSTL=$HUBS HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0|shim contact" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-260) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
solve r1e_s70_g90 HS_G90_fine 0.05
solve r1e_s70_stop HS_STOP_0_fine 0.5
echo "R1E_SHIM_DONE $(date)" >> $L
