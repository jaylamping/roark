#!/bin/bash
# Combined-geometry pass (2026-11-12, coordinator): the shoulder thread's rev D hub with R1.2 Z-face lug-root fillets (bc16e97,
# reproduced on our ring FEA hub with their edge selection), our slot top edges broken 1.2 x 1.6 (ARM_SLOT_BREAK), the lug bolt
# joint as built (brass inserts, explicit bonds). Models: 0.1 gap (ringg01zi), nominal = 0.1 gap with 0.1 ribs (ringnomzi),
# 0.2 gap (ringg02zi). Then the solves in the coordinator's order, Intel direct sparse set by macro, post/lug/fin 0.8 control,
# global 4.0, memory watch. One SolidWorks job at a time, 3-minute gaps, clean closes; python checks under capped.py.
#   r1d_combined.sh [hub] [models] [solves]      (stages to run; default all three)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
PYC="python $R/scripts/fea/r1c/capped.py --mb 6144 -- python"
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
push() { until mkdir cad/_wip/.r1d_git_lock 2>/dev/null; do sleep 5; done; git add $1 >/dev/null 2>&1; git commit -q -m "$2" >/dev/null 2>&1; for t in 1 2 3; do git push -q origin left-arm-organic-r1 >/dev/null 2>&1 && break; sleep 10; done; rmdir cad/_wip/.r1d_git_lock; }
RV=cad/reviews/upper-arm/20261111_r1c-delta/r1d
export CAD_WRITER='upper-arm-r1:2bcc415b' SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 ARM_SLOT_BREAK=1.2,1.6
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
HUBF=HUB_RING_ZF.SLDPRT; HUBS=HUB_RING_ZF.STL
STAGES="${*:-hub models solves}"
echo "start $(date) stages: $STAGES" >> $L

if [[ " $STAGES " == *" hub "* ]]; then
  hung; waitfree
  ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py zfillet HUB_GROOVE_RING.SLDPRT $HUBF > cad/_wip/r1d_hub_zf.log 2>&1; fin "$R/_wip/arm-sw-hub"
  grep -q "LUG_ZROOTS feature True" cad/_wip/r1d_hub_zf.log || { echo "HUB_ZF_FAILED $(tail -2 cad/_wip/r1d_hub_zf.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
  echo "HUB_ZF built $(date +%H:%M): $(grep 'LUG_ZROOTS edges' cad/_wip/r1d_hub_zf.log)" >> $L
  # our filleted FEA hub against the shoulder thread's export: only the lug roots may differ from our unfilleted hub, and the
  # fillet must match theirs (fillet_check: sections, fixed axes)
  $PYC cad/scripts/fea/r1c/fillet_check.py cad/_sim/ua2/$HUBS cad/_sim/ua2/HUB_GROOVE_RING.STL 1.2 1.6 139.75,149.0 192.0,201.25 > $RV/hub_zf_vs_ring.json 2>cad/_wip/fc_zf.err
  $PYC cad/scripts/fea/r1c/fillet_check.py cad/_sim/ua2/$HUBS cad/_wip/shoulder_hub_bc16e97/shoulder_hub_left_revD_candidate.STL 1.2 1.6 139.75,149.0 192.0,201.25 > $RV/hub_zf_vs_bc16e97.json 2>>cad/_wip/fc_zf.err
  echo "HUB_ZF checked $(date +%H:%M)" >> $L
  push "$RV" "cad: R1d combined pass, FEA hub with the rev D lug-root fillets (bc16e97 selection) and its section checks"
  sleep 180
fi

build() {  # tag gap rib: arm FEA model (unless it exists for this gap/rib) and the hub-seat model with inserts, slot break, ZF hub
  hung; waitfree
  local tag=$1 gap=$2 rib=$3 arm=UA_ORGANIC_BONDED_v32_ring_$4.SLDPRT
  export ARM_WIP_TAG=_ring_$4 ARM_FLANK_GAP=$gap ARM_RIB_PROUD=$rib ARM_FEA_NAME=$arm HS_HUB_FILE=$HUBF HS_MODEL=UA_HUBSEAT_r1d_${tag}.SLDPRT
  if [ ! -f cad/_sim/ua2/$arm ]; then
    bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_ring_$4.log
    grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED $tag" >> $L; exit 1; }
    cp -p cad/_sim/upper-arm/$arm cad/_sim/ua2/
    echo "BUILT arm ring_$4 (gap $gap, ribs $rib) $(date +%H:%M)" >> $L
    sleep 180; waitfree
  fi
  rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_${tag}.SLDPRT
  ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_${tag}.log 2>&1; fin "$R/_wip/arm-sw-hub"
  grep -q "  inserts True" cad/_wip/r1d_hub_${tag}.log && grep -q "  pads True" cad/_wip/r1d_hub_${tag}.log || { echo "HUB_BUILD_FAILED $tag $(tail -2 cad/_wip/r1d_hub_${tag}.log | tr '\n' ' ' | cut -c1-200)" >> $L; exit 1; }
  echo "BUILT $tag $(date +%H:%M) $(grep -E 'SLOT_BREAK|insert bodies' cad/_wip/r1d_hub_${tag}.log | tr '\n' ' ' | cut -c1-200)" >> $L
  sleep 180
}
if [[ " $STAGES " == *" models "* ]]; then
  build ringg01zi 0.1 0 g01
  build ringnomzi 0.1 0.1 nom
  build ringg02zi 0.2 0 g02
fi

solve() {  # folder model case pad_E
  hung
  FOLDER=$1 MTAG=$2 CASE=$3 PADE=$4 HUBFILE=$HUBF HUBSTL=$HUBS HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
if [[ " $STAGES " == *" solves "* ]]; then
  solve r1d11_g01_stop ringg01zi HS_STOP_0_fine 0.5
  solve r1d11_g01_g90 ringg01zi HS_G90_fine 0.05
  solve r1d11_nom_stop ringnomzi HS_STOP_0_fine 0.5
  solve r1d11_nom_g90 ringnomzi HS_G90_fine 0.05
  solve r1d11_nom_stop124 ringnomzi HS_STOP_124_fine 0.5
  solve r1d11_g02_stop ringg02zi HS_STOP_0_fine 0.5
  solve r1d11_g01_stop_rep ringg01zi HS_STOP_0_fine 0.5
fi
echo "COMBINED_DONE $(date)" >> $L
