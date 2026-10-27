#!/usr/bin/env bash
# Rebuild the cup-board copper from the placed, unrouted board (3ab5285). Run from the repo root, KiCad closed.
# Usage: build.sh <scratch-dir>      -> leaves $T/cup.dsn ready for Freerouting
set -euo pipefail
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
B=$PWD/kicad/cup-board/cup-board.kicad_pcb; G=kicad/lib/route; T=$1
q() { "$PY" -u "$@" 2>&1 | grep -v "image handler\|wxApp\|memory leak" || true; }
git show 3ab5285:kicad/cup-board/cup-board.kicad_pcb > "$B"
# U6 decoupling: VIN's 100 nF (C35) brought from the U7 corner to pin 30; C38 and C35 slid 1.4 mm off U6's
# pin 25-32 face so VIN / VOUT2 / SENSE / SWP / VSSN can escape (the rip-up loop thrashed there without it)
q $G/autoplace.py "$B" C38 135.19 115.01 --r 0.6 --angles -45,135 --pad 1 --toward 132.91,116.93
q $G/autoplace.py "$B" C35 133.93 112.96 --r 0.8 --angles -45,135 --pad 1 --toward 132.56,116.58
q $G/planes.py "$B" /GND=In1.Cu /1V8=In2.Cu
FANOUT_NETS=/GND,/1V8 q $G/fanout.py "$B"
q $G/dsn.py "$B" "$T/cup_raw.dsn"
PROTECT=1 PLANE_LAYERS=In2.Cu EDGE_INSET=0.4 FINE_NETS="/VIN_CUP /3V3_MIC /VLED" /usr/bin/python3 -I $G/dsn_tweak.py "$T/cup_raw.dsn" "$T/cup.dsn"
echo "DSN ready: $T/cup.dsn"
