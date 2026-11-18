#!/usr/bin/env python3
"""Read-only I2C checks on /dev/i2c-1: scan by 1-byte read, then BMP581 CHIP_ID x N.

Writes only the register POINTER byte (a read of reg 0x01), never a register value.
"""
import fcntl
import os
import sys

I2C_SLAVE = 0x0703
BUS = "/dev/i2c-1"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 10

fd = os.open(BUS, os.O_RDWR)
found = []
for addr in range(0x08, 0x78):
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        os.read(fd, 1)
        found.append(addr)
    except OSError:
        pass
print("scan:", " ".join(f"0x{a:02x}" for a in found))

ok = 0
errs = {}
for _ in range(n):
    try:
        fcntl.ioctl(fd, I2C_SLAVE, 0x46)
        os.write(fd, b"\x01")
        v = os.read(fd, 1)[0]
        if v == 0x50:
            ok += 1
        else:
            errs[f"0x{v:02x}"] = errs.get(f"0x{v:02x}", 0) + 1
    except OSError as e:
        errs[e.strerror] = errs.get(e.strerror, 0) + 1
print(f"BMP581 0x46 CHIP_ID==0x50: {ok}/{n}  other: {errs}")
