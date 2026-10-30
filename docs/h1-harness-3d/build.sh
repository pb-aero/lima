#!/usr/bin/env bash
# Regenerate the board models for the 3D harness page (docs/h1-harness-3d/index.html). Run from the repo root.
# Exports one at a time: two kicad-cli GLB exports in parallel corrupted cup.glb's JSON (2026-10-30).
# The artifact host serves no .glb, so the page fetches base64 text copies.
set -euo pipefail
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; D=docs/h1-harness-3d
"$CLI" pcb export glb --user-origin 135x105mm --include-silkscreen --include-soldermask -f -o $D/audio.glb kicad/audio-board/audio-board.kicad_pcb
"$CLI" pcb export glb --user-origin 150x100mm --include-silkscreen --include-soldermask -f -o $D/cup.glb kicad/cup-board/cup-board.kicad_pcb
base64 -i $D/audio.glb -o $D/audio.glb.txt; base64 -i $D/cup.glb -o $D/cup.glb.txt
