#!/bin/bash
# Measure whether this NAND actually RETAINS what is written to it.
#
# DESTRUCTIVE to the region tested (default 1 MiB = 8 blocks, starting at block 16).
# The part is scratch, so this costs nothing and answers the question ubiformat keeps raising:
# erase and program are being ACKNOWLEDGED but the data is not sticking.
#
#   sudo bash ~/aerovault/nand-write-test.sh
#
# nandtest erases, writes a known pattern, reads it back and compares, for each block, N times.
# Any "compare failed" line is a block that accepted a write and did not keep it.
set -u
exec &> >(tee /home/node/aerovault/nand-write-test.log)

DEV=/dev/mtd0
OFF=0x200000          # block 16 — well clear of the UBI headers at PEBs 0-2
LEN=0x100000          # 1 MiB = 8 eraseblocks
PASSES=3

echo "=== ECC/bad-block counters BEFORE ==="
for f in bad_blocks ecc_failures corrected_bits; do
	printf "  %-14s %s\n" "$f" "$(cat /sys/class/mtd/mtd0/$f)"
done

echo
echo "=== nandtest: $PASSES passes over $LEN bytes at $OFF ==="
/usr/sbin/nandtest -p "$PASSES" -r 2 -o "$OFF" -l "$LEN" "$DEV"
echo "nandtest exit: $?"

echo
echo "=== ECC/bad-block counters AFTER ==="
for f in bad_blocks ecc_failures corrected_bits; do
	printf "  %-14s %s\n" "$f" "$(cat /sys/class/mtd/mtd0/$f)"
done

echo
echo "=== kernel complaints during the test ==="
dmesg | tail -20
