#!/bin/bash
# Rebuild the 0.1 gap R1d variant with 5-segment taper ramps, its pad hub-seat model, a capped mesh-only check, then the STOP_0.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_fix.log
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_TAPER=1 ARM_TAPER_SEGS=5 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export ARM_WIP_TAG=_tg01 ARM_FLANK_GAP=0.1 ARM_RIB_PROUD=0 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_tg01.SLDPRT HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_PADS=1 HS_PAD_E=0.05
echo "start $(date)" >> $L
bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_tg01_seg5.log
grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED" >> $L; exit 1; }
echo "BUILT arm $(grep -c 'RIDGE_TAPER.: cut' cad/_wip/r1d_build_tg01_seg5.log) taper cuts" >> $L
cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_tg01.SLDPRT cad/_sim/ua2/; sleep 60
rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_tg01p.SLDPRT
HS_MODEL=UA_HUBSEAT_r1d_tg01p.SLDPRT ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_tg01p_seg5.log 2>&1; fin "$R/_wip/arm-sw-hub"
grep -q "  pads True" cad/_wip/r1d_hub_tg01p_seg5.log && echo "BUILT tg01p (pads in)" >> $L || { echo "HUB_BUILD_FAILED" >> $L; exit 1; }
sleep 60
# capped mesh-only check at the working mesh (0.5 mm on ridge + groove)
D=cad/_sim/r1d_mt_seg5; rm -rf $D; mkdir -p $D; cp cad/_sim/ua2/UA_HUBSEAT_r1d_tg01p.SLDPRT $D/; S="$R/_wip/arm-sw-fea"
FEA_MESH_ONLY=1 HS_SEAT_MESH=0.5 HS_MODEL=UA_HUBSEAT_r1d_tg01p.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1d_mt_seg5" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine >> $D/run.log 2>&1 &
P=$!; t=0; while kill -0 $P 2>/dev/null && [ $t -lt 900 ]; do sleep 10; t=$((t+10)); done
if kill -0 $P 2>/dev/null; then kill $P; sleep 5; fin "$S"; echo "MESH_CAP seg5 still not meshed in 15 min" >> $L; exit 1; fi
fin "$S"; echo "MESH_OK $(grep -E ' mesh ' $D/run.log | tail -1)" >> $L
sleep 180
R1D_IGNORE_HOLD=1 bash cad/scripts/fea/r1c/r1d_chain4.sh "tg01p:HS_STOP_0_fine:r1d7_tg01p_stop:arm-sw-fea:0:0.5"
echo "FIX_DONE $(date)" >> $L
