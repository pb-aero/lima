#!/usr/bin/env python3
"""Test: is BMP581 INT_STATUS.por (0x27 bit4) consumed by a prior read, and restored by soft reset?

Reads 0x27 twice (clear-on-read), then writes CMD 0x7E = 0xB6 (soft reset) only if argv[1]=='reset',
then reads 0x27 and STATUS 0x28.
"""
import fcntl
import os
import sys
import time

fd = os.open("/dev/i2c-1", os.O_RDWR)
fcntl.ioctl(fd, 0x0703, 0x46)


def rd(reg):
    os.write(fd, bytes([reg]))
    return os.read(fd, 1)[0]


print(f"INT_STATUS 0x27 read 1: 0x{rd(0x27):02x}")
print(f"INT_STATUS 0x27 read 2: 0x{rd(0x27):02x}")
print(f"STATUS     0x28       : 0x{rd(0x28):02x}  (bit1 nvm_rdy, bit2 nvm_err)")
if len(sys.argv) > 1 and sys.argv[1] == "reset":
    os.write(fd, bytes([0x7E, 0xB6]))
    time.sleep(0.005)
    print("soft reset written (0x7E <- 0xB6), waited 5 ms")
    print(f"INT_STATUS 0x27 after : 0x{rd(0x27):02x}  (want bit4 0x10 set)")
    print(f"INT_STATUS 0x27 again : 0x{rd(0x27):02x}  (clear-on-read: want 0x00)")
    print(f"STATUS     0x28 after : 0x{rd(0x28):02x}")
    print(f"CHIP_ID    0x01 after : 0x{rd(0x01):02x}")
