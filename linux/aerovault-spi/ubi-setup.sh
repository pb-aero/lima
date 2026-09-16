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

# ubiformat refuses to touch an mtd that UBI still holds, so let go of it first. Both of these
# are expected to fail on a clean boot and that is fine.
umount "$MNT" 2>/dev/null && echo "(unmounted $MNT)"
/usr/sbin/ubidetach -m 0 2>/dev/null && echo "(detached ubi from mtd0)"

/usr/sbin/ubiformat /dev/mtd0 -y   || { echo "FAILED: ubiformat";  exit 1; }
modprobe ubi                        || { echo "FAILED: modprobe ubi"; exit 1; }
/usr/sbin/ubiattach -m 0            || { echo "FAILED: ubiattach";  exit 1; }
# A previous volume can survive a reformat in the volume table and then owns every LEB, so
# ubimkvol fails with "does not have free logical eraseblocks". Remove it first; failure here
# is expected and fine when there is nothing to remove.
/usr/sbin/ubirmvol /dev/ubi0 -N "$VOL" 2>/dev/null && echo "(removed pre-existing volume $VOL)"
/usr/sbin/ubimkvol /dev/ubi0 -N "$VOL" -m || { echo "FAILED: ubimkvol"; exit 1; }
mkdir -p "$MNT"
mount -t ubifs "ubi0:$VOL" "$MNT"   || { echo "FAILED: mount";      exit 1; }

set +x
echo "=== RESULT ==="
df -h "$MNT"
/usr/sbin/ubinfo -a
echo "OK — UBIFS mounted at $MNT"
