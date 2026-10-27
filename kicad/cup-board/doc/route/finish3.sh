#!/usr/bin/env bash
# Cup-board third finishing stage: U1 (codec, r160) has its mic inputs on the outer face and was boxed in by early
# autorouted tracks on F.Cu, B.Cu and In2. Rip every net with copper near U1's signal pins or the three mic ZIFs and
# re-route mic pairs first (MK1, MK2, ADC2, DMIC, C10-R5), then the rest, then the rip-up loop. In2 is a costly last
# resort (LAYER_COST 3) so the 1V8 plane stops being carved into islands.
# Usage: finish3.sh <scratch-dir>   Run from the repo root, KiCad closed.
set -uo pipefail
T=$1; B=${BOARD:-$PWD/kicad/cup-board/cup-board.kicad_pcb}; G=$PWD/kicad/lib/route
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; export PLANE_NETS=/GND,/1V8
drc() { "$CLI" pcb drc --refill-zones -o "$T/$1" "$B" > /dev/null 2>&1; echo "$1: $(grep -c '^\[unconnected' "$T/$1") unconnected"; }
q() { "$PY" -u "$@" 2>&1 | grep -E "ripped|blamed|routed [0-9]+ of" || true; }
q $G/ripnets.py "$B" --near U1.1,U1.2,U1.4,U1.7,U1.15,U1.19,U1.20,U1.21,U1.22,U1.23,U1.24,U1.27,U1.28,U1.35,U1.36,U1.38,U1.39,U1.41,U1.44,U1.45,U1.49,U1.50,U1.51,U1.52,U1.54,U1.56,U1.58,U1.59,J9.1,J9.2,J9.3,J10.1,J10.2,J10.3,J11.1,J11.2,J11.3,C10.2,R5.1 --r 1.5 /B_SENSE
drc t5.rpt
export MAZE_LAYERS=F.Cu,B.Cu,In2.Cu LAYER_COST=3
MAZE_FIRST="/MK1_OUTP /MK1_OUTN /MK2_OUTP /MK2_OUTN /ADC2_P /ADC2_N /DMIC_CLK /DMIC_DATA Net-(C10-Pad2) /HPOUTP /HPOUTN /B_SENSE" \
  q $G/maze.py "$B" "$T/t5.rpt"
drc t6.rpt; q $G/drcfix.py "$B" "$T/t6.rpt"
rm -f "$T/best.kicad_pcb"
STALL=6 "$G/finish.sh" "$B" "$T" 25
