#!/usr/bin/env bash
# fetch-3d-models.sh — restore the gitignored 3D models referenced by kicad/lib/*.pretty
# The STEP is 13 MB, so it is not committed (CLAUDE.md §5). This script restores it
# deterministically from the vendor, with the archive checksum pinned.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/kicad/lib/Digi.3dshapes"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Digi ConnectCore 91/93 SoM 3D Model (STEP+PDF), asset dated 2024-08-18.
URL='https://hub.digi.com/dp/path=/support/asset/connectcore-91-and-93-som-3d-model-step-pdf/'
ZIP_SHA256='b633376ed52c5c4950fc849b43d04ca3f592d467650570a6dada0ada96c76a0b'
MEMBER='3001753x-02_A_CC93_3D/CC93_55002169-01_1P_STEP.step'
OUT="$DEST/Digi_ConnectCore93.step"
OUT_SHA256='24786966510d9b91ee8fe41b55416782a5bd909ca828af090ee64e131fbfa80a'

if [ -f "$OUT" ] && shasum -a 256 "$OUT" | grep -q "$OUT_SHA256"; then
  echo "OK  $OUT already present and matches checksum"
else
  mkdir -p "$DEST"
  echo "fetching $URL"
  curl -fsSL --max-time 600 -A 'Mozilla/5.0' -o "$TMP/cc93_3d.zip" "$URL"

  got=$(shasum -a 256 "$TMP/cc93_3d.zip" | cut -d' ' -f1)
  if [ "$got" != "$ZIP_SHA256" ]; then
    echo "FATAL: archive checksum mismatch." >&2
    echo "  expected $ZIP_SHA256" >&2
    echo "  got      $got" >&2
    echo "Digi may have revised the asset. Verify the new file by hand before trusting it," >&2
    echo "re-check the module geometry, and update the pins in this script." >&2
    exit 1
  fi

  unzip -q -o -j "$TMP/cc93_3d.zip" "$MEMBER" -d "$TMP"
  mv "$TMP/$(basename "$MEMBER")" "$OUT"

  got=$(shasum -a 256 "$OUT" | cut -d' ' -f1)
  [ "$got" = "$OUT_SHA256" ] || { echo "FATAL: extracted STEP checksum mismatch ($got)" >&2; exit 1; }
  echo "OK  restored $OUT"
fi

# u-blox DAN-F10N GNSS module 3D model. u-blox publish no STEP for this part; this file
# traces back to u-blox's own SolidWorks assembly (DAN_with_Taoglas_Antenna_110225.STEP)
# via the SparkFun-KiCad-Libraries repo, CC-BY 4.0, pinned to a specific commit.
DEST2="$ROOT/kicad/lib/ublox.3dshapes"
COMMIT='5741e46fc9824e1e83e5cd353fc43880803dafcb'
URL2="https://raw.githubusercontent.com/sparkfun/SparkFun-KiCad-Libraries/${COMMIT}/3dmodels/GNSS.3dshapes/u-blox_DAN-F10N.step"
OUT2="$DEST2/u-blox_DAN-F10N.step"
OUT2_SHA256='ac4e12deeab905551cd0424d0b4f7989850cd446ad4ea172667a5f08f06ca568'

if [ -f "$OUT2" ] && shasum -a 256 "$OUT2" | grep -q "$OUT2_SHA256"; then
  echo "OK  $OUT2 already present and matches checksum"
else
  mkdir -p "$DEST2"
  echo "fetching $URL2"
  curl -fsSL --max-time 120 -o "$OUT2" "$URL2"
  got2=$(shasum -a 256 "$OUT2" | cut -d' ' -f1)
  if [ "$got2" != "$OUT2_SHA256" ]; then
    echo "FATAL: DAN-F10N STEP checksum mismatch." >&2
    echo "  expected $OUT2_SHA256" >&2
    echo "  got      $got2" >&2
    rm -f "$OUT2"
    exit 1
  fi
  echo "OK  restored $OUT2"
fi
