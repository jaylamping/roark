#!/bin/bash
# run a SolidWorks job; when the launch gave up behind another session's solve ("did not answer for 300 s"), run it again
log=$1; shift
for n in 1 2 3 4 5 6; do
  "$@" > "$log" 2>&1
  if grep -qE "did not answer for 300 s|never registered in the ROT" "$log"; then echo "launch $n waited out a busy instance: $(date +%T)" >> launch_waits.log; else break; fi
done
