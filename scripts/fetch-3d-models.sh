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
  echo "OK  $OUT already present and matches checksum"; exit 0
fi

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
