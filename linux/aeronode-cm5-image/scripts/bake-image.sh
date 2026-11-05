#!/usr/bin/env bash
# Stage 2 of 2: turn a WORKING card into a distributable .img.
#
# Run this on a LINUX host with the AeroNode's SD/eMMC attached, or on the
# board itself against its own boot device.  It does NOT run on macOS: it
# needs loop devices, e2fsck/resize2fs and parted.
#
#   sudo ./bake-image.sh /dev/sdX  aeronode-rev002-ardupilot-$(date +%F).img
#
# Order matters: SHRINK BEFORE YOU DD, or you copy the whole card.
set -euo pipefail

SRC="${1:-}"
OUT="${2:-}"
[ -n "$SRC" ] && [ -n "$OUT" ] || { sed -n '2,12p' "$0"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
[ -b "$SRC" ] || { echo "$SRC is not a block device" >&2; exit 1; }

echo "=== source device ==="
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$SRC"
echo
echo "This will READ $SRC and WRITE $OUT. $SRC must be UNMOUNTED and must not"
echo "be the running root filesystem unless you know what you are doing."
read -r -p "type the device path again to confirm: " confirm
[ "$confirm" = "$SRC" ] || { echo "mismatch -- aborted"; exit 1; }

echo "=== 1. first-boot reset, so every flashed board is distinct ==="
cat <<'NOTE'
  Before baking, on the board, clear the identity that must NOT be cloned:
    sudo rm -f /etc/ssh/ssh_host_*            # regenerated on first boot
    sudo rm -f /etc/machine-id && sudo touch /etc/machine-id
    sudo rm -rf /var/lib/ardupilot/*          # logs, params, terrain cache
    sudo rm -f /home/*/.bash_history
  ArduPilot stores its PARAMETERS under -l (/var/lib/ardupilot). Baking them
  in means every board inherits one board's calibration -- including its
  accel/compass offsets, which are per-unit. Clear them.
NOTE
read -r -p "done that? [y/N] " ack
[ "$ack" = y ] || { echo "aborted"; exit 1; }

echo "=== 2. fsck + shrink the last partition ==="
LAST=$(lsblk -lno NAME "$SRC" | tail -1)
LASTDEV="/dev/$LAST"
e2fsck -fy "$LASTDEV"
resize2fs -M "$LASTDEV"
BLKSZ=$(tune2fs -l "$LASTDEV" | awk -F': *' '/Block size/{print $2}')
BLKS=$(tune2fs -l "$LASTDEV" | awk -F': *' '/Block count/{print $2}')
FS_BYTES=$(( BLKS * BLKSZ ))
START=$(partx -g -o START "$LASTDEV" | tr -d ' ')
END_SECT=$(( START + FS_BYTES/512 + 8192 ))     # 4 MiB slack
parted -s "$SRC" unit s resizepart "${LAST##*p}" "${END_SECT}s"
echo "shrunk: fs ${FS_BYTES} B, partition ends at sector ${END_SECT}"

echo "=== 3. dd only up to the end of the last partition ==="
COUNT=$(( (END_SECT + 1) / 2048 + 1 ))          # 1 MiB blocks
dd if="$SRC" of="$OUT" bs=1M count="$COUNT" status=progress conv=fsync

echo "=== 4. compress + checksum ==="
xz -T0 -9 -k "$OUT"
sha256sum "$OUT" "$OUT.xz" | tee "$OUT.sha256"

echo
echo "=== 5. VERIFY THE IMAGE, do not ship it unverified ==="
cat <<'VERIFY'
  An image that boots is not an image that flies. On a FRESHLY FLASHED board:
    1. journalctl -u arduplane -b | grep -E 'RPI 5|Cannot detect board-type'
    2. the sensors actually probed:
         journalctl -u arduplane -b | grep -iE 'icm45686|mmc5983|bmp5|bmp3'
    3. no Config Error:
         journalctl -u arduplane -b | grep -i 'Config Error'
    4. EKF reaches healthy (needs the board to see GPS):
         ekf-bridge --in udp:127.0.0.1:14550 --out stdout | head -3
       and confirm  "flags":{"uninitialized":false,...,"_healthy":true}
  Only (4) proves the thing the image exists for.
VERIFY
