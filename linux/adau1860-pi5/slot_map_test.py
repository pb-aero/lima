#!/usr/bin/env python3
"""Settle which Pi transmit slot the ADAU1860 latches as which channel.

    python3 slot_map_test.py            # generate + sweep, listen on P30
    python3 slot_map_test.py --secs 4   # longer bursts

Why by ear and not by loopback: SPT0_ROUTE*'s source list is FastDSP / TDSP /
ASRC / ADC / DMIC / decimator / EQ -- it has NO serial-port input, so the chip
cannot be made to echo received slots back to the Pi. `DAC_ROUTE0` reading a
serial-port channel directly is the only path from a received slot to anything
observable, and the only observation point is the analog output.

The 2026-09-02 note proposed distinct DC values per slot. DC is inaudible, so
this uses a distinct TONE per slot instead -- octaves apart, so which one is
playing is unmistakable without an instrument:

    Pi slot 0 -> 250 Hz      Pi slot 2 -> 1000 Hz
    Pi slot 1 -> 500 Hz      Pi slot 3 -> 2000 Hz

DAC_ROUTE0 is then pointed at Serial Port 0 Channel 0, 1, 2, 3 in turn. What you
hear at each step IS the mapping.

  All four in order 250/500/1000/2000  -> the codec latches all four slots and
                                          channel N == Pi slot N. TDM-like.
  250 then 1000, then silence/noise    -> STEREO framing latching only the two
                                          half-frame heads: channel 0 = slot 0,
                                          channel 1 = slot 2, slots 1 and 3
                                          DISCARDED. This is the hypothesis from
                                          RESULTS-2026-09-02.md.
  anything else                        -> write down exactly what you heard; the
                                          mapping is neither of the above.

ROUTE ENCODING IS PART-SPECIFIC AND THIS IS A TRAP. In ADI's Lark SDK the plain
ADAU1860 (LARK_SDK) has SAI0_00..15 = 0..15, so route 0 IS serial port 0 channel
0. The ADAU1860-1 (LARK_LITE_SDK) uses a DIFFERENT map in the SAME register:
ADC0=0, ADC1=1, ADC2=2, and SAI0_00 does not start until 21. Same datasheet, same
register address, different meaning. The H1 cups use the -1; this bench board
behaves as the plain part (audio does come out of route 0), but the ID registers
do not appear to distinguish them, so a design targeting the -1 must re-derive
this table. `[gap]`
"""
import argparse, math, struct, subprocess, sys, time
from smbus2 import SMBus, i2c_msg

ADDR, DAC_ROUTE0 = 0x67, 0x4000C053
TONES = (250.0, 500.0, 1000.0, 2000.0)
RATE, SLOTS = 48000, 4


def wr(bus, reg, val):
    bus.i2c_rdwr(i2c_msg.write(ADDR, reg.to_bytes(4, "big") + bytes([val])))


def rd(bus, reg):
    w = i2c_msg.write(ADDR, reg.to_bytes(4, "big")); q = i2c_msg.read(ADDR, 1)
    bus.i2c_rdwr(w, q); return list(q)[0]


def make(path, secs, dbfs):
    amp = int(2 ** 31 * (10 ** (dbfs / 20.0)))
    n = int(RATE * secs)
    w = [2 * math.pi * f / RATE for f in TONES]
    buf = bytearray()
    for i in range(n):
        buf += struct.pack("<4i", *(int(amp * math.sin(wk * i)) for wk in w))
    open(path, "wb").write(buf)
    return n


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--secs", type=float, default=3.0)
    p.add_argument("--gap", type=float, default=1.2)
    p.add_argument("--dbfs", type=float, default=-6.0)
    p.add_argument("--dev", default="hw:0,0")
    p.add_argument("--bus", type=int, default=1)
    a = p.parse_args()

    path = "/tmp/slotmap.raw"
    make(path, a.secs, a.dbfs)
    print(f"# slot tones: " + ", ".join(f"slot {i} = {f:.0f} Hz" for i, f in enumerate(TONES)))
    print(f"# {a.secs:.0f} s per step, {a.gap:.1f} s gap. Listen on P30.\n")
    with SMBus(a.bus) as bus:
        for ch in range(4):
            wr(bus, DAC_ROUTE0, ch)
            back = rd(bus, DAC_ROUTE0)
            print(f"--- step {ch + 1}/4: DAC_ROUTE0 = {back}  (Serial Port 0 Channel {ch})",
                  flush=True)
            t = time.time()
            subprocess.run(["aplay", "-D", a.dev, "-f", "S32_LE", "-c", str(SLOTS),
                            "-r", str(RATE), "-t", "raw", path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"    played {time.time() - t:.2f} s -- what did you hear?", flush=True)
            time.sleep(a.gap)
        wr(bus, DAC_ROUTE0, 0)
    print("\n# DAC_ROUTE0 restored to 0. Report the four answers in order.")


if __name__ == "__main__":
    main()
