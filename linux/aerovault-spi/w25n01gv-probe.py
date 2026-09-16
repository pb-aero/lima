#!/usr/bin/env python3
"""W25N01GV (Flash 5 Click) probe over spidev — READ-ONLY. Programs nothing, erases nothing.

Step 2 of AeroVault bring-up: prove the part answers on the wire before handing it to the
kernel's spi-nand/MTD driver. Everything here is a read; the array is never touched.

Usage:  ./w25n01gv-probe.py [--bus 0] [--dev 0] [--speed 1000000]
Exit:   0 = the part identified itself correctly
        1 = wrong/absent ID (see the printed diagnosis)
        2 = could not run the test at all
"""
import argparse
import sys

try:
    import spidev
except ImportError:
    print("FATAL: python3-spidev not installed", file=sys.stderr)
    sys.exit(2)

JEDEC_EXPECT = [0xEF, 0xAA, 0x21]          # Winbond mfr EFh, device AAh 21h  [datasheet 9.1]
SR_ADDR = {"SR-1 protection": 0xA0, "SR-2 configuration": 0xB0, "SR-3 status": 0xC0}


def read_jedec(spi):
    """9Fh + 8 dummy clocks -> EFh AAh 21h."""
    return spi.xfer2([0x9F, 0x00, 0x00, 0x00, 0x00])[2:]


def read_sr(spi, addr):
    """0Fh <addr> -> one status byte."""
    return spi.xfer2([0x0F, addr, 0x00])[2]


def decode_sr1(v):
    bp = (v >> 3) & 0x0F
    tb = (v >> 2) & 1
    out = [f"BP3-0={bp:04b} TB={tb}", f"WP-E={(v >> 1) & 1}", f"SRP0={(v >> 7) & 1}"]
    if bp:
        out.append("** ARRAY IS WRITE-PROTECTED — this is the power-up default, not a fault. "
                   "Clear SR-1 (write 0x00 to A0h) before any program or erase.")
    return out


def decode_sr2(v):
    buf = (v >> 3) & 1
    return [f"BUF={buf} ({'buffer read — IG default' if buf else 'CONTINUOUS read — IT default'})",
            f"ECC-E={(v >> 4) & 1} ({'on-die ECC enabled' if (v >> 4) & 1 else 'ECC OFF'})",
            f"OTP-E={(v >> 6) & 1} SR1-L={(v >> 0) & 1}"]


def decode_sr3(v):
    ecc = (v >> 4) & 0x03
    meaning = {0: "no errors", 1: "1-bit corrected", 2: "UNCORRECTABLE", 3: "multi-page errors"}
    return [f"BUSY={v & 1} WEL={(v >> 1) & 1}",
            f"E-FAIL={(v >> 2) & 1} P-FAIL={(v >> 3) & 1}",
            f"ECC-1/0={ecc:02b} ({meaning[ecc]})", f"LUT-F={(v >> 6) & 1}"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", type=int, default=0)
    ap.add_argument("--dev", type=int, default=0)
    ap.add_argument("--speed", type=int, default=1_000_000, help="start slow; the part does 104 MHz")
    ap.add_argument("--mode", type=int, default=0, choices=[0, 3], help="W25N supports mode 0 and mode 3")
    args = ap.parse_args()

    spi = spidev.SpiDev()
    try:
        spi.open(args.bus, args.dev)
    except OSError as exc:
        print(f"FATAL: cannot open /dev/spidev{args.bus}.{args.dev}: {exc}", file=sys.stderr)
        return 2
    spi.mode = args.mode
    spi.bits_per_word = 8
    spi.max_speed_hz = args.speed

    jedec = read_jedec(spi)
    got = " ".join(f"{b:02X}" for b in jedec)
    print(f"mode {args.mode}, {args.speed / 1000:g} kHz")
    print(f"JEDEC ID (9Fh + dummy) : {got}   expected EF AA 21")

    if jedec == JEDEC_EXPECT:
        print("  -> W25N01GV identified. 1 Gbit SLC NAND, 2048+64 B page, 64 pages/block, 1024 blocks.")
    elif not any(jedec):
        print("  -> ALL ZERO. Nothing is driving MISO: check power, the CS wire, and that a chip\n"
              "     select actually exists (dtoverlay=spi0-0cs drives NO CS at all).")
        spi.close()
        return 1
    elif all(b == 0xFF for b in jedec):
        print("  -> ALL ONES. MISO idling high with nothing answering: part unpowered or MISO open.")
        spi.close()
        return 1
    else:
        print("  -> WRONG ID. Something answered but it is not a W25N01GV, or the clock/mode is wrong.")
        spi.close()
        return 1

    print()
    for name, addr in SR_ADDR.items():
        v = read_sr(spi, addr)
        decode = {0xA0: decode_sr1, 0xB0: decode_sr2, 0xC0: decode_sr3}[addr]
        print(f"{name} (0Fh {addr:02X}h) = 0x{v:02X}")
        for line in decode(v):
            print(f"    {line}")
    spi.close()
    print("\nRead-only probe complete. Nothing was written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
