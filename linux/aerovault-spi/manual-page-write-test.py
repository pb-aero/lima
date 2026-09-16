#!/usr/bin/env python3
"""Drive the W25N01GV by hand over spidev, with a correct wait between pages.

The kernel loses every other page of a multi-page write. This bypasses the kernel's NAND stack
entirely and does the same job with an explicitly correct sequence:

    WRITE ENABLE -> PROGRAM LOAD (02h) -> PROGRAM EXECUTE (10h) -> poll BUSY until clear

If all eight pages land here, the chip, the harness and the SPI controller are all sound and the
fault is in the kernel write path. If they do not, the fault is lower down.

Needs the jedec,spi-nand overlay removed. DESTRUCTIVE to the one block used (default 410).
"""
import sys
import time

import spidev

BLOCK = int(sys.argv[1]) if len(sys.argv) > 1 else 410
SPEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
NPAGES = 8
PAGESZ = 2048

spi = spidev.SpiDev()
spi.open(0, 0)
spi.mode, spi.bits_per_word, spi.max_speed_hz = 0, 8, SPEED


def sr(addr):
    return spi.xfer2([0x0F, addr, 0x00])[2]


def wait_ready(timeout_s=1.0):
    """Poll until BUSY clears. Returns (status, microseconds_waited, polls)."""
    t0 = time.perf_counter()
    polls = 0
    while True:
        s = sr(0xC0)
        polls += 1
        if not (s & 0x01):
            return s, (time.perf_counter() - t0) * 1e6, polls
        if time.perf_counter() - t0 > timeout_s:
            return s, (time.perf_counter() - t0) * 1e6, polls


def write_enable():
    spi.xfer2([0x06])


def block_erase(page_addr):
    write_enable()
    spi.xfer2([0xD8, 0x00, (page_addr >> 8) & 0xFF, page_addr & 0xFF])
    return wait_ready()


def program_page(page_addr, data):
    write_enable()
    if not sr(0xC0) & 0x02:
        return None, "WEL not set — chip refused write enable"
    spi.xfer2([0x02, 0x00, 0x00] + list(data))        # PROGRAM LOAD, column 0
    spi.xfer2([0x10, 0x00, (page_addr >> 8) & 0xFF, page_addr & 0xFF])  # EXECUTE
    s, us, polls = wait_ready()
    return (s, us, polls), ("P-FAIL set" if s & 0x08 else None)


def read_page(page_addr, length=PAGESZ):
    spi.xfer2([0x13, 0x00, (page_addr >> 8) & 0xFF, page_addr & 0xFF])  # page -> cache
    wait_ready()
    return spi.xfer2([0x03, 0x00, 0x00, 0x00] + [0x00] * length)[4:]


jedec = spi.xfer2([0x9F, 0, 0, 0, 0])[2:]
if jedec != [0xEF, 0xAA, 0x21]:
    sys.exit(f"part not responding: {jedec}")
spi.xfer2([0x1F, 0xA0, 0x00])                          # unlock the array
print(f"JEDEC EF AA 21 · SR-1 = 0x{sr(0xA0):02X} · SR-2 = 0x{sr(0xB0):02X}\n")

base = BLOCK * 64
s, us, polls = block_erase(base)
print(f"erase block {BLOCK}: {us:.0f} us, {polls} polls, SR-3 = 0x{s:02X}, "
      f"E-FAIL={(s >> 2) & 1}")

pattern = [bytes(f"@{p:03d}-AEROVAULT-".encode()) for p in range(NPAGES)]
pages = [(pattern[p] * (PAGESZ // len(pattern[p]) + 1))[:PAGESZ] for p in range(NPAGES)]

print(f"\nprogramming {NPAGES} consecutive pages, waiting for BUSY after each:")
for p in range(NPAGES):
    res, err = program_page(base + p, pages[p])
    if res is None:
        print(f"  page {p}: {err}")
        continue
    s, us, polls = res
    print(f"  page {p}: {us:7.0f} us, {polls:3d} polls, SR-3 = 0x{s:02X}"
          + (f"  <-- {err}" if err else ""))

print("\nreading back:")
ok = 0
for p in range(NPAGES):
    got = bytes(read_page(base + p))
    if got == pages[p]:
        print(f"  page {p}: LANDED")
        ok += 1
    elif all(b == 0xFF for b in got):
        print(f"  page {p}: BLANK")
    else:
        print(f"  page {p}: WRONG — starts {got[:16].hex()}")
print(f"\n{ok} of {NPAGES} pages landed, driven by hand.")
spi.close()
