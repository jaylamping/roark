#!/bin/bash
# R1c "nothing else moved": G90_fine on the bonded FEA model v31 and HALFK31_fine (key pair 3+1) on the halves (the R1c master), vs R1 (v28)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
D=r1c_w; rm -rf cad/_sim/$D; mkdir -p cad/_sim/$D
cp cad/_sim/upper-arm/UA_ORGANIC_BONDED_v31.SLDPRT cad/_sim/$D/
cp cad/_wip/r1c/upper_arm_organic_master_left_r1c.SLDPRT cad/_sim/$D/UA_HALVES_v31.SLDPRT
export ORG_MODEL=UA_ORGANIC_BONDED_v31.SLDPRT HALVES_MODEL=UA_HALVES_v31.SLDPRT
S="$R/_wip/arm-sw-fea3"
for c in G90_fine HALFK31_fine; do
  until [ "$(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -ge 14 ]; do sleep 60; done
  for t in 1 2; do fin "$S"; ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$D" timeout 3600 python cad/scripts/fea/organic_fea.py $c >> cad/_sim/$D/run.log 2>&1; fin "$S"; ls cad/_sim/$D/*_$c.npz >/dev/null 2>&1 && { echo "$c OK" >> cad/_sim/$D/run.log; break; }; echo "$c try $t failed" >> cad/_sim/$D/run.log; sleep 60; done
done
echo CHAIN_DONE
