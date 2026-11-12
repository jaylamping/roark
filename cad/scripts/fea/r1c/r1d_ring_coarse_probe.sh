#!/bin/bash
# Mesh-only: node counts of the ring STOP_0 model with a coarser global size (seat control 0.8 kept), for direct sparse memory.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad; L=cad/_wip/r1d_ring_coarse.log; S="$R/_wip/arm-sw-fea"
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 FEA_MESH_ONLY=1
sleep 180
for el in 3.0 4.0; do
  until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
  D=cad/_sim/r1d_cp_$el; rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01p.SLDPRT $D/
  HS_GLOBAL_EL=$el HS_MODEL=UA_HUBSEAT_r1d_ringg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1d_cp_$el" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $D/run.log 2>&1
  (cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish()") >> $L 2>&1
  echo "global $el: $(grep -E ' mesh ' $D/run.log | tail -1)" >> $L
  sleep 180
done
echo "COARSE_DONE $(date +%H:%M)" >> $L
