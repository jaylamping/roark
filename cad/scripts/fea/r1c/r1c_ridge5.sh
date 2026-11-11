#!/bin/bash
# R1c ridge5: + full seat collar (r 35.9-37.4, Y 296-302), 0.25 bore-floor corner fillet, 0.2 ridge tip chamfer; hub with 0.4 groove-bottom and
# spigot-bottom rounds and a 1.0 lug-root fillet (X-facing sides). master, halves, FEA model v31 -> bolted hub-seat model -> G90, STOP_0
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 ARM_RIDGE=1 ARM_SEAT_RIBS=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
bash cad/_wip/organic-arm/run/rebuild_ua.sh "master:upper parts:front parts:back parts:fea_upper"
cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1c/rebuild_ridge5.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo BUILD_FAILED; exit 1; }
cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v31.SLDPRT cad/_sim/ua2/
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_MODEL=UA_HUBSEAT_v31_ridge5_bolted.SLDPRT
H="$R/_wip/arm-sw-hub"
for t in 1 2; do fin "$H"; ARM_SW_DIR="$H" ARM_FEA_DIR="$R/_sim/ua2" timeout 1500 python cad/scripts/fea/hub_seat.py build > cad/_wip/r1c/hub_build_ridge5.log 2>&1 && break; done
fin "$H"; sleep 30
ls cad/_sim/ua2/$HS_MODEL || { echo HUB_BUILD_FAILED; exit 1; }
for d in r1c_q r1c_r; do rm -rf cad/_sim/$d; mkdir -p cad/_sim/$d; cp cad/_sim/ua2/$HS_MODEL cad/_sim/$d/; done
one() { for t in 1 2; do S="$R/_wip/$3"; fin "$S"; echo "dir $R/_sim/$2" >> cad/_sim/$2/run.log; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$2" timeout 4800 python cad/scripts/fea/organic_fea.py $1 >> cad/_sim/$2/run.log 2>&1; fin "$S"; ls cad/_sim/$2/org16_$1.npz >/dev/null 2>&1 && { echo "$1 OK" >> cad/_sim/$2/run.log; break; }; echo "$1 try $t failed" >> cad/_sim/$2/run.log; sleep 60; done; }
one HS_G90_fine r1c_q arm-sw-fea &
sleep 240
one HS_STOP_0_fine r1c_r arm-sw-fea2 &
wait
echo CHAIN_DONE
