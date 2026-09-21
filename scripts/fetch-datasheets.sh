#!/usr/bin/env bash
# fetch-datasheets.sh — restore the gitignored vendor PDFs the notes in this repo cite.
# PDFs are gitignored (CLAUDE.md §5: no large binaries), so checksums are pinned here and
# the documents are restored on demand. analog.com is unreachable from this machine
# (2026-09-06 scar), so ADI documents come from a mirror; the checksum is what makes that safe.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fetch() { # url dest sha256
  local url="$1" dest="$2" want="$3"
  if [ -f "$dest" ] && shasum -a 256 "$dest" | grep -q "$want"; then
    echo "OK    $(basename "$dest") present and matches checksum"; return 0
  fi
  mkdir -p "$(dirname "$dest")"
  echo "fetch $url"
  local tmp; tmp="$(mktemp)"
  curl -fsSL --max-time 300 -o "$tmp" "$url"
  local got; got="$(shasum -a 256 "$tmp" | cut -d' ' -f1)"
  if [ "$got" != "$want" ]; then
    rm -f "$tmp"
    echo "FAIL  checksum mismatch for $(basename "$dest")" >&2
    echo "      want $want" >&2
    echo "      got  $got" >&2
    echo "      The document may have been revised. Verify the new revision by hand," >&2
    echo "      re-read anything this repo cites from it, then update the pin here." >&2
    return 1
  fi
  mv "$tmp" "$dest"; chmod 644 "$dest"
  echo "OK    $(basename "$dest") restored"
}

# EVAL-ADAU1860 User Guide UG-2017 Rev. 0 (26 pp). Cited by docs/rig-logic-levels.md and
# docs/two-adau1860-channel-allocation.md. Schematic sheets are VECTOR-DRAWN: pdftotext and
# PyMuPDF get_text() return ~140 chars per sheet and see NONE of the labels. Render the pages
# and read them as images. See the 2026-09-21 scar in .agent/MEMORY.md.
fetch \
  'https://docs.ampnuts.ru/analog.com.datasheet/adau1860/related_data/eval-adau1860-ug-2017.pdf' \
  "$ROOT/linux/adau1860-pi5/EVAL-ADAU1860_UG-2017.pdf" \
  'f4744990a98b4622ee1b0224a0fd4c8690f294cb6b48a687f7d1ab0dd4438090'


# ICM-45686 datasheet, document number DS-000489 Rev. 1.1 (199 pp). Cited by
# docs/audio-board-io-voltage.md. TDK's own invensense.tdk.com PDF URL and the Mouser mirror
# both return HTML to curl and to WebFetch (bot wall, same class as the analog.com block);
# this LCSC CDN path is the one that serves the real PDF. Text layer is present and complete —
# Tables 3 and 9 extract cleanly with `pdftotext -layout`.
fetch \
  'https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2411220643_TDK-InvenSense-ICM-45686_C22459454.pdf' \
  "$ROOT/kicad/imu-board/doc/ICM-45686_DS-000489.pdf" \
  'dbff9a161c741953bca8701a67348d85738a7904c35640ef4c8c44f0e22c3059'

# ADAU1860 datasheet Rev. 0 (30 pp). Cited by docs/audio-board-level-shifter.md for Table 9 (serial
# port timing: tSOD, tSS/tSH, fBCLK) and Table 13 (pin functions). This is the ABRIDGED datasheet —
# it carries no register map and no absolute-maximum table. The register map lives in the ADAU186x
# Hardware Reference Manual UG-2257, which is NOT mirrored here: every URL tried returned 404 or
# HTML. Fetch it by hand from ADI when a register-level question needs settling.
fetch \
  'https://docs.ampnuts.ru/analog.com.datasheet/adau1860/adau1860.pdf' \
  "$ROOT/linux/adau1860-pi5/ADAU1860_datasheet.pdf" \
  'b2f6f1196343bc8c7b3e6192eddefbdcd0b5a32b1f968ff56520d8eb2ca61b3a'

echo "done"
