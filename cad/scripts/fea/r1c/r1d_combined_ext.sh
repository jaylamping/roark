#!/bin/bash
# Combined pass, extension (2026-11-12, coordinator decision C: ribs are take-up features, not the strength path). Bracket the
# print's flank-gap band 0 to 0.2 with the flank bearing, for both loads: 0 gap (flank in contact, no ribs) G90 and STOP_0, and
# 0.2 gap G90. Waits for the resumed queue to finish (COMBINED_DONE). Same model recipe as r1d_combined.sh.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
until grep -q "COMBINED_DONE" $L; do sleep 30; done
echo "EXT start $(date +%H:%M)" >> $L
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_SLOT_BREAK=1.2,1.6
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
HUBF=HUB_RING_ZF.SLDPRT; HUBS=HUB_RING_ZF.STL
sleep 180
# 0 gap model: arm with the flank line-to-line and no ribs
hung; waitfree
export ARM_WIP_TAG=_ring_g00 ARM_FLANK_GAP=0 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT HS_HUB_FILE=$HUBF HS_MODEL=UA_HUBSEAT_r1d_ringg00zi.SLDPRT
if [ ! -f cad/_sim/ua2/UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT ]; then
  bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_ring_g00.log
  grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED ringg00" >> $L; exit 1; }
  cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_ring_g00.SLDPRT cad/_sim/ua2/
  echo "BUILT arm ring_g00 (gap 0, no ribs) $(date +%H:%M)" >> $L
  sleep 180; waitfree
fi
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_ringg00zi.SLDPRT
ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_ringg00zi.log 2>&1; fin "$R/_wip/arm-sw-hub"
grep -q "  inserts True" cad/_wip/r1d_hub_ringg00zi.log || { echo "HUB_BUILD_FAILED ringg00zi $(tail -2 cad/_wip/r1d_hub_ringg00zi.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
echo "BUILT ringg00zi $(date +%H:%M)" >> $L
sleep 180
solve() {
  hung
  FOLDER=$1 MTAG=$2 CASE=$3 PADE=$4 HUBFILE=$HUBF HUBSTL=$HUBS HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
solve r1d11_g00_g90 ringg00zi HS_G90_fine 0.05
solve r1d11_g00_stop ringg00zi HS_STOP_0_fine 0.5
solve r1d11_g02_g90 ringg02zi HS_G90_fine 0.05
echo "EXT_DONE $(date)" >> $L
