#!/bin/bash
# R1e shim-body check (2026-11-12): the G90 shim model shows axial tension across the shim / arm end face (bonded-like). Re-solve
# the saved study r1e_s70_g90 as it is with nodal displacements exported (FEA_SAVE_DISP), to see whether the ring lifts off the
# arm on the tension side (contact working) or moves with it (bonded). Copy of the folder, so the reported result stays as it is.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
S="$R/_wip/arm-sw-verify"      # its own session folder (the first try shared arm-sw-fea with a probe)
until grep -q "R1E_STOPB_DONE" $L; do sleep 30; done
sleep 180
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
D=cad/_sim/r1e_s70_g90_disp; rm -rf $D; mkdir -p $D
cp cad/_sim/r1e_s70_g90/UA_HUBSEAT_r1d_ringg00s70i.SLDPRT cad/_sim/r1e_s70_g90/HUB_GROOVE_r1d.STL $D/
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_PAD_E=0.05 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 R1C_RING=1 CAD_WRITER='upper-arm-r1:2bcc415b'
export HS_INSERT_MODEL=1 HS_SHIM=0.70 HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8
echo "START r1e_s70_g90_disp $(date +%H:%M)" >> $L
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
FEA_EXISTING_STUDY=r1e_s70_g90 FEA_SAVE_DISP=1 HS_MODEL=UA_HUBSEAT_r1d_ringg00s70i.SLDPRT ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ringg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1e_s70_g90_disp" python cad/scripts/fea/organic_fea.py HS_G90_fine > $D/run.log 2>&1 &
cpid=$!
while kill -0 $cpid 2>/dev/null; do      # memory watch: clean stop at 12 GB used (free-RAM drop) or under 4 GB free
  sleep 60; fr=$(free); pid=$(awk '{print $1}' "$S/.sw_instance_pid" 2>/dev/null)
  mb=$( [ -n "$pid" ] && powershell -NoProfile -c "[int]((Get-Process -Id $pid -ErrorAction SilentlyContinue).PrivateMemorySize64/1MB)" )
  if [ "${mb:-0}" -gt 12288 ] || [ "${fr:-99999}" -lt 4096 ]; then echo "MEM_STOP r1e_s70_g90_disp ours $mb MB free $fr" >> $L; break; fi
done
(cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish(); print('ended')") >> $L 2>&1
wait $cpid 2>/dev/null
echo "DISP_DONE r1e_s70_g90_disp $(date +%H:%M) $(grep -E 'existing study|solve |displacements' $D/run.log | tr '\n' ' ' | cut -c1-240)" >> $L
