#!/bin/bash
# ridge6b solves, two at a time (machine limit lifted 2026-11-11 21:50Z): after the running r1c_u G90, run r1c_u STOP_0 with r1c_v G90, then r1c_v STOP_0
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 HS_GROOVE=1 HS_BOLTED=1 HS_MODEL=UA_HUBSEAT_v31_ridge6b_bolted.SLDPRT
while powershell -NoProfile -c "if (Get-Process -Id $1 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"; do sleep 30; done
fin "$R/_wip/arm-sw-fea"
one() { S="$R/_wip/$3"; for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$2" timeout 4800 python cad/scripts/fea/organic_fea.py $1 >> cad/_sim/$2/run.log 2>&1; fin "$S"; ls cad/_sim/$2/org16_$1.npz >/dev/null 2>&1 && { echo "$1 OK" >> cad/_sim/$2/run.log; break; }; echo "$1 try $t failed" >> cad/_sim/$2/run.log; sleep 60; done; }
ls cad/_sim/r1c_u/org16_HS_G90_fine.npz >/dev/null 2>&1 || one HS_G90_fine r1c_u arm-sw-fea
one HS_STOP_0_fine r1c_u arm-sw-fea &
sleep 120
one HS_G90_fine r1c_v arm-sw-fea2 &
wait
one HS_STOP_0_fine r1c_v arm-sw-fea
echo CHAIN_DONE
