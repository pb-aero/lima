#!/usr/bin/env bash
# STEP -> slim GLB (mm, page frame) for the 3D harness page. KiCad tessellates a STEP only as a footprint's 3D model,
# so the STEP is wrapped in a one-footprint scratch board and exported, then slimmed by slim_glb.py.
# Usage: step2glb.sh <file.step> <out.glb>     Run one at a time: parallel kicad-cli exports corrupted output once.
set -euo pipefail
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli; HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d); ln -sf "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")" "$W/model.step"
cat > "$W/wrap.kicad_pcb" <<PCB
(kicad_pcb (version 20240108) (generator "pcbnew") (generator_version "8.0") (general (thickness 1.6)) (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user) (49 "F.Fab" user) (47 "F.CrtYd" user "F.Courtyard"))
  (net 0 "")
  (footprint "wrap:MODEL" (layer "F.Cu") (at 100 100) (attr smd)
    (model "$W/model.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0))))
  (gr_rect (start 99 99) (end 101 101) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts")))
PCB
"$CLI" pcb export glb --no-board-body --user-origin 100x100mm -f -o "$W/raw.glb" "$W/wrap.kicad_pcb" > /dev/null
cp "$W/raw.glb" "${2%.glb}.raw.glb"
/usr/bin/python3 -I "$HERE/slim_glb.py" "$W/raw.glb" "$2"
