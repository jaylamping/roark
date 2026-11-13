#!/bin/bash
# Stop a job cleanly if its mesh comes out with a body missing (node count under MINN): 2026-11-13, r1g3 meshed to 194,600
# against 397,709 for the same controls on r1g2 (the hub's ~210 k nodes missing).
cd /j/code/roark-wt/left-arm-organic
F=$1; MINN=${MINN:-300000}; L=cad/_wip/r1d_combined.log
# (2026-11-13) only a run.log written after this guard started counts: the folder still holds the previous run's log until the
# solve script clears it, and reading that one ended nothing but logged a false failure (r1g6_stop124 17:01)
T0=$(date +%s)
until [ -f cad/_sim/$F/run.log ] && [ $(stat -c %Y cad/_sim/$F/run.log) -ge $T0 ] && grep -qE "mesh 0 nodes [0-9]+" cad/_sim/$F/run.log 2>/dev/null; do sleep 5; done
n=$(grep -oE "mesh 0 nodes [0-9]+" cad/_sim/$F/run.log | grep -oE "[0-9]+$")
if [ "$n" -lt "$MINN" ]; then
  echo "MESH_GUARD $F: $n nodes (< $MINN, a body likely unmeshed): ending its session before the solve result is used" >> $L
  (cd cad/scripts/arm && ARM_SW_DIR="J:/code/roark-wt/left-arm-organic/cad/_wip/arm-sw-job-$F" python -c "from swlib import finish; finish(); print('ended $F')") >> $L 2>&1
else
  echo "MESH_GUARD $F: $n nodes OK" >> $L
fi
