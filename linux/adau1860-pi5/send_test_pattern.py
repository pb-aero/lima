#!/usr/bin/env python3
"""
Generate a TDM test pattern for proving samples reach the ADAU1860.

Emits raw interleaved S32_LE frames on stdout, for piping into aplay:

    python3 send_test_pattern.py --seconds 10 \
      | aplay -D hw:$CARD,0 -f S32_LE -c 4 -r 48000 -t raw   # $CARD from `aplay -l`

Slot layout (matches adau1860-pi5-tx-overlay.dts, TDM4):
    slot 0  sine at --tone Hz          <- this is the one the DAC plays
    slot 1  half-amplitude sine, 90 deg out of phase
    slot 2  slow ramp, one sweep per second
    slot 3  0xA5 << 24 | (seq & 0xFFFFFF)   <- framing / slip detector

Amplitude defaults to -12 dBFS, deliberately. Sitting at full scale means any
gain above unity in the chip saturates, and saturation looks like a plausible
flattened peak rather than an obvious fault.

Use --check to read the pattern back instead (from arecord on stdin) and
report slot alignment and lost frames.
"""

import argparse
import math
import struct
import sys

MAGIC = 0xA5


def generate(args):
    out = sys.stdout.buffer
    amp = int(2**31 * (10 ** (args.dbfs / 20.0)))
    total = int(args.rate * args.seconds)
    w = 2 * math.pi * args.tone / args.rate
    ramp_period = args.rate
    buf = bytearray()
    for n in range(total):
        s0 = int(amp * math.sin(w * n))
        s1 = int(amp / 2 * math.cos(w * n))
        s2 = int(-2**31 + (2**32 - 1) * ((n % ramp_period) / ramp_period))
        s3 = (MAGIC << 24) | (n & 0xFFFFFF)
        # slot 3 is a bit pattern, not a signal: reinterpret as signed
        s3 = struct.unpack("<i", struct.pack("<I", s3 & 0xFFFFFFFF))[0]
        buf += struct.pack("<4i", s0, s1, s2, s3)
        if len(buf) >= 65536:
            out.write(buf)
            buf = bytearray()
    if buf:
        out.write(buf)


def check(args):
    """Read interleaved S32_LE frames on stdin and verify slot 3."""
    data = sys.stdin.buffer.read()
    frame = 16  # 4 slots x 4 bytes
    n = len(data) // frame
    if n == 0:
        sys.exit("no frames on stdin")

    # Which slot actually carries the magic? If it is not slot 3, the link
    # slipped and every axis is permuted.
    votes = [0] * 4
    for i in range(min(n, 2000)):
        for s in range(4):
            v, = struct.unpack_from("<I", data, i * frame + s * 4)
            if (v >> 24) == MAGIC:
                votes[s] += 1
    best = max(range(4), key=lambda s: votes[s])
    if votes[best] == 0:
        sys.exit("FAIL: magic byte 0xA5 not found in any slot. Either nothing "
                 "arrived, the slot width/count is wrong, or the data was "
                 "converted on the way (plughw? a resampler?).")
    print(f"magic found in slot {best} ({votes[best]} of {min(n,2000)} frames)")
    if best != 3:
        print(f"*** SLIPPED by {(3 - best) % 4} slots -- your axes are permuted ***")

    prev, lost, checked = None, 0, 0
    for i in range(n):
        v, = struct.unpack_from("<I", data, i * frame + best * 4)
        if (v >> 24) != MAGIC:
            continue
        seq = v & 0xFFFFFF
        if prev is not None:
            gap = (seq - prev) & 0xFFFFFF
            if gap != 1:
                lost += gap - 1
        prev = seq
        checked += 1
    print(f"frames checked: {checked}, frames lost: {lost}")
    print("PASS -- samples arrived intact" if lost == 0 and best == 3
          else "PROBLEM -- see above")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=int, default=48000)
    ap.add_argument("--tone", type=float, default=1000.0)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--dbfs", type=float, default=-12.0)
    ap.add_argument("--check", action="store_true",
                    help="read frames on stdin and verify, instead of generating")
    args = ap.parse_args()
    check(args) if args.check else generate(args)


if __name__ == "__main__":
    main()
