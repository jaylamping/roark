#!/bin/bash
# R1d "ring": full-semicircle ridge per half (no taper), 0.1 flank gap, no ribs (gap case); mirror hub with a full-ring groove and
# full-ring r 23 fill (its own hub file); pads E 0.5 MPa; then the 0.1 gap STOP_0. One SolidWorks job at a time, gaps between.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring.log
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_WIP_TAG=_ring_g01 ARM_FLANK_GAP=0.1 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_ring_g01.SLDPRT
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_PADS=1 HS_PAD_E=0.5
export R1C_RING=1 HUB_STL_NAME=HUB_GROOVE_RING.STL
echo "start $(date)" >> $L
until [ -z "$(powershell -NoProfile -c "Get-CimInstance Win32_Process | ? { \$_.CommandLine -match 'rebuild_ua.sh' } | Select -First 1 -Expand ProcessId")" ]; do sleep 20; done
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_ring_g01.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED" >> $L; exit 1; }
echo "BUILT arm $(grep -E 'SEAT_RIDGE_RING' cad/_wip/r1d_build_ring_g01.log | tail -1)" >> $L
cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_ring_g01.SLDPRT cad/_sim/ua2/; sleep 60
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01p.SLDPRT cad/_sim/ua2/HUB_GROOVE_RING.SLDPRT
HS_MODEL=UA_HUBSEAT_r1d_ringg01p.SLDPRT ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_ringg01p.log 2>&1; fin "$R/_wip/arm-sw-hub"
grep -q "  pads True" cad/_wip/r1d_hub_ringg01p.log && echo "BUILT hub-seat ring (pads in) $(grep -E 'SPIGOT_GROOVE_RING|SPIGOT_FILL' cad/_wip/r1d_hub_ringg01p.log | tr '\n' ' ')" >> $L || { echo "HUB_BUILD_FAILED" >> $L; exit 1; }
sleep 60
D=cad/_sim/r1d_mt_ring; rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg01p.SLDPRT $D/; S="$R/_wip/arm-sw-fea"
FEA_MESH_ONLY=1 HS_SEAT_MESH=0.5 HS_MODEL=UA_HUBSEAT_r1d_ringg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1d_mt_ring" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine >> $D/run.log 2>&1 &
P=$!; t=0; while kill -0 $P 2>/dev/null && [ $t -lt 900 ]; do sleep 10; t=$((t+10)); done
if kill -0 $P 2>/dev/null; then kill $P; sleep 5; fin "$S"; echo "MESH_CAP ring not meshed in 15 min" >> $L; exit 1; fi
fin "$S"; echo "MESH_OK $(grep -E ' mesh ' $D/run.log | tail -1)" >> $L
sleep 180
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "ringg01p:HS_STOP_0_fine:r1d8_ringg01p_stop:arm-sw-fea:0:0.5"
echo "RING_DONE $(date)" >> $L
