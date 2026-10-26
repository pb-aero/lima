#!/usr/bin/env bash
# Rebuild the audio-board copper from the rev2 placement: moves -> plane cut -> hand routes -> fanout -> DSN.
# Run from the repo root with KiCad closed.  Usage: build.sh <scratch-dir>
set -euo pipefail
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
B=$PWD/kicad/audio-board/audio-board.kicad_pcb; R=kicad/audio-board/doc/route; T=$1
git show 4d9bbee:kicad/audio-board/audio-board.kicad_pcb > "$B"
q() { "$PY" "$@" 2>&1 | grep -v "image handler\|wxApp" || true; }
q $R/moves.py "$B" $R/placement-rev2b-moves.json
q $R/moves.py "$B" $R/placement-rev2c-moves.json
q $R/planecut.py "$B"
q $R/handroute.py "$B" $R/hand-routes.json
if [ "${IN2:-plane}" = signal ]; then FANOUT_NETS=/GND q $R/fanout.py "$B"; else q $R/fanout.py "$B"; fi
q $R/dsn.py "$B" "$T/raw.dsn"
/usr/bin/python3 -I $R/dsn_tweak.py "$T/raw.dsn" "$T/tw.dsn"
sed 's/(type route)/(type protect)/g; s/(type fix)/(type protect)/g' "$T/tw.dsn" > "$T/route.dsn"
echo "DSN ready: $T/route.dsn"
