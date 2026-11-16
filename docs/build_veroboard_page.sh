#!/usr/bin/env bash
# Rebuild docs/gma-match-veroboard.html from its source and the checked stripboard layout. Run from the repo root.
# veroboard.py refuses to emit JSON unless the layout's connectivity matches design_nets.py.
set -euo pipefail
J=$(cd kicad/gma-match-board/doc && python3 -I veroboard.py json 2>&1 >/dev/null)
awk -v j="$J" '{ i = index($0, "__VERO_JSON__"); if (i) print substr($0, 1, i - 1) j substr($0, i + 13); else print }' \
  docs/gma-match-veroboard.src.html > docs/gma-match-veroboard.html
echo "built docs/gma-match-veroboard.html"
