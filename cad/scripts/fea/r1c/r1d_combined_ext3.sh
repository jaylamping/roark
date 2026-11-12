#!/bin/bash
# Combined pass, last case (2026-11-12, coordinator): 0.2 gap STOP_0 refined, 0.3 mm on the lug-root fillets and, if it fits in
# memory, on the groove band too (groove bottom, 45 flank, spigot core faces: full rings, both bodies). Mesh-only probes pick the
# groove size: 0.3 if the model stays under NMAX nodes, else 0.5, else none. Waits for EXT2_DONE.
cd /j/code/roark-wt/left-arm-organic
R=J:/code/roark-wt/left-arm-organic/cad
L=cad/_wip/r1d_combined.log
NMAX=${NMAX:-480000}
until grep -q "EXT2_DONE" $L; do sleep 30; done
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_REUSE_HUB=1 HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1
S="$R/_wip/arm-sw-fea"
fin() { (cd cad/scripts/arm && ARM_SW_DIR="$S" python -c "from swlib import finish; finish()") >> $L 2>&1; }
waitfree() { until ! python "C:/joe/code/roark-wt/sw-hang-fix/tools/solidworks/sw_instance.py" --status 2>/dev/null | grep -q "busy"; do sleep 30; done; }
F=r1d11_g02_stop_ref
mkdir -p cad/_wip/hs_root_mesh cad/_wip/hs_groove_mesh
echo 0.3 > cad/_wip/hs_root_mesh/$F.txt; echo 0.3 > cad/_wip/hs_root_mesh/r1d11_g01_stop_ref.txt
sleep 180
G=""
for g in 0.3 0.5; do
  ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
  waitfree
  P=cad/_sim/${F}_probe; rm -rf $P; mkdir -p $P; cp cad/_sim/ua2/UA_HUBSEAT_r1d_ringg02zi.SLDPRT $P/
  FEA_MESH_ONLY=1 HS_ROOT_MESH=0.3 HS_GROOVE_MESH=$g HS_MODEL=UA_HUBSEAT_r1d_ringg02zi.SLDPRT ARM_SW_DIR="$S" ARM_FEA_DIR="$R/_sim/${F}_probe" python cad/scripts/fea/organic_fea.py HS_STOP_0_fine > $P/run.log 2>&1; fin
  n=$(grep -oE "mesh 0 nodes [0-9]+" $P/run.log | grep -oE "[0-9]+$")
  echo "PROBE $F groove $g: nodes ${n:-?} $(grep -E ' control ' $P/run.log | tr '\n' ' ' | cut -c1-200)" >> $L
  sleep 180
  if [ -n "$n" ] && [ "$n" -le "$NMAX" ]; then G=$g; break; fi
done
for ff in $F r1d11_g01_stop_ref; do
  if [ -n "$G" ]; then echo $G > cad/_wip/hs_groove_mesh/$ff.txt; else rm -f cad/_wip/hs_groove_mesh/$ff.txt; fi
done
[ -z "$G" ] && echo "GROOVE_REFINE_SKIPPED (over $NMAX nodes at 0.3 and 0.5)" >> $L
for job in "$F:ringg02zi" "r1d11_g01_stop_ref:ringg01zi"; do
  IFS=: read ff mt <<< "$job"
  ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }
  FOLDER=$ff MTAG=$mt CASE=HS_STOP_0_fine PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $ff groove ${G:-none} root 0.3 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$ff/run.log | tr '
' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $ff" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
done
echo "EXT3_DONE $(date)" >> $L
