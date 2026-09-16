#!/bin/bash
# Write ONE page with a self-describing pattern and dump it back, to see the STRUCTURE of the
# corruption. Random data cannot tell you whether bytes are mangled, shifted, or simply absent;
# a pattern that encodes its own offset can.
#
#   sudo bash ~/aerovault/page-pattern-test.sh
#
# Destructive to one 128 KiB block (block 300) on a scratch part.
set -u
exec &> >(tee /home/node/aerovault/page-pattern-test.log)

DEV=/dev/mtd0
BLK=300
OFF=$((BLK * 131072))
PAT=/tmp/pat.bin
OUT=/tmp/readback.bin

# 2048 bytes: each 16-byte line is "@%06x" followed by a fixed marker, so any shift is obvious
python3 - "$PAT" <<'PY'
import sys
buf = bytearray()
while len(buf) < 2048:
    buf += b"@%06X-AEROVAULT-" % len(buf)
open(sys.argv[1], "wb").write(bytes(buf[:2048]))
PY

echo "=== pattern written to flash (first 64 bytes) ==="
hexdump -C "$PAT" | head -4

echo
echo "=== erase block $BLK (offset $(printf 0x%x $OFF)) ==="
/usr/sbin/flash_erase "$DEV" "$OFF" 1

echo
echo "=== verify the erase actually took (expect all ff) ==="
/usr/sbin/nanddump -s "$OFF" -l 64 -o "$DEV" 2>/dev/null | head -6

echo
echo "=== write one page ==="
/usr/sbin/nandwrite -s "$OFF" "$DEV" "$PAT" && echo "nandwrite OK"

echo
echo "=== read it back ==="
/usr/sbin/nanddump -s "$OFF" -l 2048 -f "$OUT" "$DEV" 2>&1 | tail -2
hexdump -C "$OUT" | head -6

echo
echo "=== verdict ==="
if cmp -s "$PAT" "$OUT"; then
	echo "IDENTICAL — this page round-trips perfectly."
else
	echo "DIFFERS. First 10 differing byte positions:"
	cmp -l "$PAT" "$OUT" 2>/dev/null | head -10
	echo "bytes differing: $(cmp -l "$PAT" "$OUT" 2>/dev/null | wc -l) of 2048"
	echo
	echo "Is the readback a SHIFTED copy of the pattern? Searching for the marker:"
	grep -aob "AEROVAULT" "$OUT" | head -5 || echo "  marker not present anywhere — data is mangled, not shifted"
fi
