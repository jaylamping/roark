#!/bin/bash
# R1e wedge seat, bearing case (2026-11-12, coordinator): flank line-to-line, no ribs (0 gap). Waits for the running queue
# (COMBINED_DONE), builds the 0 gap model, then 0 gap G90, a mesh-only probe for the groove-band refinement, and 0 gap STOP_0 and
# STOP_124 with 0.3 on the lug roots (plus the groove band at 0.3 or 0.5 if under NMAX nodes). No preload in these.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
NMAX=${NMAX:-480000}
until grep -q "COMBINED_DONE" $L; do sleep 30; done
echo "R1E_GAP0 start $(date +%H:%M)" >> $L
S="$R/_wip/arm-sw-fea"
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_SLOT_BREAK=1.2,1.6
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
HUBF=HUB_RING_ZF.SLDPRT; HUBS=HUB_RING_ZF.STL
sleep 180
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
solve() {  # folder case padE
  hung
  FOLDER=$1 MTAG=ringg00zi CASE=$2 PADE=$3 HUBFILE=$HUBF HUBSTL=$HUBS HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-220) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
solve r1e_g00_g90 HS_G90_fine 0.05
# groove-band refinement: probe the node count
export HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8
G=""
for g in 0.3 0.5; do
  hung; waitfree
  P=cad/_sim/r1e_g00_probe; rm -rf $P; mkdir -p $P; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg00zi.SLDPRT $P/
  FEA_MESH_ONLY=1 HS_ROOT_MESH=0.3 HS_GROOVE_MESH=$g HS_MODEL=UA_HUBSEAT_r1d_ringg00zi.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1e_g00_probe" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $P/run.log 2>&1; fin "$S"
  n=$(grep -oE "mesh 0 nodes [0-9]+" $P/run.log | grep -oE "[0-9]+$")
  echo "PROBE r1e g00 root 0.3 groove $g: nodes ${n:-?} $(grep -E ' control ' $P/run.log | tr '\n' ' ' | cut -c1-200)" >> $L
  sleep 180
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then G=$g; break; fi
done
mkdir -p cad/_wip/hs_root_mesh cad/_wip/hs_groove_mesh
for ff in r1e_g00_stop r1e_g00_stop124; do
  echo 0.3 > cad/_wip/hs_root_mesh/$ff.txt
  if [ -n "$G" ]; then echo $G > cad/_wip/hs_groove_mesh/$ff.txt; else rm -f cad/_wip/hs_groove_mesh/$ff.txt; fi
done
[ -z "$G" ] && echo "GROOVE_REFINE_SKIPPED (over $NMAX nodes at 0.3 and 0.5)" >> $L
solve r1e_g00_stop HS_STOP_0_fine 0.5
solve r1e_g00_stop124 HS_STOP_124_fine 0.5
echo "R1E_GAP0_DONE $(date)" >> $L
