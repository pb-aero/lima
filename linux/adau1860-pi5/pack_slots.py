#!/usr/bin/env python3
"""Stream mono S32_LE on stdin -> 4-slot S32_LE frames on stdout, for the ADAU1860.

WHY SLOTS 0 AND 2: RP1 will not lock to the codec's narrow TDM frame sync, so the
codec runs SAI_MODE=STEREO and a stereo receiver takes only the first 32-bit word
after each LRCLK edge. Of the four words the Pi transmits, only two ever arrive
(measured by ear 2026-09-07, commit 91b0e9e):

    codec channel 0  <- Pi slot 0        Pi slot 1 -> discarded
    codec channel 1  <- Pi slot 2        Pi slot 3 -> discarded

Mono therefore goes to slots 0 AND 2 so both codec channels get it. aplay must
still be told -c 4: the transport is four words wide whatever lands.

Streaming, so the gain is FIXED, not peak-normalised -- there is no future to look
at. Piper already normalises its output, so -6 dB of headroom is a straight halving.
"""
import argparse, sys
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("--gain-db", type=float, default=-6.0, help="fixed gain; headphones downstream")
p.add_argument("--chunk", type=int, default=4096, help="frames per read")
a = p.parse_args()

g = 10.0 ** (a.gain_db / 20.0)
inp, out = sys.stdin.buffer, sys.stdout.buffer
frames = 0
while True:
    buf = inp.read(a.chunk * 4)
    if not buf:
        break
    mono = np.frombuffer(buf[: len(buf) // 4 * 4], dtype="<i4")
    # scale in float64: int32 * gain overflows int32 on anything above -0 dB
    mono = np.clip(mono.astype(np.float64) * g, -2147483648, 2147483647).astype("<i4")
    quad = np.zeros((mono.size, 4), dtype="<i4")
    quad[:, 0] = mono      # slot 0 -> codec channel 0
    quad[:, 2] = mono      # slot 2 -> codec channel 1
    out.write(quad.tobytes())
    frames += mono.size
out.flush()
print(f"packed {frames} frames ({frames/48000:.2f} s at 48 kHz) gain {a.gain_db:+.1f} dB",
      file=sys.stderr)
