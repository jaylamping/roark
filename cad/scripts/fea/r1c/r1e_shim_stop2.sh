#!/bin/bash
# R1e shim-body STOP_0, second try (2026-11-12). The first used 0.3 on the lug roots at global 4.0: 1.19 M nodes, stuck at the
# start of the factorisation and ended by hand. This one probes "0.4,20,5.0" / "0.5,20,5.0" / "0.6,20,5.5" (root size, max face
# area, global size) on the shim model and solves with the first under NMAX nodes. Displacements saved (contact-gap check).
# Runs after the 0 gap stop re-runs.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
NMAX=${NMAX:-410000}
until grep -q "R1E_STOPB_DONE" $L; do sleep 30; done
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1 HS_SHIM=0.70
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1 R1C_SHIM=0.70
S="$R/_wip/arm-sw-fea"
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
sleep 180
CH=""
for spec in "0.4,20,5.0" "0.5,20,5.0" "0.6,20,5.5"; do
  hung; waitfree
  P=cad/_sim/r1e_s70_probe; rm -rf $P; mkdir -p $P; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg00s70i.SLDPRT $P/
  FEA_MESH_ONLY=1 HS_ROOT_MESH=$spec HS_MODEL=UA_HUBSEAT_r1d_ringg00s70i.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/r1e_s70_probe" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $P/run.log 2>&1; fin
  n=$(grep -oE "mesh 0 nodes [0-9]+" $P/run.log | grep -oE "[0-9]+$")
  echo "PROBE r1e s70 root $spec: nodes ${n:-?}" >> $L
  sleep 180
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then CH=$spec; break; fi
done
[ -z "$CH" ] && { echo "ROOT_REFINE s70: nothing under $NMAX nodes; not solving" >> $L; exit 1; }
echo "$CH" > cad/_wip/hs_root_mesh/r1e_s70_stop2.txt
hung
FOLDER=r1e_s70_stop2 MTAG=ringg00s70i CASE=HS_STOP_0_fine PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 FEA_SAVE_DISP=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
echo "CASE_DONE r1e_s70_stop2 root $CH $(date +%H:%M) $(grep -E " control |mesh 0|shim contact|displacements" cad/_sim/r1e_s70_stop2/run.log | tr '\n' ' ' | cut -c1-260) $(grep -E "^(SOLVED|SOLVE_FAILED) r1e_s70_stop2" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
echo "R1E_SHIM_STOP2_DONE $(date)" >> $L
