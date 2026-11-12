#!/bin/bash
# After the 0.1 gap STOP_0: rebuild print / tg02 / tnom with 5-segment ramps (+ the tg02 pad model, pads E 0.5 MPa for the stop),
# then the release-order solves (coordinator 2026-11-12 08:29Z): nominal STOP_0, G90, STOP_124; then the 0.2 gap STOP_0.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_after.log
until grep -q "FIX_DONE" cad/_wip/r1d_fix.log 2>/dev/null; do sleep 30; done
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_TAPER=1 ARM_TAPER_SEGS=5 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1
echo "start $(date)" >> $L
b() {  # tag gap rib jobs [pads-suffix] [padE]
  ARM_WIP_TAG=_t$1 ARM_FLANK_GAP=$2 ARM_RIB_PROUD=$3 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_t$1.SLDPRT bash cad/scripts/fea/r1c/rebuild_ua.sh "$4"
  cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_t$1_seg5.log
  grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED t$1" >> $L; return 1; }
  echo "BUILT t$1 $(date +%H:%M)" >> $L; sleep 60
  if [ "$1" != print ]; then
    cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_t$1.SLDPRT cad/_sim/ua2/
    M=UA_HUBSEAT_r1d_t$1${5}.SLDPRT; rm -f cad/_sim/ua2/$M
    HS_PADS=$([ -n "$5" ] && echo 1 || echo 0) HS_PAD_E=${6:-0.05} ARM_WIP_TAG=_t$1 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_t$1.SLDPRT HS_MODEL=$M ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_t$1${5}_seg5.log 2>&1; fin "$R/_wip/arm-sw-hub"
    grep -q "bolts True" cad/_wip/r1d_hub_t$1${5}_seg5.log && echo "BUILT hub-seat t$1$5" >> $L || echo "HUB_BUILD_FAILED t$1$5" >> $L
    sleep 60
  fi
}
b print 0.1 0.25 "master:upper parts:front parts:back"
echo "PRINT_READY $(date +%H:%M)" >> $L
b nom 0.1 0.1 "master:upper parts:fea_upper"
b g02 0.2 0 "master:upper parts:fea_upper" p 0.5
sleep 120
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh \
  "tnom:HS_STOP_0_fine:r1d7_tnom_stop:arm-sw-fea:0:0.5" \
  "tnom:HS_G90_fine:r1d7_tnom_g90:arm-sw-fea:0:0.5" \
  "tnom:HS_STOP_124_fine:r1d7_tnom_stop124:arm-sw-fea:0:0.5" \
  "tg02p:HS_STOP_0_fine:r1d7_tg02p_stop:arm-sw-fea:0:0.5"
echo "AFTER_DONE $(date)" >> $L
