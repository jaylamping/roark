#!/bin/bash
# Ring 0.1 gap STOP_0 at 0.8 mm (pads E 0.5): build the study, mesh it and save it in its own copy of the model, for the solver
# to be set by hand in the GUI (StaticStudyOptions puts fail from our scripts, 2026-11-12). One in-process try first: a plain-text
# SolidWorks Basic macro run inside our instance sets SolverType 1 (direct sparse) and the model is saved again.
# Waits for the ring print build to finish and for a free instance, then leaves the 3-minute gap.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring_saved.log
until grep -qE "RING_PRINT_DONE|BUILD_FAILED" cad/_wip/r1d_ring_print.log 2>/dev/null; do sleep 30; done
until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
sleep 180
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
echo "start $(date)  free $(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)') MB" >> $L
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600
D=cad/_sim/r1d8_ring_saved; rm -rf $D; mkdir -p $D
cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01p.SLDPRT $D/UA_HUBSEAT_r1d_ringg01p_ds.SLDPRT; cp cad/_sim/ua2/HUB_GROOVE_RING.STL $D/HUB_GROOVE_r1d.STL
S="$R/_wip/arm-sw-fea"
FEA_MESH_ONLY=1 FEA_SAVE_STUDY=1 FEA_STUDY_NAME=RING_G01_STOP0_DS FEA_SOLVER_MACRO=1 HS_MODEL=UA_HUBSEAT_r1d_ringg01p_ds.SLDPRT ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ringg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1d8_ring_saved" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $D/run.log 2>&1
(cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish(); print('ended')") >> $L 2>&1
echo "SAVED $(date +%H:%M) $(grep -E 'saved study|solver macro|solver reads|saved again| mesh ' $D/run.log | tr -s ' ' | tr '\n' ' ' | cut -c1-600)" >> $L
