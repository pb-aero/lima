#!/bin/bash
# AeroVault: format the W25N01GV with UBI and mount UBIFS on it.
#
# DESTRUCTIVE — erases the whole 128 MiB array. Safe on a blank part, not on one with data.
# Run it with sudo. Every step is traced and the whole run is logged to /home/node/aerovault/ubi-setup.log,
# so the outcome can be read back afterwards even if the terminal is gone.
#
#   sudo bash ~/aerovault/ubi-setup.sh
#
# Lives in ~/aerovault, NOT /tmp: /tmp on this Pi is tmpfs and is wiped by every reboot.
#
# ubiformat is used deliberately in place of flash_erase: it erases while PRESERVING the
# factory bad-block markers and the per-block erase counters. On NAND that distinction matters.
set -x
exec &> >(tee /home/node/aerovault/ubi-setup.log)

VOL=aerovault
MNT=/mnt/aerovault

/usr/sbin/ubiformat /dev/mtd0 -y   || { echo "FAILED: ubiformat";  exit 1; }
modprobe ubi                        || { echo "FAILED: modprobe ubi"; exit 1; }
/usr/sbin/ubiattach -m 0            || { echo "FAILED: ubiattach";  exit 1; }
/usr/sbin/ubimkvol /dev/ubi0 -N "$VOL" -m || { echo "FAILED: ubimkvol"; exit 1; }
mkdir -p "$MNT"
mount -t ubifs "ubi0:$VOL" "$MNT"   || { echo "FAILED: mount";      exit 1; }

set +x
echo "=== RESULT ==="
df -h "$MNT"
/usr/sbin/ubinfo -a
echo "OK — UBIFS mounted at $MNT"
