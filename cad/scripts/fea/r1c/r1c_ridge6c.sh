#!/bin/bash
# R1c ridge6c = ridge6 + bore-floor corner ring only where there is a floor (theta 72-108, front) + ridge top flattened at Y 301.5.
# arm rebuild -> (slice + mesh gate) in parallel with (hub-seat model -> G90 and STOP_0 side by side)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 ARM_RIDGE=1 ARM_SEAT_RIBS=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:front parts:back parts:fea_upper"
cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1c/rebuild_ridge6c.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo BUILD_FAILED; exit 1; }
cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v31.SLDPRT cad/_sim/ua2/
( cd cad/scripts/arm && ARM_EXPORTS=$R/_wip/r1c/exports ARM_PRINT_OUT=$R/_wip/r1c/print ARM_PRINT_SUFFIX=_r1c ARM_PRINT_HUBBAND_Y0=274.0 timeout 3600 python organic_print.py back front > $R/_wip/r1c/slice_r1c.log 2>&1
  cd $R/_wip/organic-arm/cad && ARM_EXPORTS=$R/_wip/r1c/exports ARM_PRINT_OUT=$R/_wip/r1c/print timeout 3600 python print_check.py back front > $R/_wip/r1c/print_check_r1c.log 2>&1; echo SLICE_DONE >> $R/_wip/r1c/print_check_r1c.log ) &
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_MODEL=UA_HUBSEAT_v31_ridge6c_bolted.SLDPRT
S="$R/_wip/arm-sw-fea"
for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" timeout 1500 python cad/scripts/fea/hub_seat.py build > cad/_wip/r1c/hub_build_ridge6c.log 2>&1 && break; done
fin "$S"
rm -rf cad/_sim/r1c_x; mkdir -p cad/_sim/r1c_x; cp cad/_sim/ua2/$HS_MODEL cad/_sim/r1c_x/; cp cad/_sim/ua2/HUB_GROOVE.STL cad/_sim/r1c_x/HUB_GROOVE_ridge6c.STL
one() { S="$R/_wip/$3"; for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$2" timeout 4800 python cad/scripts/fea/organic_fea.py $1 >> cad/_sim/$2/run.log 2>&1; fin "$S"; ls cad/_sim/$2/org16_$1.npz >/dev/null 2>&1 && { echo "$1 OK" >> cad/_sim/$2/run.log; break; }; echo "$1 try $t failed" >> cad/_sim/$2/run.log; sleep 60; done; }
one HS_STOP_0_fine r1c_x arm-sw-fea &
sleep 90
one HS_G90_fine r1c_x arm-sw-fea2 &
wait
echo CHAIN_DONE
