#!/bin/bash
# R1e YAW_17 (coordinator, 2026-11-12): the RS02's 17 N.m peak about the hub (yaw) axis, applied to the arm through the RS02 bore
# (remote load, as G90), hub top fixed. The full ring carries no torque about the hub axis, so it all goes through the two lugs.
# R1e 0 gap model with the shim lumped (ringg00zi), 0.8 on posts / lugs / fins, 0.5 on the lug roots at global 5.0 (the probe
# that fits). Both signs: the joint is not symmetric in Z (front posts have the brass inserts, back posts clearance holes).
# Order: after the 0 gap STOP_0 now solving, ahead of STOP_124 and the shim-body STOP_0. The queued STOP_124 (r1e_g00_stop_b.sh)
# is stopped while it is only waiting (before it launches anything) and re-run here afterwards.
cd /j/code/roark-wt/left-arm-organic
L=cad/_wip/r1d_combined.log
mkdir -p cad/_wip/hs_root_mesh
for f in r1e_g00_yawp r1e_g00_yawm; do echo "0.5,20,5.0" > cad/_wip/hs_root_mesh/$f.txt; done
until grep -q "CASE_DONE r1e_g00_stop_b " $L; do sleep 2; done
# stop the queued chain: the stop_b script and a r1d_ring_ds_solve.sh it may have started (still in its wait: no START line yet)
for p in /proc/[0-9]*; do
  c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null)
  case "$c" in *r1e_g00_stop_b.sh*) kill ${p#/proc/} 2>/dev/null && echo "killed stop_b chain pid ${p#/proc/}: $c" >> $L ;; esac
done
sleep 1
if tail -3 $L | grep -q "START r1e_g00_stop124_b"; then echo "YAW: STOP_124 had already started; yaw waits for it" >> $L; fi
for p in /proc/[0-9]*; do
  c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null)
  case "$c" in *r1d_ring_ds_solve.sh*) grep -q "START r1e_g00_stop124_b" cad/_wip/r1d_ring_ds.log || { kill ${p#/proc/} 2>/dev/null && echo "killed waiting ds_solve pid ${p#/proc/}" >> $L; } ;; esac
done
echo "R1E_YAW start $(date +%H:%M)" >> $L
export CAD_WRITER='upper-arm-r1:2bcc415b' ARM_R1C=1 ARM_R1D=1
export HS_GROOVE=1 HS_BOLTED=1 HS_ROUNDS=1 HS_LUG_FILLET=1.0 HS_GROOVE_R45=1.0 HS_REVCP=1 HS_FILL=1 HS_FILL_R0=23.0 HS_GROOVE_FULL=1 HS_PADS=1 HS_REUSE_HUB=1 HS_INSERT_MODEL=1
export HS_HUB_FILE=HUB_RING_ZF.SLDPRT HS_PAD_E=0.5 HS_SEAT_MESH=0.8 HS_SEAT_MESH_AMAX=600 HS_POST_MESH=0.8 R1C_RING=1 R1C_INSERTS=1
hung() { ls cad/_wip/arm-sw*/HUNG_PID >/dev/null 2>&1 && { echo "STOPPED: HUNG_PID present" >> $L; exit 1; }; }
solve() {
  hung
  FOLDER=$1 MTAG=ringg00zi CASE=$2 PADE=0.5 HUBFILE=HUB_RING_ZF.SLDPRT HUBSTL=HUB_RING_ZF.STL HS_GLOBAL_EL=4.0 HS_POST_MESH=0.8 DS_SOLVER=1 FEA_SAVE_DISP=1 bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh new
  echo "CASE_DONE $1 $(date +%H:%M) $(grep -E " control |mesh 0" cad/_sim/$1/run.log | tr '\n' ' ' | cut -c1-200) $(grep -E "^(SOLVED|SOLVE_FAILED) $1" cad/_wip/r1d_ring_ds.log | tail -1 | cut -c1-160)" >> $L
}
solve r1e_g00_yawp HS_LC2_fine
solve r1e_g00_yawm HS_LC2M_fine
echo "R1E_YAW_DONE $(date)" >> $L
# then the stop case the yaw cases jumped
grep -q "SOLVED r1e_g00_stop124_b" cad/_wip/r1d_ring_ds.log || { echo "0.5,20,5.0" > cad/_wip/hs_root_mesh/r1e_g00_stop124_b.txt; solve r1e_g00_stop124_b HS_STOP_124_fine; }
echo "R1E_STOPB_DONE $(date) (after the yaw cases)" >> $L
