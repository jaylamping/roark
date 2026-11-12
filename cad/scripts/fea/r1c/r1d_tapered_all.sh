#!/bin/bash
# R1d baseline (tapered ridge ends, ribs on the full-height part, counterbore Dia 6.0): rebuild the variants, then the solves in
# priority order via r1d_chain4.sh (no hard client timeouts; stops on a HUNG_PID). Run only after the launch all-clear.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_tapered.log
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_TAPER=1 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1
build() {  # tag gap rib jobs
  ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED (HUNG_PID) before build $1" >> $L; exit 1; }
  export ARM_WIP_TAG=_t$1 ARM_FLANK_GAP=$2 ARM_RIB_PROUD=$3 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_t$1.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_t$1.SLDPRT
  bash cad/scripts/fea/r1c/rebuild_ua.sh "$4"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_t$1.log
  grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED t$1" >> $L; exit 1; }
  if [ "$1" != print ]; then
    cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_t$1.SLDPRT cad/_sim/ua2/
    (ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_t$1.log 2>&1; cd cad/scripts/arm && ARM_SW_DIR="$R/_wip/arm-sw-hub" python -c "from swlib import finish; finish()")
    ls cad/_sim/ua2/UA_HUBSEAT_r1d_t$1.SLDPRT >/dev/null 2>&1 || { echo "HUB_BUILD_FAILED t$1" >> $L; exit 1; }
  fi
  echo "BUILT t$1 $(date +%H:%M)" >> $L
}
echo "start $(date)" >> $L
build g01 0.1 0 "master:upper parts:fea_upper"
bash cad/scripts/fea/r1c/r1d_chain4.sh "tg01:HS_STOP_0_fine:r1d4_tg01_stop_soft:arm-sw-fea:1" &
build nom 0.1 0.1 "master:upper parts:fea_upper"
build g02 0.2 0 "master:upper parts:fea_upper"
build print 0.1 0.25 "master:upper parts:front parts:back"
wait
bash cad/scripts/fea/r1c/r1d_chain4.sh "tg01:HS_G90_fine:r1d4_tg01_g90_soft:arm-sw-fea:1" "tg02:HS_STOP_0_fine:r1d4_tg02_stop_soft:arm-sw-fea:1" "tg02:HS_G90_fine:r1d4_tg02_g90_soft:arm-sw-fea:1" "tnom:HS_STOP_0_fine:r1d4_tnom_stop:arm-sw-fea:0" "tnom:HS_G90_fine:r1d4_tnom_g90:arm-sw-fea:0" "tg01:HS_STOP_124_fine:r1d4_tg01_stop124_soft:arm-sw-fea:1" "tg01:HS_STOP_0_fine:r1d4_tg01_stop_soft_rep:arm-sw-fea:1" "tg01:HS_STOP_0_fine:r1d4_tg01_stop_soft_m25:arm-sw-fea:1:0.25"
echo "ALL_DONE $(date)" >> $L
