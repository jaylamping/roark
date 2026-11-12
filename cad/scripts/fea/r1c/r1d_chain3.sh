#!/bin/bash
# R1d solves, resumable (skips cases with a result), detached from any Claude session. Mesh control 0.35 on ridge + groove faces only.
# Each result: post-processed, JSON copied to the review folder, committed and pushed (under a mkdir lock).
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_chain3.log
RV=cad/reviews/upper-arm/20261111_r1c-delta/r1d
mkdir -p $RV
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" timeout 300 python -c "from swlib import finish; finish()") >/dev/null 2>&1; }
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 CAD_WRITER='upper-arm-r1:2bcc415b'
push() {  # message
  until mkdir cad/_wip/.r1d_git_lock 2>/dev/null; do sleep 5; done
  git add $RV >/dev/null 2>&1; git commit -q -m "$1" >/dev/null 2>&1; for t in 1 2 3; do git push -q origin left-arm-organic-r1 >/dev/null 2>&1 && break; sleep 10; done
  rmdir cad/_wip/.r1d_git_lock
}
solve() {  # tag case folder instance [mesh]
  D=cad/_sim/$3
  if ls $D/org16_$2.npz >/dev/null 2>&1; then echo "SKIP $3 (has result)" >> $L; return 0; fi
  until [ "$(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)')" -ge 12 ]; do sleep 60; done
  rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_$1.SLDPRT $D/; cp cad/_sim/ua2/HUB_GROOVE_r1d.STL $D/
  S="$R/_wip/$4"; echo "START $3 $(date +%H:%M)" >> $L
  for t in 1 2; do fin "$S"; HS_SOFT_SPRING=${SOFT:-0} HS_SEAT_MESH=${5:-0.35} HS_MODEL=UA_HUBSEAT_r1d_$1.SLDPRT ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_$1.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$3" timeout 7200 python cad/scripts/fea/organic_fea.py $2 >> $D/run.log 2>&1; fin "$S"; ls $D/org16_$2.npz >/dev/null 2>&1 && break; sleep 60; done
  if ls $D/org16_$2.npz >/dev/null 2>&1; then
    timeout 3600 python cad/scripts/fea/r1c/hub_r1c.py $D/org16_$2.npz $D/HUB_GROOVE_r1d.STL > $D/post.txt 2>&1
    cp $D/org16_$2.npz.r1c.json $RV/$3.json; cp $D/post.txt $RV/$3.post.txt; grep -E "mesh 0|solve " $D/run.log | tail -2 >> $RV/$3.post.txt
    echo "SOLVED $3 $(date +%H:%M) $(grep -E 'mesh 0' $D/run.log | tail -1) $(grep SANITY $D/post.txt)" >> $L
    push "cad: R1d FEA result $3"
  else echo "SOLVE_FAILED $3 $(date +%H:%M) $(grep -E 'solve ' $D/run.log | tail -1)" >> $L; fi
}
echo "start $(date)" >> $L
# option A: soft springs, one gap case first (soft springs crashed SolidWorks here before; its own instance)
SOFT=1 solve g01 HS_STOP_0_fine r1d3_g01_stop_soft arm-sw-fea4
echo "CHAIN_DONE $(date)" >> $L
