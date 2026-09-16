#!/usr/bin/env python3
"""Does the W25N01GV's BUSY bit ever read back as 1 on this Pi?

The kernel's spinand_write_page() is textbook-correct: write-enable, load cache, program, then
spinand_wait() polls REG_STATUS (0Fh C0h) until BUSY clears. If that poll never SEES busy, the
driver returns success immediately and the next page's WRITE ENABLE lands on a chip that is still
programming — and a busy chip discards it. That is exactly the observed alternating page loss.

This drives the chip by hand over spidev and answers the question directly: issue a block erase,
then poll status as fast as possible and report whether BUSY is ever observed set.

Needs the jedec,spi-nand overlay REMOVED so /dev/spidev0.0 exists.
DESTRUCTIVE to the one block erased (default block 400).
"""
import sys
import time

import spidev

BLOCK = int(sys.argv[1]) if len(sys.argv) > 1 else 400
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000

spi = spidev.SpiDev()
spi.open(0, 0)
spi.mode = 0
spi.bits_per_word = 8
spi.max_speed_hz = SPEED


def sr(addr):
    return spi.xfer2([0x0F, addr, 0x00])[2]


def wsr(addr, val):
    spi.xfer2([0x1F, addr, val])


jedec = spi.xfer2([0x9F, 0, 0, 0, 0])[2:]
print("JEDEC:", " ".join(f"{b:02X}" for b in jedec))
if jedec != [0xEF, 0xAA, 0x21]:
    sys.exit("part not responding — is the overlay still bound to CE0?")

print(f"SR-1 before unlock : 0x{sr(0xA0):02X}")
wsr(0xA0, 0x00)
print(f"SR-1 after  unlock : 0x{sr(0xA0):02X}   (0x00 = whole array writable)")
print(f"SR-2 config        : 0x{sr(0xB0):02X}")
print(f"SR-3 status        : 0x{sr(0xC0):02X}")

spi.xfer2([0x06])                      # WRITE ENABLE
s3 = sr(0xC0)
print(f"\nafter WRITE ENABLE : SR-3 = 0x{s3:02X}  WEL={(s3 >> 1) & 1}  (WEL must be 1)")

page = BLOCK * 64
print(f"\nBLOCK ERASE block {BLOCK} (page address 0x{page:04X}) — then poll BUSY flat out")
t0 = time.perf_counter()
spi.xfer2([0xD8, 0x00, (page >> 8) & 0xFF, page & 0xFF])

busy_seen = 0
polls = 0
first_busy_us = None
while True:
    s = sr(0xC0)
    polls += 1
    if s & 0x01:
        busy_seen += 1
        if first_busy_us is None:
            first_busy_us = (time.perf_counter() - t0) * 1e6
    elif busy_seen:
        break
    if (time.perf_counter() - t0) > 0.5:
        break
elapsed_us = (time.perf_counter() - t0) * 1e6

print(f"  polls issued     : {polls}")
print(f"  polls showing BUSY: {busy_seen}")
print(f"  first BUSY seen at: {first_busy_us if first_busy_us is not None else '—'} us")
print(f"  total elapsed     : {elapsed_us:.0f} us")
s3 = sr(0xC0)
print(f"  final SR-3        : 0x{s3:02X}  E-FAIL={(s3 >> 2) & 1}")

print()
if busy_seen:
    print("BUSY IS OBSERVABLE. The chip reports busy and the status path works, so the kernel's")
    print("spinand_wait() should see it too — the alternating page loss is NOT a blind status read.")
else:
    print("*** BUSY NEVER OBSERVED *** — the erase takes milliseconds, so the status read is not")
    print("reflecting the chip's real state. That is the mechanism: the kernel's wait returns")
    print("instantly, the next WRITE ENABLE hits a busy chip and is discarded, and that page is")
    print("silently skipped.")
spi.close()
