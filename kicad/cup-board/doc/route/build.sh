#!/usr/bin/env bash
# Rebuild the cup-board copper from the placed, unrouted board (3ab5285). Run from the repo root, KiCad closed.
# Usage: build.sh <scratch-dir>      -> leaves $T/cup.dsn ready for Freerouting
set -euo pipefail
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
B=$PWD/kicad/cup-board/cup-board.kicad_pcb; G=kicad/lib/route; T=$1
q() { "$PY" -u "$@" 2>&1 | grep -v "image handler\|wxApp\|memory leak" || true; }
git show 3ab5285:kicad/cup-board/cup-board.kicad_pcb > "$B"
# U6 turned +90 deg so its B-bus pins (22-24) and SENSE/SWP/VSSN (26-28) face the B filter/bias chain up the ring
# (B-side ratsnest 115 -> 92 mm, A side unchanged). Its decaps are parked, then re-seated end-on at their pins
# (decaps.py) so no cap lies along a pin face; C35 is VIN's 100 nF, brought over from the U7 corner.
q kicad/lib/route/moves.py "$B" kicad/cup-board/doc/route/u6-rotate.json
q $G/decaps.py "$B" U6 C35:30 C39:20 C37:1 C38:21 C36:2 --r 4
q $G/planes.py "$B" /GND=In1.Cu /1V8=In2.Cu
FANOUT_NETS=/GND,/1V8 q $G/fanout.py "$B"
q $G/dsn.py "$B" "$T/cup_raw.dsn"
PROTECT=1 PLANE_LAYERS=In2.Cu EDGE_INSET=0.4 FINE_NETS="/VIN_CUP /3V3_MIC /VLED" /usr/bin/python3 -I $G/dsn_tweak.py "$T/cup_raw.dsn" "$T/cup.dsn"
echo "DSN ready: $T/cup.dsn"
