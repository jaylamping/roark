#!/bin/bash
# R1c ridge6b: hub-only rebuild of ridge6 with the R1.0 round on the 45-side groove bottom corner (rev C+, Y 300.4) actually built.
# One SolidWorks instance; G90 and STOP_0 each solved twice (r1c_u, then repeat in r1c_v) to check reproducibility (bad-RAM suspicion).
cd /j/code/roark-wt/left-arm-organic
while pgrep -f r1c_ridge6.sh >/dev/null 2>&1 || ps -ef | grep -v grep | grep -q "r1c_ridge6.sh"; do sleep 30; done
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_MODEL=UA_HUBSEAT_v31_ridge6b_bolted.SLDPRT
export SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
S="$R/_wip/arm-sw-fea"
for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/ua2" timeout 1500 python cad/scripts/fea/hub_seat.py build > cad/_wip/r1c/hub_build_ridge6b.log 2>&1 && break; done
fin "$S"
grep -q "GROOVE_BOT_ROUND45: R1.0" cad/_wip/r1c/hub_build_ridge6b.log || { echo ROUND45_NOT_BUILT; exit 1; }
ls cad/_sim/ua2/$HS_MODEL || { echo HUB_BUILD_FAILED; exit 1; }
for d in r1c_u r1c_v; do rm -rf cad/_sim/$d; mkdir -p cad/_sim/$d; cp cad/_sim/ua2/$HS_MODEL cad/_sim/$d/; done
for d in r1c_u r1c_v; do for c in HS_G90_fine HS_STOP_0_fine; do
  for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$d" timeout 4800 python cad/scripts/fea/organic_fea.py $c >> cad/_sim/$d/run.log 2>&1; fin "$S"; ls cad/_sim/$d/org16_$c.npz >/dev/null 2>&1 && { echo "$c OK" >> cad/_sim/$d/run.log; break; }; echo "$c try $t failed" >> cad/_sim/$d/run.log; sleep 60; done
done; done
echo CHAIN_DONE
