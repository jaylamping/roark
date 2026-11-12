#!/bin/bash
# Re-run the saved ring STOP_0 study (Intel direct sparse) only to capture the .OUT that SolidWorks deletes on failure.
cd /j/code/roark-wt/left-arm-organic
D=cad/_sim/r1d8_ring_saved; B=cad/_wip/r1d_ring_err24; mkdir -p $B; rm -f $B/.stop
( while [ ! -f $B/.stop ]; do for f in $D/*.OUT $D/*.BMC $D/*BenchMark*.txt $D/*.ERR $D/*.err; do [ -f "$f" ] && cp -p "$f" $B/ 2>/dev/null; done; sleep 2; done ) &
cpid=$!
bash cad/scripts/fea/r1c/r1d_ring_ds_solve.sh saved > cad/_wip/r1d_ring_ds2.out 2>&1
touch $B/.stop; wait $cpid
echo "DIAG_DONE $(date +%H:%M) $(ls $B | tr '\n' ' ')" >> cad/_wip/r1d_ring_ds.log
