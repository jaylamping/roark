#!/bin/bash
# R1e: 0 gap STOP_0 and STOP_124 with the lug-root refinement that fits the solver memory (2026-11-12). Tries: 0.3 on the
# fillet faces at global 4.0 was 458 k nodes and the memory watch stopped it, so a mesh-only probe picks the first of
# "0.4,20,5.0" / "0.5,20,5.0" (root size, max face area, global size) under NMAX nodes. Runs after the shim-body cases.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
NMAX=${NMAX:-410000}
until grep -q "R1E_SHIM_DONE" $L; do sleep 30; done
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1
S="$R/_wip/arm-sw-fea"
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
sleep 180
CH=""
for spec in "0.4,20,5.0" "0.5,20,5.0"; do
  hung; waitfree
  P=cad/_sim/r1e_g00_probe2; rm -rf $P; mkdir -p $P; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg00zi.SLDPRT $P/
  FEA_MESH_ONLY=1 HS_ROOT_MESH=$spec HS_MODEL=UA_HUBSEAT_r1d_ringg00zi.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1e_g00_probe2" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $P/run.log 2>&1; fin
  n=$(grep -oE "mesh 0 nodes [0-9]+" $P/run.log | grep -oE "[0-9]+$")
  echo "PROBE r1e g00 root $spec: nodes ${n:-?} $(grep -E ' control ' $P/run.log | tr '\n' ' ' | cut -c1-160)" >> $L
  sleep 180
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then CH=$spec; break; fi
done
[ -z "$CH" ] && { echo "ROOT_REFINE: nothing under $NMAX nodes; running the stop cases unrefined (0.8)" >> $L; }
for ff in r1e_g00_stop_b r1e_g00_stop124_b; do
  if [ -n "$CH" ]; then echo "$CH" > cad/_wip/hs_root_mesh/$ff.txt; else rm -f cad/_wip/hs_root_mesh/$ff.txt; fi
done
solve() {
  hung
  FOLDER=$1 MTAG=ringg00zi CASE=$2 PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 root ${CH:-none} $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
solve r1e_g00_stop_b HS_STOP_0_fine
solve r1e_g00_stop124_b HS_STOP_124_fine
echo "R1E_STOPB_DONE $(date)" >> $L
