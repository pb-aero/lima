#!/usr/bin/env bash
# Cup-board second finishing stage (after finish.sh left 7 open, all but two at the codec U1):
# re-seat the orphaned 1V8 fanout at R1.2, rip the nets crowding U1's mic/DMIC pins and the ZIF pads, route the
# stuck nets first (DMIC pair to J11, MK2 pair to J10, C10-R5, B_SENSE), then the rip-up finish loop.
# Usage: finish2.sh <scratch-dir>   Run from the repo root, KiCad closed.
set -uo pipefail
T=$1; B=${BOARD:-$PWD/kicad/cup-board/cup-board.kicad_pcb}; G=$PWD/kicad/lib/route
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; export PLANE_NETS=/GND,/1V8
drc() { "$CLI" pcb drc --refill-zones -o "$T/$1" "$B" > /dev/null 2>&1; echo "$1: $(grep -c '^\[unconnected' "$T/$1") unconnected"; }
q() { "$PY" -u "$@" 2>&1 | grep -E "ripped|blamed|fanned|locked|routed [0-9]+ of|: routed" || true; }
q $G/ripnets.py "$B" --near R1.2 --r 2.2 --local /1V8
FANOUT_NETS=/1V8 FANOUT_PADS=R1.2 q $G/fanout.py "$B"
q $G/ripnets.py "$B" --near U1.1,U1.7,U1.21,U1.22,C10.2,R5.1,J10.2,J10.3,J11.2,J11.3 --r 1.0 \
  /DMIC_CLK /DMIC_DATA /MK2_OUTP /MK2_OUTN "Net-(C10-Pad2)" /B_SENSE
drc t3.rpt
MAZE_LAYERS=F.Cu,B.Cu,In2.Cu LAYER_COST=1.3 MAZE_FIRST="/DMIC_CLK /DMIC_DATA /MK2_OUTN /MK2_OUTP Net-(C10-Pad2) /B_SENSE" \
  q $G/maze.py "$B" "$T/t3.rpt"
drc t4.rpt; q $G/drcfix.py "$B" "$T/t4.rpt"
rm -f "$T/best.kicad_pcb"
MAZE_LAYERS=F.Cu,B.Cu,In2.Cu LAYER_COST=1.3 STALL=6 "$G/finish.sh" "$B" "$T" 25
