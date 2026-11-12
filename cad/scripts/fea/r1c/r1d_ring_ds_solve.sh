#!/bin/bash
# Ring 0.1 gap STOP_0 at 0.8 mm (pads E 0.5) with direct sparse.
#   mode "saved": solve the study saved by r1d_ring_saved.sh as it is (solver set by hand in the GUI, or by the macro)
#   mode "new":   a new study (Simulation default solver set to direct sparse in the GUI)
# Memory watch (coordinator, 2026-11-12): stop cleanly if our instance's processes pass 12 GB or the machine drops under 4 GB free.
# Clean stop = stop the client, then end our session (swlib.finish). No force-kill of anything else.
mode=${1:-saved}
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring_ds.log
RV=cad/reviews/upper-arm/20261111_r1c-delta/r1d
export ARM_R1C=1 ARM_R1D=1 HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 R1C_RING=1 CAD_WRITER='upper-arm-r1:2bcc415b'
S="$R/_wip/arm-sw-fea"
until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done
ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
free() { powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)'; }
until [ "$(free)" -ge 16000 ]; do sleep 60; done
if [ "$mode" = saved ]; then
  D=cad/_sim/r1d8_ring_saved; folder=r1d8_ring_saved
  ENVX="FEA_EXISTING_STUDY=RING_G01_STOP0_DS HS_MODEL=UA_HUBSEAT_r1d_ringg01p_ds.SLDPRT"
else
  folder=r1d8_ringg01p_stop_ds_new; D=cad/_sim/$folder; rm -rf $D; mkdir -p $D
  cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01p.SLDPRT $D/; cp cad/_sim/ua2/HUB_GROOVE_RING.STL $D/HUB_GROOVE_r1d.STL
  ENVX="HS_MODEL=UA_HUBSEAT_r1d_ringg01p.SLDPRT"
fi
echo "START $folder ($mode) $(date +%H:%M) free $(free) MB" >> $L
env $ENVX ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ringg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/$folder" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine >> $D/run.log 2>&1 &
cpid=$!
peak=0
while kill -0 $cpid 2>/dev/null; do
  sleep 60
  pid=$(awk '{print $1}' "$S/.sw_instance_pid" 2>/dev/null)
  [ -z "$pid" ] && continue
  # our instance and every process under it (the solver may run as a child), private MB
  mb=$(powershell -NoProfile -c "\$ps=Get-CimInstance Win32_Process; \$ids=@($pid); do { \$n=\$ids.Count; \$ids=@(\$ids + (\$ps | ? { \$ids -contains \$_.ParentProcessId -and \$ids -notcontains \$_.ProcessId } | % ProcessId)) } while (\$ids.Count -ne \$n); [int]((\$ps | ? { \$ids -contains \$_.ProcessId } | Measure-Object PrivatePageCount -Sum).Sum/1MB)")
  fr=$(free); [ "${mb:-0}" -gt $peak ] && peak=$mb
  echo "mem $(date +%H:%M) ours ${mb} MB free ${fr} MB $(tail -c 300 $D/run.log | tr '\n' ' ' | tail -c 120)" >> cad/_wip/r1d_ring_ds_mem.log
  if [ "${mb:-0}" -gt 12288 ] || [ "${fr:-99999}" -lt 4096 ]; then
    echo "MEM_STOP $(date +%H:%M) ours ${mb} MB free ${fr} MB: stopping the client, then ending our instance" >> $L
    kill $cpid 2>/dev/null; sleep 5
    break
  fi
done
wait $cpid 2>/dev/null
(cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish(); print('ended')") >> $L 2>&1
echo "peak ours ${peak} MB; solver in .OUT: $(grep -h -m1 'SOLVER TYPE' $D/*.OUT 2>/dev/null | tr -s ' ' | tail -c 40)" >> $L
sleep 180
if ls $D/org16_HS_STOP_0_fine.npz >/dev/null 2>&1; then
  python cad/scripts/fea/r1c/hub_r1c.py $D/org16_HS_STOP_0_fine.npz $D/HUB_GROOVE_r1d.STL > $D/post.txt 2>&1
  cp $D/org16_HS_STOP_0_fine.npz.r1c.json $RV/$folder.json; cp $D/post.txt $RV/$folder.post.txt; grep -E "mesh|solve |reaction|displacement|solver" $D/run.log | tail -8 >> $RV/$folder.post.txt
  echo "SOLVED $folder $(date +%H:%M) $(grep -E 'solve ' $D/run.log | tail -1) $(grep SANITY $D/post.txt)" >> $L
  until mkdir cad/_wip/.r1d_git_lock 2>/dev/null; do sleep 5; done
  git add $RV >/dev/null 2>&1; git commit -q -m "cad: R1d ring STOP_0 direct sparse result ($folder)" >/dev/null 2>&1
  for t in 1 2 3; do git push -q origin left-arm-organic-r1 >/dev/null 2>&1 && break; sleep 10; done; rmdir cad/_wip/.r1d_git_lock
else
  echo "SOLVE_FAILED $folder $(date +%H:%M) $(grep -E 'solve |never registered|Error|existing study' $D/run.log | tail -2 | tr '\n' ' ' | cut -c1-200)" >> $L
fi
