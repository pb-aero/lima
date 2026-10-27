#!/usr/bin/env bash
# Finish routing with maze.py + rip-up until DRC shows nothing unconnected, KiCad closed.
# Each pass: route every open connection normally, then at most one rip-up (displaced nets re-route next pass).
# Rip history (RIP_HIST) makes repeat victims dearer, so two nets can't ping-pong forever. The best board seen
# (fewest unconnected, 0 errors) is kept and restored if the loop stalls for STALL passes.
# Usage: finish.sh <board> <scratch-dir> [max-passes]   (env passes through to maze.py: PLANE_NETS, MAZE_W, ...)
set -uo pipefail
B=$1; T=$2; MAX=${3:-40}; STALL=${STALL:-8}
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; D=$(cd "$(dirname "$0")" && pwd)
export RIP_HIST=$T/rip_hist.json; rm -f "$RIP_HIST"
best=999999; since=0
for i in $(seq 1 "$MAX"); do
  "$CLI" pcb drc --refill-zones -o "$T/finish.rpt" "$B" >/dev/null 2>&1
  n=$(grep -c '^\[unconnected_items\]' "$T/finish.rpt")
  e=$(grep -B3 '; error' "$T/finish.rpt" | grep '^\[' | grep -vc '^\[unconnected_items\]')
  echo "pass $i: unconnected $n, other errors $e"
  if [ "$e" -eq 0 ] && [ "$n" -lt "$best" ]; then best=$n; since=0; cp "$B" "$T/best.kicad_pcb"; else since=$((since + 1)); fi
  [ "$n" -eq 0 ] && break
  [ "$since" -ge "$STALL" ] && { echo "stalled $STALL passes"; break; }
  RIPUP=1 "$PY" -u "$D/maze.py" "$B" "$T/finish.rpt" 2>&1 | grep -E "rip-up|routed [0-9]+ of" | tail -3
  rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] && { echo "no rip-up possible"; break; }
  [ "$rc" -ne 3 ] && { echo "maze exit $rc"; break; }
done
"$CLI" pcb drc --refill-zones -o "$T/finish.rpt" "$B" >/dev/null 2>&1
n=$(grep -c '^\[unconnected_items\]' "$T/finish.rpt")
if [ -f "$T/best.kicad_pcb" ] && [ "$best" -lt "$n" ]; then cp "$T/best.kicad_pcb" "$B"; n=$best; echo "restored best board"; fi
echo "final: unconnected $n"
