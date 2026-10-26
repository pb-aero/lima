#!/usr/bin/env bash
# Finish routing with maze.py + rip-up until DRC shows nothing unconnected (or no progress). KiCad closed.
# Usage: finish.sh <board> <scratch-dir> [max-iterations]   env passes through to maze.py (PLANE_NETS, MAZE_W, ...)
set -uo pipefail
B=$1; T=$2; MAX=${3:-40}
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; D=$(cd "$(dirname "$0")" && pwd)
for i in $(seq 1 "$MAX"); do
  "$CLI" pcb drc --refill-zones -o "$T/finish.rpt" "$B" >/dev/null 2>&1
  n=$(grep -c '^\[unconnected_items\]' "$T/finish.rpt"); e=$(grep -c '; error' "$T/finish.rpt")
  echo "iter $i: unconnected $n, errors $e"
  [ "$n" -eq 0 ] && break
  RIPUP=1 "$PY" -u "$D/maze.py" "$B" "$T/finish.rpt" 2>&1 | grep -E "rip-up|routed [0-9]+ of|no path" | tail -4
  rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] && { "$CLI" pcb drc --refill-zones -o "$T/finish.rpt" "$B" >/dev/null 2>&1; echo "no rip-up possible; unconnected now $(grep -c "^\[unconnected_items\]" "$T/finish.rpt")"; break; }
  [ "$rc" -ne 3 ] && { echo "maze exit $rc"; break; }
done
