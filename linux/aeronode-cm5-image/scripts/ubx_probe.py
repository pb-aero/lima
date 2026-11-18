#!/usr/bin/env python3
"""Debug: send UBX polls (MON-VER, NAV-STATUS, VALGET rate) and report every UBX frame that comes back.
usage: ubx_probe.py [port] [baud]   Reads only; the polls change nothing."""
import struct
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 38400


def ubx(cls, mid, payload=b""):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


polls = {"MON-VER": ubx(0x0A, 0x04), "NAV-STATUS": ubx(0x01, 0x03),
         "VALGET rate": ubx(0x06, 0x8B, struct.pack("<BBHI", 0, 0, 0, 0x30210001))}
with serial.Serial(port, baud, timeout=0.1) as s:
    for name, msg in polls.items():
        s.reset_input_buffer()
        s.write(msg)
        s.flush()
        buf = b""
        t0 = time.time()
        while time.time() - t0 < 2.0:
            buf += s.read(4096)
        frames = []
        i = buf.find(b"\xb5\x62")
        while i >= 0 and len(buf) >= i + 6:
            frames.append(f"{buf[i+2]:02x}-{buf[i+3]:02x} len {struct.unpack_from('<H', buf, i+4)[0]}")
            i = buf.find(b"\xb5\x62", i + 2)
        print(f"{name:12s} sent {msg.hex()}  -> {len(buf)} B back, UBX frames: {frames or 'none'}")
