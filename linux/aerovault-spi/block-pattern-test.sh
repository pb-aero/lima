#!/bin/bash
# One page round-trips perfectly; a whole block does not. Find WHERE it breaks.
# Writes a self-describing pattern across a full 128 KiB eraseblock, reads it back, and reports
# the first divergence and how the errors are distributed across the 64 pages.
#
#   sudo bash ~/aerovault/block-pattern-test.sh [block_number]
#
# Destructive to the one block tested (default 301) on a scratch part.
set -u
exec &> >(tee /home/node/aerovault/block-pattern-test.log)

DEV=/dev/mtd0
BLK=${1:-301}
BS=131072
OFF=$((BLK * BS))
PAT=/tmp/pat_blk.bin
OUT=/tmp/read_blk.bin

python3 - "$PAT" "$BS" <<'PY'
import sys
n = int(sys.argv[2]); buf = bytearray()
while len(buf) < n:
    buf += b"@%06X-AEROVAULT-" % len(buf)
open(sys.argv[1], "wb").write(bytes(buf[:n]))
PY

echo "=== erase block $BLK ==="
/usr/sbin/flash_erase "$DEV" "$OFF" 1 2>&1 | tr '\r' '\n' | tail -1

echo "=== write $BS bytes (64 pages) in one nandwrite ==="
/usr/sbin/nandwrite -s "$OFF" "$DEV" "$PAT" 2>&1 | tail -2

echo "=== read back ==="
/usr/sbin/nanddump -s "$OFF" -l "$BS" -f "$OUT" "$DEV" 2>&1 | tail -1

echo
echo "=== verdict ==="
if cmp -s "$PAT" "$OUT"; then
	echo "IDENTICAL — the whole block round-trips."
	exit 0
fi
FIRST=$(cmp "$PAT" "$OUT" 2>/dev/null | grep -o "byte [0-9]*" | head -1 | cut -d" " -f2)
TOTAL=$(cmp -l "$PAT" "$OUT" 2>/dev/null | wc -l)
echo "first differing byte : $FIRST  (page $(( (FIRST-1) / 2048 )) of 64)"
echo "total differing bytes: $TOTAL of $BS"
echo
echo "errors per page (page:count, only pages with errors):"
cmp -l "$PAT" "$OUT" 2>/dev/null | awk '{p=int(($1-1)/2048); c[p]++} END {for (i=0;i<64;i++) if (c[i]) printf "  page %2d: %5d\n", i, c[i]}'
echo
echo "first 64 bytes of the first bad page:"
BADPAGE=$(( (FIRST-1) / 2048 ))
dd if="$OUT" bs=2048 skip=$BADPAGE count=1 2>/dev/null | hexdump -C | head -4
echo "  ...expected:"
dd if="$PAT" bs=2048 skip=$BADPAGE count=1 2>/dev/null | hexdump -C | head -4
