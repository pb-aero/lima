#!/bin/bash
# AeroVault: verify a mounted UBIFS end to end. Run with sudo. Logs to /home/node/aerovault/ubi-verify.log.
#
#   sudo bash ubi-verify.sh
#
# Writes a 16 MiB test file, checksums it, forces it out of cache, re-reads it, then UNMOUNTS
# and REMOUNTS and checksums again — because a checksum that never left the page cache proves
# nothing about the flash. Removes the test file at the end. Does not touch anything else.
set -u
exec &> >(tee /home/node/aerovault/ubi-verify.log)

MNT=/mnt/aerovault
VOL=aerovault
TEST="$MNT/.verify.bin"
SIZE_MB=16
fail() { echo "FAIL: $*"; exit 1; }

mountpoint -q "$MNT" || fail "$MNT is not a mount point — run ubi-setup.sh first"
echo "=== before ==="; df -h "$MNT"; echo

echo "=== write ${SIZE_MB} MiB ==="
dd if=/dev/urandom of="$TEST" bs=1M count=$SIZE_MB conv=fsync 2>&1 | tail -1 || fail "write"
SUM_W=$(sha256sum "$TEST" | cut -d" " -f1)
echo "sha256 written : $SUM_W"

sync; echo 3 > /proc/sys/vm/drop_caches
echo; echo "=== read back with a cold cache ==="
time SUM_R=$(sha256sum "$TEST" | cut -d" " -f1)
echo "sha256 re-read : $SUM_R"
[ "$SUM_W" = "$SUM_R" ] || fail "checksum differs after cache drop — data is being corrupted"

echo; echo "=== unmount / remount — the only test that proves it reached the flash ==="
umount "$MNT"            || fail "umount"
mount -t ubifs "ubi0:$VOL" "$MNT" || fail "remount"
SUM_M=$(sha256sum "$TEST" | cut -d" " -f1)
echo "sha256 remount : $SUM_M"
[ "$SUM_W" = "$SUM_M" ] || fail "checksum differs after remount — it never reached the NAND"

echo; echo "=== flash health ==="
/usr/sbin/ubinfo -a | grep -iE "bad|corrupt|PEB|volume|size" | head -20
echo "--- kernel complaints (empty is good) ---"
dmesg | grep -iE "ubi.*(error|bad|corrupt|ecc)|spi-nand.*error" | tail -10
echo "(nothing above = no ECC corrections, no bad blocks reported this boot)"

rm -f "$TEST"; sync
echo; echo "=== after ==="; df -h "$MNT"
echo; echo "PASS — identical sha256 written, re-read cold, and re-read across an unmount cycle."
