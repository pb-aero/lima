#!/usr/bin/env python3
"""Hold SPI0 busy at a slow clock so the CS/SCLK/MOSI pins can be sampled with pinctrl.

Proves the Pi END of the bus is really moving: with no scope, run this in the background and
sample `pinctrl get 8-11` — /CS must be seen LOW at least once, SCLK and MOSI must be seen
changing. If CS never reads low, the part is being ignored by the Pi, not the wiring.

Usage: ./spi-cs-activity.py [--seconds 8] [--speed 100000]
"""
import argparse, sys, time
import spidev

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=8.0)
ap.add_argument("--speed", type=int, default=100_000)
ap.add_argument("--bus", type=int, default=0)
ap.add_argument("--dev", type=int, default=0)
a = ap.parse_args()

spi = spidev.SpiDev()
spi.open(a.bus, a.dev)
spi.mode = 0
spi.bits_per_word = 8
spi.max_speed_hz = a.speed

block = [0xA5, 0x5A] * 512          # 1 KiB of transitions; ~80 ms at 100 kHz
end = time.time() + a.seconds
n = 0
while time.time() < end:
    spi.xfer2(list(block))
    n += len(block)
spi.close()
print(f"transferred {n} bytes at {a.speed} Hz over {a.seconds:g}s")
