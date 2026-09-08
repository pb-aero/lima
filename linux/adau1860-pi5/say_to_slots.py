#!/usr/bin/env python3
"""Turn a mono 32-bit 48 kHz WAV into the 4-slot S32_LE raw frame the ADAU1860 eats.

WHY THE PACKING IS NOT OBVIOUS: RP1 refuses the codec's narrow TDM frame sync, so the
codec runs SAI_MODE=STEREO. A stereo receiver takes only the first 32-bit word after
each LRCLK edge, so of the four words the Pi transmits, only slots 0 and 2 ever arrive
(measured by ear 2026-09-07, commit 91b0e9e):

    codec channel 0  <- Pi slot 0
    codec channel 1  <- Pi slot 2
    Pi slots 1 and 3 -> discarded on the wire

So mono speech goes into slots 0 AND 2 (both ears), zeros elsewhere. aplay must still
be told -c 4: the transport is four words wide even though two of them land nowhere.
"""
import struct, sys, wave, argparse

p = argparse.ArgumentParser()
p.add_argument("wav"); p.add_argument("out")
p.add_argument("--peak-dbfs", type=float, default=-6.0,
               help="normalise speech peak to this level (headphones are on the other end)")
a = p.parse_args()

with wave.open(a.wav, "rb") as w:
    assert w.getnchannels() == 1, f"expected mono, got {w.getnchannels()}ch"
    assert w.getsampwidth() == 4, f"expected 32-bit, got {w.getsampwidth()*8}-bit"
    assert w.getframerate() == 48000, f"expected 48 kHz, got {w.getframerate()}"
    n = w.getnframes()
    mono = list(struct.unpack(f"<{n}i", w.readframes(n)))

peak = max(abs(v) for v in mono) or 1
target = int((10 ** (a.peak_dbfs / 20.0)) * 0x7FFFFFFF)
g = target / peak
mono = [int(v * g) for v in mono]

with open(a.out, "wb") as f:
    for v in mono:
        f.write(struct.pack("<iiii", v, 0, v, 0))   # slot0, -, slot2, -

print(f"{n} frames  {n/48000:.2f} s  peak {20*__import__('math').log10(peak/0x7FFFFFFF):.1f} "
      f"-> {a.peak_dbfs:.1f} dBFS  gain x{g:.2f}  wrote {n*16} bytes")
