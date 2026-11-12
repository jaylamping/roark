#!/bin/bash
# R1d: build the arm variants and their hub-seat models (hub = the ridge6d mirror of rev C+: r 23 fill, R1.0 / R0.4 groove corners,
# reused, not rebuilt), then solve in a queue of at most two at a time with a free-memory check. 0.35 mm mesh control on the seat.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_chain.log
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_SEAT_MESH=0.35
build() {  # tag gap rib jobs
  export ARM_WIP_TAG=_$1 ARM_FLANK_GAP=$2 ARM_RIB_PROUD=$3 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_$1.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_$1.SLDPRT
  bash cad/scripts/fea/r1c/rebuild_ua.sh "$4"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_$1.log
  grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED $1" >> $L; return 1; }
  cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_$1.SLDPRT cad/_sim/ua2/
  H="$R/_wip/arm-sw-hub"; fin "$H"
  ARM_SW_DIR="$H" ARM_FEA_DIR="$R/_sim/ua2" timeout 1500 python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_$1.log 2>&1; fin "$H"
  ls cad/_sim/ua2/UA_HUBSEAT_r1d_$1.SLDPRT >/dev/null 2>&1 && echo "BUILT $1" >> $L || echo "HUB_BUILD_FAILED $1" >> $L
}
solve() {  # tag case folder instance [mesh]
  until [ "$(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -ge 14 ]; do sleep 60; done
  D=cad/_sim/$3; rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_$1.SLDPRT $D/; cp cad/_sim/ua2/HUB_GROOVE_r1d.STL $D/
  S="$R/_wip/$4"
  for t in 1 2; do fin "$S"; HS_SEAT_MESH=${5:-0.35} HS_MODEL=UA_HUBSEAT_r1d_$1.SLDPRT ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_$1.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$3" timeout 7200 python cad/scripts/fea/organic_fea.py $2 >> $D/run.log 2>&1; fin "$S"; ls $D/org16_$2.npz >/dev/null 2>&1 && break; sleep 60; done
  if ls $D/org16_$2.npz >/dev/null 2>&1; then timeout 2400 python cad/scripts/fea/r1c/hub_r1c.py $D/org16_$2.npz $D/HUB_GROOVE_r1d.STL > $D/post.txt 2>&1; echo "SOLVED $1 $2 $3 $(grep -E 'SANITY' $D/post.txt)" >> $L; else echo "SOLVE_FAILED $1 $2 $3" >> $L; fi
}
echo "start $(date)" > $L
build g01 0.1 0 "master:upper parts:fea_upper"
solve g01 HS_STOP_0_fine r1d_g01_stop arm-sw-fea &
build nom 0.1 0.1 "master:upper parts:fea_upper"
solve nom HS_STOP_0_fine r1d_nom_stop arm-sw-fea2 &
build g02 0.2 0 "master:upper parts:fea_upper"
wait
solve nom HS_G90_fine r1d_nom_g90 arm-sw-fea &
solve g01 HS_G90_fine r1d_g01_g90 arm-sw-fea2 &
build print 0.1 0.25 "master:upper parts:front parts:back"
wait
solve g02 HS_STOP_0_fine r1d_g02_stop arm-sw-fea &
solve g02 HS_G90_fine r1d_g02_g90 arm-sw-fea2 &
wait
solve nom HS_STOP_124_fine r1d_nom_stop124 arm-sw-fea &
solve g01 HS_STOP_0_fine r1d_g01_stop_rep arm-sw-fea2 &
wait
solve nom HS_STOP_0_fine r1d_nom_stop_rep arm-sw-fea &
solve g01 HS_STOP_0_fine r1d_g01_stop_m25 arm-sw-fea2 0.25 &
wait
echo "CHAIN_DONE $(date)" >> $L
