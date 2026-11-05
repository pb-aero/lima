#!/usr/bin/env bash
# RUN ON THE AERONODE CM5.  Changes nothing.  Answers the four questions the
# hwdef cannot answer from a schematic, and prints the lines to paste into it.
#
#   ./discover-buses.sh
set -uo pipefail

hr() { printf '\n--- %s ---\n' "$*"; }

hr "1. is this board detected as a Pi 5 by ArduPilot's rule?"
# ArduPilot reads bytes 4-7 of /proc/device-tree/soc*/ranges.  0x10 => RPI_5.
for r in /proc/device-tree/soc*/ranges; do
  [ -e "$r" ] || continue
  echo "node   : $r"
  echo -n "bytes  : "; od -An -tx1 -N16 "$r"
  b=$(od -An -tx1 -N8 "$r" | awk '{print $5$6$7$8}')
  echo "base   : 0x$b"
  case "$b" in
    00000010) echo "verdict: 0x10 -> RPI_5    GOOD" ;;
    *)        echo "verdict: NOT 0x10 -> UNKNOWN_BOARD; GPIO_RPI::init() will panic" ;;
  esac
done
# The node is named soc@107c000000 on every 2712 kernel, which upstream's
# strncmp(d_name,"soc",4) does NOT match.  patches/0001 is mandatory.
echo "note   : node name above must be matched by a 3-char prefix compare -> patches/0001"

hr "2. spidev enumeration (THE hwdef LINUX_SPIDEV numbers)"
ls -l /dev/spidev* 2>/dev/null || echo "NO /dev/spidev* -- enable SPI in config.txt first (see config/)"

hr "3. i2c buses + what answers on each"
ls -l /dev/i2c-* 2>/dev/null || echo "NO /dev/i2c-* -- enable I2C in config.txt first"
command -v i2cdetect >/dev/null || { echo "install: sudo apt install -y i2c-tools"; }
for d in /dev/i2c-*; do
  n=${d#/dev/i2c-}
  echo "== i2c-$n =="
  i2cdetect -y "$n" 2>/dev/null || echo "   (scan failed)"
done
cat <<'EXPECT'
   expected on the AeroNode rev 0.0.2 (vendor schematic HW 0.0.2 rev 1):
     0x30  MMC5983MA magnetometer   (product ID reg 0x2F reads 0x30)
     0x46  BMP581 barometer         (or 0x47)
     0x76  BMP390 barometer         (or 0x77, via the BMP388 driver)
     0x48  ADS1115 (CO chain)       -- not an ArduPilot flight sensor
     0x76/0x77 may collide with BME690; check which part answers
EXPECT

hr "4. WHO_AM_I on the AeroImu island, over spidev"
cat <<'WAI'
   ICM-45686      expect 0xE9   -> supported (AP_InertialSensor_Invensensev3)
   LSM6DSV320X    expect 0x73   -> NOT supported: the ArduPilot LSM6DSV driver
                                   accepts only 0x70 (DSV16X/DSV32X) and
                                   0x75 (LSM6DSK320X, a DIFFERENT ST part).
                                   See README section 5.
   Read it with:  scripts/whoami-spi.py <spidev> <reg>
WAI

hr "5. paste-ready hwdef line"
for s in /dev/spidev*; do
  [ -e "$s" ] || continue
  bs=${s#/dev/spidev}; bus=${bs%%.*}; sub=${bs##*.}
  echo "LINUX_SPIDEV \"icm45686\" $bus $sub SPI_MODE_0 8 SPI_CS_KERNEL 4*MHZ 10*MHZ   # from $s"
done
echo
echo "Confirm WHICH spidev the island is actually on (step 4) before using any line above."
