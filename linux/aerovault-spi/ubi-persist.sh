#!/bin/bash
# Make the AeroVault UBIFS come back by itself after a reboot.
#
#   sudo bash ~/aerovault/ubi-persist.sh
#
# The naive version of this (modules-load.d + modprobe options + a plain fstab line) FAILS, and
# the boot log says exactly why:
#
#   [2.415] UBI error: cannot open mtd 0, error -19      <- ubi loaded here
#   [3.468] spi-nand spi0.0: Winbond SPI NAND was found  <- the flash appeared one second LATER
#
# `ubi` is loaded early by systemd-modules-load; the SPI NAND is not probed until the SPI bus comes
# up. Attaching on a timer is a race you lose. So attach on the EVENT instead: udev starts the
# service when mtd0 appears, whenever that happens to be.
set -u
exec &> >(tee /home/node/aerovault/ubi-persist.log)

MNT=/mnt/aerovault
VOL=ubi0:aerovault

echo "=== remove the version that races ==="
rm -fv /etc/modules-load.d/aerovault-ubi.conf

echo
echo "=== 1. modprobe options: attach mtd0 as the module loads ==="
echo "options ubi mtd=0" > /etc/modprobe.d/aerovault-ubi.conf
cat /etc/modprobe.d/aerovault-ubi.conf

echo
echo "=== 2. udev: start the service when mtd0 appears ==="
cat > /etc/udev/rules.d/99-aerovault.rules <<'RULE'
# AeroVault: the SPI NAND is probed well after systemd-modules-load has run, so UBI cannot be
# attached on a timer. Fire on the device-add event instead.
SUBSYSTEM=="mtd", KERNEL=="mtd0", ACTION=="add", TAG+="systemd", ENV{SYSTEMD_WANTS}+="aerovault.service"
RULE
cat /etc/udev/rules.d/99-aerovault.rules

echo
echo "=== 3. the service: load, attach, mount ==="
cat > /etc/systemd/system/aerovault.service <<'UNIT'
[Unit]
Description=Attach UBI to mtd0 and mount AeroVault
After=dev-mtd0.device
# A flash fault must never leave a headless Pi stuck at boot.
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
# "-" on the first two: modprobe options already attach mtd0, so ubiattach is a fallback that is
# expected to fail with EEXIST on a normal boot. Only the mount is allowed to fail the unit.
ExecStart=-/sbin/modprobe ubi
ExecStart=-/usr/sbin/ubiattach -m 0
ExecStart=/bin/mount /mnt/aerovault
ExecStop=-/bin/umount /mnt/aerovault
ExecStop=-/usr/sbin/ubidetach -m 0

[Install]
WantedBy=multi-user.target
UNIT
cat /etc/systemd/system/aerovault.service

echo
echo "=== 4. fstab: noauto, because the service owns the mount now ==="
mkdir -p "$MNT"
sed -i "\|^$VOL |d" /etc/fstab
echo "$VOL $MNT ubifs noauto,nofail 0 0" >> /etc/fstab
grep -n aerovault /etc/fstab

echo
echo "=== 5. reload and prove it works NOW, before trusting it to a reboot ==="
udevadm control --reload-rules
systemctl daemon-reload
systemctl enable aerovault.service
umount "$MNT" 2>/dev/null && echo "(unmounted for the test)"
ubidetach -m 0 2>/dev/null && echo "(detached for the test)"
systemctl restart aerovault.service
systemctl is-active aerovault.service
df -h "$MNT" | tail -1
