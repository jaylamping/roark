#!/bin/bash
# Probe which StaticStudyOptions.SolverType values this SolidWorks accepts (mesh-only runs, ring model, 0.8 mm). One instance each.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_solver_probe.log
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_SEAT_MESH_AMAX=600 FEA_MESH_ONLY=1
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
for v in 2 3 4 1 0; do
  D=cad/_sim/r1d_sp_$v; rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01p.SLDPRT $D/
  FEA_SOLVER=$v HS_SEAT_MESH=0.8 HS_MODEL=UA_HUBSEAT_r1d_ringg01p.SLDPRT ARM_SW_DIR="$R/_wip/arm-sw-fea" ARM_FEA_DIR="$R/_sim/r1d_sp_$v" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $D/run.log 2>&1
  fin "$R/_wip/arm-sw-fea"
  echo "value $v: $(grep -E 'solver set|solver not set' $D/run.log | cut -c1-120) | $(grep -E ' mesh ' $D/run.log | tail -1 | cut -c1-60)" >> $L
done
echo "PROBE_DONE $(date +%H:%M)" >> $L
