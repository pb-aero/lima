#!/usr/bin/env python3
"""Map the safe operating envelope: SPI clock vs required inter-transaction gap.

Drives the part by hand over spidev so the whole 2-D sweep costs ONE reboot instead of one per
combination. For each (clock, gap) it erases a block, programs 8 consecutive pages, and counts how
many actually landed. 8 of 8 is the pass mark; anything less is silent data loss.

Needs the jedec,spi-nand overlay removed. DESTRUCTIVE to the blocks it uses (from --first-block).
"""
import argparse
import time

import spidev

ap = argparse.ArgumentParser()
ap.add_argument("--first-block", type=int, default=500)
ap.add_argument("--pages", type=int, default=8)
ap.add_argument("--clocks", default="1,5,10,25,50", help="MHz, comma separated")
ap.add_argument("--gaps", default="0,10,50,100,200,300,500", help="microseconds, comma separated")
args = ap.parse_args()

CLOCKS = [int(float(c) * 1e6) for c in args.clocks.split(",")]
GAPS_US = [float(g) for g in args.gaps.split(",")]
PAGESZ = 2048

spi = spidev.SpiDev()
spi.open(0, 0)
spi.mode, spi.bits_per_word = 0, 8


def run(clock, gap_s, block):
    spi.max_speed_hz = clock

    def x(data):
        r = spi.xfer2(data)
        if gap_s:
            time.sleep(gap_s)
        return r

    def status():
        return x([0x0F, 0xC0, 0x00])[2]

    def ready(limit=1.0):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < limit:
            if not status() & 0x01:
                return True
        return False

    x([0x1F, 0xA0, 0x00])                       # unlock
    base = block * 64
    # Erase EVERY block the page range touches, not just the first. Writing into an un-erased
    # page fails and looks exactly like the fault being measured — an earlier version of this
    # script erased one block and reported a confident 128/256.
    nblocks = (args.pages + 63) // 64
    for b in range(nblocks):
        addr = (block + b) * 64
        x([0x06])
        x([0xD8, 0x00, (addr >> 8) & 0xFF, addr & 0xFF])
        ready()

    pats = []
    for p in range(args.pages):
        mark = f"@{p:03d}-AEROVAULT-".encode()
        pat = (mark * (PAGESZ // len(mark) + 1))[:PAGESZ]
        pats.append(pat)
        x([0x06])
        x([0x02, 0x00, 0x00] + list(pat))
        x([0x10, 0x00, ((base + p) >> 8) & 0xFF, (base + p) & 0xFF])
        ready()

    landed = 0
    for p in range(args.pages):
        x([0x13, 0x00, ((base + p) >> 8) & 0xFF, (base + p) & 0xFF])
        ready()
        got = bytes(x([0x03, 0x00, 0x00, 0x00] + [0] * PAGESZ)[4:])
        if got == pats[p]:
            landed += 1
    return landed


spi.max_speed_hz = 1_000_000          # the ID check must not inherit spidev's 125 MHz default
jedec = spi.xfer2([0x9F, 0, 0, 0, 0])[2:]
if jedec != [0xEF, 0xAA, 0x21]:
    raise SystemExit(f"part not responding: {jedec} — is the NAND overlay still bound?")

print(f"pages per cell: {args.pages}   (pass = {args.pages} of {args.pages})\n")
print("clock      " + "".join(f"{g:>7g}us" for g in GAPS_US))
print("-" * (11 + 9 * len(GAPS_US)))
block = args.first_block
best = {}
for clock in CLOCKS:
    row = f"{clock / 1e6:5.0f} MHz  "
    for gap in GAPS_US:
        n = run(clock, gap / 1e6, block)
        block += (args.pages + 63) // 64 + 1
        row += f"{n:>6}/{args.pages} " if n != args.pages else f"{'  PASS':>8} "
        if n == args.pages and clock not in best:
            best[clock] = gap
    print(row)

print()
for clock in CLOCKS:
    if clock in best:
        print(f"  {clock / 1e6:>5.0f} MHz : smallest gap that passes = {best[clock]} us")
    else:
        print(f"  {clock / 1e6:>5.0f} MHz : no gap in the sweep passed")
spi.close()
