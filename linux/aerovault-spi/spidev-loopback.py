#!/usr/bin/env python3
"""spidev loopback test — Raspberry Pi 5, SPI0 (MOSI GPIO10 / MISO GPIO9 / SCLK GPIO11).

Physical loopback: jumper header pin 19 (GPIO10, MOSI) to pin 21 (GPIO9, MISO).

Run it TWICE and keep both results:
  * jumper OFF -> NEGATIVE CONTROL. Every read must come back all-zero. If it
    "passes" with no wire fitted, the test is measuring nothing and is worthless.
  * jumper ON  -> POSITIVE CONTROL. Every byte sent must come back identical.

Usage:  ./spidev-loopback.py [--bus 0] [--dev 0] [--expect wired|open]
Exit:   0 = result matched --expect (or no --expect given and the bus opened)
        1 = mismatch / corruption
        2 = could not run the test at all (instrument fault, not a result)
"""
import argparse
import os
import random
import sys

try:
    import spidev
except ImportError:
    print("FATAL: python3-spidev not installed (apt install python3-spidev)", file=sys.stderr)
    sys.exit(2)

SPEEDS = [100_000, 1_000_000, 5_000_000, 10_000_000, 25_000_000, 50_000_000]


def patterns():
    """(name, bytes) — each probes a different failure mode."""
    yield "zeros      ", [0x00] * 16
    yield "ones       ", [0xFF] * 16
    yield "alt AA/55  ", [0xAA, 0x55] * 8
    yield "walking one", [1 << (i % 8) for i in range(16)]
    yield "ramp       ", list(range(256))
    rnd = random.Random(20260915)
    yield "random 4k  ", [rnd.randrange(256) for _ in range(4096)]


def describe(spi, bus, dev):
    print(f"device      : /dev/spidev{bus}.{dev}")
    print(f"mode        : {spi.mode}")
    print(f"bits/word   : {spi.bits_per_word}")
    print(f"max speed   : {spi.max_speed_hz} Hz")
    print(f"lsbfirst    : {spi.lsbfirst}")
    # py-spidev exposes SPI_LOOP (0x20) as its own attribute; mode is 0-3 only.
    try:
        spi.loop = True
        supported = bool(spi.loop)
        spi.loop = False
    except (OSError, TypeError) as exc:
        print(f"SPI_LOOP    : rejected by driver ({exc}) - physical jumper required")
    else:
        print(f"SPI_LOOP    : {'ACCEPTED - internal loopback available' if supported else 'silently ignored - physical jumper required'}")
    print()


def run(spi, speed):
    """Return (all_ok, all_zero, first_failure_text)."""
    ok, zero, first = True, True, None
    spi.max_speed_hz = speed
    for name, tx in patterns():
        rx = spi.xfer2(list(tx))
        if any(rx):
            zero = False
        if rx != list(tx):
            ok = False
            if first is None:
                bad = next(i for i, (a, b) in enumerate(zip(tx, rx)) if a != b)
                first = (f"{name.strip()}: byte {bad} sent 0x{tx[bad]:02X} got 0x{rx[bad]:02X}"
                         f" ({sum(1 for a, b in zip(tx, rx) if a != b)}/{len(tx)} bytes differ)")
    return ok, zero, first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", type=int, default=0)
    ap.add_argument("--dev", type=int, default=0)
    ap.add_argument("--expect", choices=["wired", "open"], default=None,
                    help="wired = jumper fitted (positive control); open = no jumper (negative control)")
    ap.add_argument("--internal-loop", action="store_true",
                    help="set SPI_LOOP (controller shift-register loopback) instead of relying on a wire")
    args = ap.parse_args()

    node = f"/dev/spidev{args.bus}.{args.dev}"
    if not os.path.exists(node):
        print(f"FATAL: {node} does not exist — is dtparam=spi=on set?", file=sys.stderr)
        return 2

    spi = spidev.SpiDev()
    try:
        spi.open(args.bus, args.dev)
    except (OSError, PermissionError) as exc:
        print(f"FATAL: cannot open {node}: {exc} — is this user in group 'spi'?", file=sys.stderr)
        return 2

    spi.mode = 0
    spi.bits_per_word = 8
    describe(spi, args.bus, args.dev)
    if args.internal_loop:
        try:
            spi.loop = True
        except OSError as exc:
            print(f"FATAL: this controller refuses SPI_LOOP ({exc}) — it has no internal "
                  "loopback. Fit the jumper and run without --internal-loop.", file=sys.stderr)
            spi.close()
            return 2
        print("SPI_LOOP set — data that returns now never left the controller.\n")

    print(f"{'clock':>12}  {'result':<10} detail")
    print(f"{'-' * 12}  {'-' * 10} {'-' * 48}")
    results = {}
    for speed in SPEEDS:
        try:
            ok, zero, first = run(spi, speed)
        except OSError as exc:
            print(f"{speed / 1e6:9.1f} MHz  {'ERROR':<10} {exc}")
            results[speed] = "error"
            continue
        if ok:
            verdict, detail = "ECHO", "every byte returned identical"
        elif zero:
            verdict, detail = "ALL-ZERO", ("SPI_LOOP accepted but INERT — no internal loop"
                                          if args.internal_loop else "nothing on MISO — open circuit (no jumper)")
        else:
            verdict, detail = "CORRUPT", first
        results[speed] = verdict.lower()
        print(f"{speed / 1e6:9.1f} MHz  {verdict:<10} {detail}")
    spi.close()

    echoed = [s for s, v in results.items() if v == "echo"]
    zeros = [s for s, v in results.items() if v == "all-zero"]
    print()
    if args.expect == "open":
        if len(zeros) == len(SPEEDS):
            print("NEGATIVE CONTROL PASS — open bus reads all-zero at every clock, as it must.")
            return 0
        print("NEGATIVE CONTROL FAIL — an unwired bus returned data. Do not trust the positive run.")
        return 1
    if args.expect == "wired":
        if len(echoed) == len(SPEEDS):
            print(f"POSITIVE CONTROL PASS — clean echo to {max(echoed) / 1e6:.0f} MHz.")
            return 0
        if echoed:
            print(f"PARTIAL — clean to {max(echoed) / 1e6:.0f} MHz, fails above. "
                  "That is a wiring/signal-integrity ceiling, not a driver fault.")
        else:
            print("POSITIVE CONTROL FAIL — no echo at any clock. Check the jumper (pin 19 to pin 21).")
        return 1
    print(f"echo at: {[f'{s / 1e6:.0f}M' for s in echoed] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
