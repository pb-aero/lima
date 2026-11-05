#!/usr/bin/env python3
"""Read one register over spidev.  RUN ON THE AERONODE CM5.

  ./whoami-spi.py 0.0 0x75        # ICM-45686 WHO_AM_I, expect 0xE9
  ./whoami-spi.py 0.1 0x0F        # LSM6DSV320X WHO_AM_I, expect 0x73

Both parts use the SPI convention: bit7 of the address byte set = read.
Prints the raw bytes, not an interpretation -- a wrong wiring and a wrong
chip look identical once you only print a verdict.
"""
import sys

try:
    import spidev
except ImportError:
    sys.exit("pip install spidev  (or: sudo apt install -y python3-spidev)")

if len(sys.argv) != 3:
    sys.exit(__doc__)

bus, _, dev = sys.argv[1].partition(".")
reg = int(sys.argv[2], 0)

spi = spidev.SpiDev()
spi.open(int(bus), int(dev or 0))
spi.max_speed_hz = 1_000_000
spi.mode = 0

tx = [reg | 0x80, 0x00]
rx = spi.xfer2(list(tx))
spi.close()

print(f"spidev{bus}.{dev or 0}  tx={[hex(b) for b in tx]}  rx={[hex(b) for b in rx]}")
print(f"register 0x{reg:02X} = 0x{rx[1]:02X}")
known = {0xE9: "ICM-45686 (supported)",
         0x73: "LSM6DSV320X (NOT supported by ArduPilot -- README section 5)",
         0x75: "LSM6DSK320X (supported)",
         0x70: "LSM6DSV16X or LSM6DSV32X (supported)"}
print("match   :", known.get(rx[1], "no known part -- suspect wiring, CS, or mode"))
