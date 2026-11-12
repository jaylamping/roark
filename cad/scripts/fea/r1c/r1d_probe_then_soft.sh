#!/bin/bash
# Probe every 5 min for a SolidWorks instance that registers; when one does, run the soft-spring gap STOP_0 chain (r1d_chain3.sh).
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_probe.log
P=J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-probe
while true; do
  if ARM_SW_DIR=$P timeout 330 python cad/scripts/fea/r1c/open_test.py 'J:\code\roark-wt\left-arm-organic\cad\_sim\ua2\HS_BOLTS.SLDPRT' > cad/_wip/r1d_probe_last.txt 2>&1 && grep -q "open True" cad/_wip/r1d_probe_last.txt; then
    echo "LAUNCH_OK $(date +%H:%M)" >> $L
    (cd cad/scripts/arm && ARM_SW_DIR=$P timeout 200 python -c "from swlib import finish; finish()") >/dev/null 2>&1
    bash cad/scripts/fea/r1c/r1d_chain3.sh
    echo "SOFT_CHAIN_RETURNED $(date +%H:%M)" >> $L
    break
  fi
  echo "LAUNCH_FAIL $(date +%H:%M) $(tail -1 cad/_wip/r1d_probe_last.txt | cut -c1-90)" >> $L
  sleep 300
done
