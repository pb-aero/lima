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

# ADAU186x Hardware Reference Manual UG-2257 Rev. 0 (337 pp). Cited by
# docs/audio-board-level-shifter.md for the SPTx clock-source registers (Tables 277/278, 296).
# CANNOT BE FETCHED BY SCRIPT. analog.com refuses curl at the connection level and times out to
# WebFetch; opened in a browser it serves a SAVE DIALOG rather than a page. Download it by hand:
#   https://www.analog.com/media/en/technical-documentation/user-guides/adau186x-hardware-reference-manual-ug-2257.pdf
# then drop it at the path below. The checksum here is what verifies the hand-download.
#   want sha256 7c9b64be89d887d1594daa0e01881fa042cfa35b80788b04939062ef95fa58c2
verify_manual() { # dest sha256
  local dest="$1" want="$2"
  if [ ! -f "$dest" ]; then
    echo "MISSING $(basename "$dest") — download by hand, see the comment above"; return 0
  fi
  if shasum -a 256 "$dest" | grep -q "$want"; then
    echo "OK    $(basename "$dest") present and matches checksum"
  else
    echo "FAIL  $(basename "$dest") present but checksum DOES NOT MATCH" >&2; return 1
  fi
}
verify_manual \
  "$ROOT/linux/adau1860-pi5/ADAU186x_HRM_UG-2257.pdf" \
  '7c9b64be89d887d1594daa0e01881fa042cfa35b80788b04939062ef95fa58c2'

# ADAU1787 datasheet Rev. A (280 pp) and the AD242x A2B family datasheet Rev. C (38 pp). Cited by
# docs/audio-board-decision-record.md. BOTH ARE HAND-DOWNLOADED, same reason as UG-2257 above:
# analog.com refuses curl and WebFetch, and serves a browser a SAVE DIALOG rather than a page. Every
# third-party mirror tried for these two returned HTML. Download by hand from:
#   https://www.analog.com/media/en/technical-documentation/data-sheets/ADAU1787.pdf
#   https://www.analog.com/media/en/technical-documentation/data-sheets/ADAU1861.pdf
#   https://www.analog.com/media/en/technical-documentation/data-sheets/AD2420(W)-AD2426(W)-AD2427(W)-AD2428(W)-AD2429(W).pdf
verify_manual "$ROOT/docs/datasheets/ADAU1787_RevA.pdf" '69da92c07764915eea7e3dd61ad4351d28fbb06e5b01ba2205809ddbd657a14e'
verify_manual "$ROOT/docs/datasheets/AD242x_RevC.pdf"   '1d4e9efe621917e7638d0b5423ce1dc2a352ac1ac6f8a5b56c823daa813c311e'
verify_manual "$ROOT/docs/datasheets/ADAU1861.pdf"      '79740d4eab12475be316d7fcf3d21d227bbc2fc9d2391ff337af3acd2ff217e6'

# IM72D128V datasheet v01.00 (19 pp, Infineon). Cited by docs/dvnc-phase-budget.md for Table 2
# (phase response, group delay, LF roll-off, POLARITY) and Figures 4/5. Infineon serves this to
# curl directly - no browser needed, unlike analog.com.
fetch \
  'https://www.infineon.com/dgdl/Infineon-IM72D128V-DataSheet-v01_00-EN.pdf' \
  "$ROOT/docs/datasheets/IM72D128V_v01_00.pdf" \
  '14f9b744735d3c9c5dd62e9e09f092c44efdea37bf5c131e568dd1661acdbde2'

# ADXL354/ADXL355 datasheet Rev. D (45 pp). Cited by docs/dvnc-phase-budget.md for the FILTER section
# (p.25: sinc shape, 1.5 kHz antialias, 1.9 kHz overall) and the 32 k output resistor. Hand-downloaded
# via the browser - analog.com refuses curl and WebFetch.
verify_manual "$ROOT/docs/datasheets/ADXL354_355_RevD.pdf" 'd54235c1db7ffea74ee9c4a361294204eb8927c20657484aefb935eafb29e56c'

echo "done"
