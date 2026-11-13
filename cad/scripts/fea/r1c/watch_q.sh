#!/bin/bash
# Wake-up helper: exits when the queue logs a new milestone (BUILT / SOLVED / SOLVE_FAILED / MEM_STOP / STOP / *_DONE / POST_DONE)
# or when no job has started within MAXWAIT seconds, or (MINWARN set) when free memory drops under MINWARN MB while waiting (default 2700 = 45 min, the memory-gate report rule). Prints the new lines.
cd /j/code/roark-wt/left-arm-organic
L1=cad/_wip/r1d_combined.log; L2=cad/_wip/r1d_ring_ds.log
n1=$(wc -l < $L1); n2=$(wc -l < $L2); t0=$(date +%s)
pat='BUILT model|^SOLVED|SOLVE_FAILED|MEM_STOP|STOP:|STOPPED|_DONE |POST_DONE'
[ "$WATCH_START" = 1 ] && pat="$pat|^START"
while true; do
  sleep 30
  [ "$WATCH_START" = 1 ] && [ -f /c/joe/.fea_solve.lock ] && grep -q "^left-arm-organic" /c/joe/.fea_solve.lock && { echo "queue holds the shared solve lock (launching): $(cat /c/joe/.fea_solve.lock)"; exit 0; }
  new=$( (tail -n +$((n1 + 1)) $L1; tail -n +$((n2 + 1)) $L2) 2>/dev/null)
  if echo "$new" | grep -qE "$pat"; then echo "$new" | cut -c1-260; exit 0; fi
  fr=$(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)')
  if [ -n "$MINWARN" ] && [ "${fr:-99999}" -lt "$MINWARN" ] && ! echo "$new" | grep -q "^START"; then echo "FREE MEMORY LOW: $fr MB (under $MINWARN) with no job of ours running"; exit 3; fi
  if echo "$new" | grep -q "^START"; then t0=$(date +%s); n2=$(wc -l < $L2); fi
  if [ $(( $(date +%s) - t0 )) -gt ${MAXWAIT:-2700} ]; then echo "WAITED ${MAXWAIT:-2700} s with no start; free $(powershell -NoProfile -c '[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)') MB"; echo "$new" | tail -5; exit 2; fi
done
