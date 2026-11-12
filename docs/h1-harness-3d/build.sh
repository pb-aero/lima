#!/usr/bin/env bash
# Regenerate the board models for the 3D harness page (docs/h1-harness-3d/index.html). Run from the repo root.
# Exports one at a time: two kicad-cli GLB exports in parallel corrupted cup.glb's JSON (2026-10-30).
# The artifact host serves no .glb, so the page fetches base64 text copies.
set -euo pipefail
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; D=docs/h1-harness-3d
"$CLI" pcb export glb --user-origin 135x105mm --include-silkscreen --include-soldermask -f -o $D/audio.glb kicad/audio-board/audio-board.kicad_pcb
"$CLI" pcb export glb --user-origin 150x100mm --include-silkscreen --include-soldermask -f -o $D/cup.glb kicad/cup-board/cup-board.kicad_pcb
base64 -i $D/audio.glb -o $D/audio.glb.txt; base64 -i $D/cup.glb -o $D/cup.glb.txt

# AeroNode Rev 0.0.2 board (STEP from Peter's Downloads, not in the repo): KiCad tessellates a STEP only as a footprint's
# 3D model, so wrap it in a one-footprint scratch board, export GLB, then slim it (merge, quantise, drop normals) to fit.
AERO_STEP=${AERO_STEP:-"$HOME/Downloads/AeroNode Rev 0.0.2 - Updated GPS model.step"}
if [ -f "$AERO_STEP" ]; then
  W=$(mktemp -d); ln -sf "$AERO_STEP" "$W/aeronode.step"
  cat > "$W/wrap.kicad_pcb" <<PCB
(kicad_pcb (version 20240108) (generator "pcbnew") (generator_version "8.0") (general (thickness 1.6)) (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user) (49 "F.Fab" user) (47 "F.CrtYd" user "F.Courtyard"))
  (net 0 "")
  (footprint "wrap:AERONODE" (layer "F.Cu") (at 100 100) (attr smd)
    (model "$W/aeronode.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0))))
  (gr_rect (start 99 99) (end 101 101) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts")))
PCB
  "$CLI" pcb export glb --no-board-body --user-origin 100x100mm -f -o "$W/aeronode.glb" "$W/wrap.kicad_pcb"
  /usr/bin/python3 -I $D/slim_glb.py "$W/aeronode.glb" $D/aeronode.glb
  base64 -i $D/aeronode.glb -o $D/aeronode.glb.txt
fi

# AeroIMU Rev 0 and AeroVault Rev 0.0.2 board models (AS_Engineering/CAD/Aeronode, downloaded to ~/Downloads).
# AeroIMU_Rev0.bin is a STEP file despite its extension. AeroMic Rev 0.1 is for the Black Maverick V1 page (black-maverick-v1.html).
for pair in "AeroIMU_Rev0.bin:aeroimu" "AeroVault Rev0.0.2.step:aerovault" "AeroMic Rev 0.1.step:aeromic"; do
  src="$HOME/Downloads/${pair%%:*}"; out=${pair##*:}
  if [ -f "$src" ]; then $D/step2glb.sh "$src" $D/$out.glb && rm -f $D/$out.raw.glb && base64 -i $D/$out.glb -o $D/$out.glb.txt; fi
done
