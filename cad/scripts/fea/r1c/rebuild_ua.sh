#!/bin/bash
# one job per fresh SolidWorks instance; retry once
cd /j/code/roark-wt/left-arm-organic
export QTAG=v26 ARM_SW_DIR='J:\code\roark-wt\left-arm-organic\cad\_wip\arm-sw'
L=cad/_wip/organic-arm/rebuild_ua.log
: > $L
run() {  # script job
  for t in 1 2; do
    (cd cad/scripts/arm && timeout 1800 python $1 $2) >> $L 2>&1; rc=$?
    (cd cad/scripts/arm && timeout 300 python -c "from swlib import finish; finish()") >> $L 2>&1
    echo "$2 try $t rc $rc" >> $L
    [ $rc -eq 0 ] && return 0
  done
  return 1
}
J="${@:-master:upper parts:ring parts:front parts:back parts:fea_upper}"
for j in $J; do
  s=${j%%:*}; k=${j#*:}
  [ $s = master ] && f=organic_master.py || f=organic_parts.py
  run $f $k || { echo "STOP at $k" >> $L; break; }
done
echo DONE >> $L
