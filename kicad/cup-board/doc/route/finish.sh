#!/usr/bin/env bash
# Cup-board finishing after Freerouting: B-side trio first (BN, BCM, BP; locked), DRC repair, rip-up finish loop.
# Usage: finish.sh <scratch-dir>   Run from the repo root, KiCad closed.
set -uo pipefail
T=$1; B=${BOARD:-$PWD/kicad/cup-board/cup-board.kicad_pcb}; G=$PWD/kicad/lib/route
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; export PLANE_NETS=/GND,/1V8
drc() { "$CLI" pcb drc --refill-zones -o "$T/$1" "$B" > /dev/null 2>&1; echo "$1: $(grep -c '^\[unconnected' "$T/$1") unconnected"; }
q() { "$PY" -u "$@" 2>&1 | grep -E "ripped|blamed|locked|routed [0-9]+ of|B_B" || true; }
# 1. U6's B-side trio has one forced crossing: BN first (takes its via), then BCM, then BP; lock all three
q $G/ripnets.py "$B" --near U6.22,U6.23,U6.24,FB3.1,FB3.2,FB4.1,FB4.2,C27.1,C27.2 --r 1.2 /B_BP /B_BN /B_BCM
drc t1.rpt; MAZE_FIRST="/B_BN /B_BCM /B_BP" q $G/maze.py "$B" "$T/t1.rpt"
q $G/locknets.py "$B" /B_BN /B_BCM /B_BP
# 2. rip what Freerouting got wrong (hole clearance, neckdowns, dangling) and re-route with In2 as a bus layer
drc t2.rpt; q $G/drcfix.py "$B" "$T/t2.rpt"
rm -f "$T/best.kicad_pcb"
MAZE_LAYERS=F.Cu,B.Cu,In2.Cu LAYER_COST=1.3 STALL=5 "$G/finish.sh" "$B" "$T" 25
