#!/bin/bash
# Ring variant FEA models for the rest of the queue (2026-11-12), same recipe as the 0.1 gap ring model (r1d_ring.sh) and the
# tapered set (r1d_tapered_all.sh): nominal = 0.1 flank gap with ribs 0.1 proud (the FEA nominal), g02 = 0.2 gap, no ribs.
# Both reuse the ring hub (HUB_GROOVE_RING.SLDPRT) and carry the four soft pads (modulus set per case at study time).
# One SolidWorks job at a time, 3-minute gaps, clean closes.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_ring_builds.log
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$1" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
export ARM_R1C=1 ARM_R1D=1 ARM_SEAT_RIBS=0 ARM_RIDGE_RING=1 ARM_RIDGE_TAPER=0 SW_PART_TEMPLATE='C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot'
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_HUB_FILE=HUB_GROOVE_RING.SLDPRT HS_PADS=1 HS_REUSE_HUB=1
export CAD_WRITER='upper-arm-r1:2bcc415b'
build() {  # tag gap rib
  ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED (HUNG_PID) before $1" >> $L; exit 1; }
  waitfree
  export ARM_WIP_TAG=_$1 ARM_FLANK_GAP=$2 ARM_RIB_PROUD=$3 ARM_FEA_NAME=UA_ORGANIC_BONDED_v32_$1.SLDPRT HS_MODEL=UA_HUBSEAT_r1d_${1}p.SLDPRT
  bash cad/scripts/fea/r1c/rebuild_ua.sh "master:upper parts:fea_upper"; cp -p cad/_wip/organic-arm/rebuild_ua.log cad/_wip/r1d_build_$1.log
  grep -q "STOP at" cad/_wip/organic-arm/rebuild_ua.log && { echo "BUILD_FAILED $1" >> $L; exit 1; }
  cp -p cad/_sim/upper-arm/UA_ORGANIC_BONDED_v32_$1.SLDPRT cad/_sim/ua2/
  sleep 180; waitfree
  rm -f cad/_sim/ua2/UA_HUBSEAT_r1d_${1}p.SLDPRT
  ARM_SW_DIR="$R/_wip/arm-sw-hub" ARM_FEA_DIR="$R/_sim/ua2" python cad/scripts/fea/hub_seat.py build > cad/_wip/r1d_hub_${1}p.log 2>&1; fin "$R/_wip/arm-sw-hub"
  grep -q "  pads True" cad/_wip/r1d_hub_${1}p.log && ls cad/_sim/ua2/UA_HUBSEAT_r1d_${1}p.SLDPRT >/dev/null 2>&1 || { echo "HUB_BUILD_FAILED $1" >> $L; exit 1; }
  echo "BUILT $1 (gap $2, ribs $3) $(date +%H:%M) $(grep -E 'SEAT_RIDGE_RING|SEAT_FLANK_RIB' cad/_wip/r1d_build_$1.log | tail -2 | tr '\n' ' ' | cut -c1-160)" >> $L
  sleep 180
}
echo "start $(date)" >> $L
for job in "$@"; do IFS=: read tag gap rib <<< "$job"; build $tag $gap $rib; done
echo "BUILDS_DONE $(date +%H:%M)" >> $L
