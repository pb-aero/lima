#!/bin/bash
# One page lands. A 64-page write lands only its FIRST page. Find the rule.
# For each burst size, erase a fresh block, write that many pages in one nandwrite, and count
# how many pages actually made it to the flash.
#
#   sudo bash ~/aerovault/write-burst-bisect.sh
#
# Destructive to blocks 310-315 on a scratch part.
set -u
exec &> >(tee /home/node/aerovault/write-burst-bisect.log)

DEV=/dev/mtd0
BS=131072
PS=2048
PAT=/tmp/burst.bin
OUT=/tmp/burst_out.bin

printf "%-8s %-10s %-12s %s\n" "pages" "bytes" "nandwrite" "pages that actually landed"
printf -- "-------- ---------- ------------ --------------------------\n"

BLK=310
for NP in 1 2 4 8 16 64; do
	OFF=$((BLK * BS))
	NB=$((NP * PS))
	python3 - "$PAT" "$NB" <<'PY'
import sys
n = int(sys.argv[2]); buf = bytearray()
while len(buf) < n:
    buf += b"@%06X-AEROVAULT-" % len(buf)
open(sys.argv[1], "wb").write(bytes(buf[:n]))
PY
	/usr/sbin/flash_erase "$DEV" "$OFF" 1 >/dev/null 2>&1
	WR=$(/usr/sbin/nandwrite -s "$OFF" "$DEV" "$PAT" 2>&1 | grep -ciE "error" || true)
	[ "$WR" -eq 0 ] && WR=ok || WR="ERROR"
	/usr/sbin/nanddump -s "$OFF" -l "$NB" -f "$OUT" "$DEV" >/dev/null 2>&1
	LANDED=0
	for ((p = 0; p < NP; p++)); do
		if cmp -s <(dd if="$PAT" bs=$PS skip=$p count=1 2>/dev/null) \
		          <(dd if="$OUT" bs=$PS skip=$p count=1 2>/dev/null); then
			LANDED=$((LANDED + 1))
		fi
	done
	printf "%-8s %-10s %-12s %s of %s\n" "$NP" "$NB" "$WR" "$LANDED" "$NP"
	BLK=$((BLK + 1))
done

echo
echo "=== same question, but one page per nandwrite call, 4 calls to consecutive pages ==="
OFF=$((320 * BS))
/usr/sbin/flash_erase "$DEV" "$OFF" 1 >/dev/null 2>&1
python3 - "$PAT" "$PS" <<'PY'
import sys
n = int(sys.argv[2]); buf = bytearray()
while len(buf) < n:
    buf += b"@%06X-AEROVAULT-" % len(buf)
open(sys.argv[1], "wb").write(bytes(buf[:n]))
PY
for ((p = 0; p < 4; p++)); do
	/usr/sbin/nandwrite -s $((OFF + p * PS)) "$DEV" "$PAT" >/dev/null 2>&1
done
/usr/sbin/nanddump -s "$OFF" -l $((4 * PS)) -f "$OUT" "$DEV" >/dev/null 2>&1
L=0
for ((p = 0; p < 4; p++)); do
	cmp -s "$PAT" <(dd if="$OUT" bs=$PS skip=$p count=1 2>/dev/null) && L=$((L + 1))
done
echo "  separate nandwrite calls: $L of 4 pages landed"
