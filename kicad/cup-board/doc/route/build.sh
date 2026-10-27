#!/usr/bin/env bash
# Rebuild the cup-board copper from the committed schematic. Run from the repo root, KiCad closed.
# Usage: build.sh <scratch-dir>      -> leaves $T/cup.dsn ready for Freerouting; BOARD/U6_TURN env override
set -euo pipefail
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
B=${BOARD:-$PWD/kicad/cup-board/cup-board.kicad_pcb}; G=$PWD/kicad/lib/route; D=$PWD/kicad/cup-board/doc; T=$1
q() { "$PY" -u "$@" 2>&1 | grep -v "image handler\|wxApp\|memory leak" || true; }
# 1. placed 68/38 board (3ab5285) synced to the current schematic: mics -> J9/J10/J11 flex ZIFs, H3 dropped
git show 3ab5285:kicad/cup-board/cup-board.kicad_pcb > "$B"
"$CLI" sch export netlist --format kicadxml -o "$T/cup.xml" kicad/cup-board/cup-board.kicad_sch > /dev/null
q $G/syncnet.py "$B" "$T/cup.xml"
# 2. ring 72/38 (Peter, 2026-10-27): outer circle r34 -> r36, then the ring placer for the new band
q $D/ring_resize.py "$B" 34 36
python3 -I $D/ring_placement.py | tail -2
q $D/apply_placement.py "$B" $D/cup_placement.json
q $D/pull_in_connectors.py "$B" $D/cup_placement.json 36   # JST MP tabs 0.55 mm inside the curved edge
# 3. U6 turned +90 deg so its B-bus pins face the B chain; decaps parked, then seated end-on at their pins
q $G/turn.py "$B" U6:${U6_TURN:-90} --park C35,C36,C37,C38,C39
q $G/decaps.py "$B" U6 C35:30 C39:20 C37:1 C38:21 C36:2 --r 4
# 4. planes, fanout, DSN for Freerouting
q $G/planes.py "$B" /GND=In1.Cu /1V8=In2.Cu
FANOUT_NETS=/GND,/1V8 q $G/fanout.py "$B"
q $G/dsn.py "$B" "$T/cup_raw.dsn"
PROTECT=1 PLANE_LAYERS=In2.Cu EDGE_INSET=0.4 FINE_NETS="/VIN_CUP /3V3_MIC /VLED" /usr/bin/python3 -I $G/dsn_tweak.py "$T/cup_raw.dsn" "$T/cup.dsn"
echo "DSN ready: $T/cup.dsn"
