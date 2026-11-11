#!/bin/bash
# R1c ridge6d: hub-only vs ridge6c, spigot fill to r 23 (shoulder hub fd0cef8); STOP_0 and G90 side by side
cd /j/code/roark-wt/left-arm-organic
while ps -ef | grep -v grep | grep -q "r1c_ridge6c.sh"; do sleep 30; done
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_MODEL=UA_HUBSEAT_v31_ridge6d_bolted.SLDPRT
export SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
S="$R/_wip/arm-sw-fea3"
for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" timeout 1500 python cad/scripts/fea/hub_seat.py build > cad/_wip/r1c/hub_build_ridge6d.log 2>&1 && break; done
fin "$S"
rm -rf cad/_sim/r1c_y; mkdir -p cad/_sim/r1c_y; cp cad/_sim/ua2/$HS_MODEL cad/_sim/r1c_y/; cp cad/_sim/ua2/HUB_GROOVE.STL cad/_sim/r1c_y/HUB_GROOVE_ridge6d.STL
one() { S="$R/_wip/$3"; for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$2" timeout 4800 python cad/scripts/fea/organic_fea.py $1 >> cad/_sim/$2/run.log 2>&1; fin "$S"; ls cad/_sim/$2/org16_$1.npz >/dev/null 2>&1 && { echo "$1 OK" >> cad/_sim/$2/run.log; break; }; echo "$1 try $t failed" >> cad/_sim/$2/run.log; sleep 60; done; }
one HS_STOP_0_fine r1c_y arm-sw-fea &
sleep 90
one HS_G90_fine r1c_y arm-sw-fea2 &
wait
echo CHAIN_DONE
