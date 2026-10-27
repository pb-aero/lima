#!/usr/bin/env bash
# One full cup-board routing attempt in its own scratch dir: build -> Freerouting -> import -> DRC repair -> finish.
# Usage: variant.sh <U6-angle> <work-dir>    Prints the final unconnected count. Run from the repo root, KiCad closed.
set -uo pipefail
A=$1; W=$2; mkdir -p "$W"; export BOARD=$W/cup.kicad_pcb U6_ANGLE=$A
cp kicad/cup-board/cup-board.kicad_pro "$W/cup.kicad_pro"   # netclasses + design rules live in the project file
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; G=$PWD/kicad/lib/route
kicad/cup-board/doc/route/build.sh "$W" > "$W/build.log" 2>&1
/opt/homebrew/opt/openjdk/bin/java -jar ~/.konnect/tools/freerouting-2.5.0.jar -de "$W/cup.dsn" -do "$W/cup.ses" -mp 150 > "$W/fr.log" 2>&1
"$PY" "$G/ses.py" "$BOARD" "$W/cup.ses" > /dev/null 2>&1; "$PY" "$G/dedupe.py" "$BOARD" > /dev/null 2>&1; "$PY" "$G/rmdup_unlocked.py" "$BOARD" > /dev/null 2>&1
"$CLI" pcb drc --refill-zones -o "$W/fr.rpt" "$BOARD" > /dev/null 2>&1
echo "angle $A after Freerouting: $(grep -c '^\[unconnected' "$W/fr.rpt") unconnected" > "$W/result.txt"
PLANE_NETS=/GND,/1V8 "$PY" "$G/drcfix.py" "$BOARD" "$W/fr.rpt" > /dev/null 2>&1
PLANE_NETS=/GND,/1V8 STALL=6 "$G/finish.sh" "$BOARD" "$W" 30 > "$W/finish.log" 2>&1
tail -1 "$W/finish.log" | sed "s/^/angle $A /" >> "$W/result.txt"; cat "$W/result.txt"
