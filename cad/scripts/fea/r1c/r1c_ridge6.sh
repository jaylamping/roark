#!/bin/bash
# R1c ridge6 (hub only vs ridge5): groove cut clipped at Y 302, 1.0 round on the 45-side groove bottom corner. ONE instance, solves in series.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_MODEL=UA_HUBSEAT_v31_ridge6_bolted.SLDPRT
export SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_R1C=1 ARM_RIDGE=1 ARM_SEAT_RIBS=0
bash cad/_wip/organic-arm/run/rebuild_ua.sh "master:upper parts:front parts:back parts:fea_upper"
cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1c/rebuild_ridge6.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo BUILD_FAILED; exit 1; }
cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v31.SLDPRT cad/_sim/ua2/
S="$R/_wip/arm-sw-fea"
for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" timeout 1500 python cad/scripts/fea/hub_seat.py build > cad/_wip/r1c/hub_build_ridge6.log 2>&1 && break; done
fin "$S"
ls cad/_sim/ua2/$HS_MODEL || { echo HUB_BUILD_FAILED; exit 1; }
rm -rf cad/_sim/r1c_t; mkdir -p cad/_sim/r1c_t; cp cad/_sim/ua2/$HS_MODEL cad/_sim/r1c_t/
for c in HS_G90_fine HS_STOP_0_fine; do
  for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1c_t" timeout 4800 python cad/scripts/fea/organic_fea.py $c >> cad/_sim/r1c_t/run.log 2>&1; fin "$S"; ls cad/_sim/r1c_t/org16_$c.npz >/dev/null 2>&1 && { echo "$c OK" >> cad/_sim/r1c_t/run.log; break; }; echo "$c try $t failed" >> cad/_sim/r1c_t/run.log; sleep 60; done
done
echo CHAIN_DONE
