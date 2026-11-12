#!/bin/bash
# Mesh-only diagnosis (2026-11-12): which R1d model ingredient stalls the mesher. Each test is capped at 15 min; on the cap the
# client is stopped and the session ended cleanly (end_session), then 3 min with no instance of ours alive.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_meshtest.log
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 FEA_MESH_ONLY=1
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
one() {  # label tag mesh
  D=cad/_sim/r1d_mt_$1; rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_$2.SLDPRT $D/
  S="$R/_wip/arm-sw-fea"; echo "START $1 $(date +%H:%M:%S)" >> $L
  HS_SEAT_MESH=$3 HS_MODEL=UA_HUBSEAT_r1d_$2.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1d_mt_$1" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine >> $D/run.log 2>&1 &
  P=$!; t=0
  while kill -0 $P 2>/dev/null && [ $t -lt 900 ]; do sleep 10; t=$((t+10)); done
  if kill -0 $P 2>/dev/null; then kill $P; sleep 5; echo "CAP $1 mesh not done in 15 min" >> $L; else echo "DONE $1 $(grep -E ' mesh ' $D/run.log | tail -1)" >> $L; fi
  fin "$S"; sleep 180
}
echo "start $(date)" >> $L
one tnom_m50 tnom 0.5
one tg01p_noctrl tg01p 0
echo "MESHTEST_DONE $(date +%H:%M)" >> $L
