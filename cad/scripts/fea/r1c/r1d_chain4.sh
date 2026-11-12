#!/bin/bash
# R1d solves after the holly-pc hang fixes (2026-11-12): no hard timeout around the client (it must never be killed mid-readback),
# a HUNG_PID file in any of our instance folders stops the chain, clean closes only (swlib.finish raises on a timed-out close).
# Usage: r1d_chain4.sh "tag:case:folder:instance:soft[:mesh]" ...   (run in order, one at a time)
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_chain4.log
RV=cad/reviews/upper-arm/20261111_r1c-delta/r1d
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 CAD_WRITER='upper-arm-r1:2bcc415b'
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1; }
push() { until mkdir cad/_wip/.r1d_git_lock 2>/dev/null; do sleep 5; done; git add $RV >/dev/null 2>&1; git commit -q -m "$1" >/dev/null 2>&1; for t in 1 2 3; do git push -q origin left-arm-organic-r1 >/dev/null 2>&1 && break; sleep 10; done; rmdir cad/_wip/.r1d_git_lock; }
echo "start $(date)" >> $L
for job in "$@"; do
  IFS=: read tag case folder inst soft mesh <<< "$job"
  D=cad/_sim/$folder
  if ls $D/org16_$case.npz >/dev/null 2>&1; then echo "SKIP $folder" >> $L; continue; fi
  if [ -f cad/_wip/R1D_HOLD ] && [ "$R1D_IGNORE_HOLD" != 1 ]; then echo "HELD: cad/_wip/R1D_HOLD present, not starting $folder" >> $L; break; fi
  if hung; then echo "STOPPED: HUNG_PID present ($(cat cad/_wip/arm-sw*/HUNG_PID 2>/dev/null | tr '\n' ' '))" >> $L; break; fi
  until [ "$(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -ge 10 ]; do sleep 60; done
  rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_$tag.SLDPRT $D/; cp cad/_sim/ua2/HUB_GROOVE_r1d.STL $D/
  S="$R/_wip/$inst"; echo "START $folder $(date +%H:%M)" >> $L
  HS_SOFT_SPRING=$soft HS_SEAT_MESH=${mesh:-0.35} HS_MODEL=UA_HUBSEAT_r1d_$tag.SLDPRT ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_$tag.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$folder" python cad/scripts/fea/organic_fea.py $case >> $D/run.log 2>&1
  fin "$S"
  if ls $D/org16_$case.npz >/dev/null 2>&1; then
    python cad/scripts/fea/r1c/hub_r1c.py $D/org16_$case.npz $D/HUB_GROOVE_r1d.STL > $D/post.txt 2>&1
    cp $D/org16_$case.npz.r1c.json $RV/$folder.json; cp $D/post.txt $RV/$folder.post.txt; grep -E "mesh 0|solve |soft|reaction|displacement" $D/run.log | tail -5 >> $RV/$folder.post.txt
    echo "SOLVED $folder $(date +%H:%M) $(grep -E 'mesh 0' $D/run.log | tail -1) $(grep SANITY $D/post.txt)" >> $L
    push "cad: R1d FEA result $folder"
  else echo "SOLVE_FAILED $folder $(date +%H:%M) $(grep -E 'solve |never registered|Error' $D/run.log | tail -1 | cut -c1-120)" >> $L; fi
done
echo "CHAIN_DONE $(date)" >> $L
