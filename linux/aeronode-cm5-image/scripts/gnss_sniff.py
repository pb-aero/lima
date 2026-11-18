#!/usr/bin/env python3
"""Read-only GNSS sniff: listen on a serial port at several bauds; count NMEA/UBX framing.

usage: gnss_sniff.py [/dev/ttyAMA0] [secs_per_baud]
Never writes to the port.
"""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 2.5
for baud in (38400, 9600, 115200, 230400, 57600):
    with serial.Serial(port, baud, timeout=0.2) as s:
        s.reset_input_buffer()
        buf = b""
        t0 = time.time()
        while time.time() - t0 < secs:
            buf += s.read(4096)
    nmea = buf.count(b"$G")
    ubx = buf.count(b"\xb5\x62")
    printable = sum(32 <= c < 127 or c in (10, 13) for c in buf) / max(len(buf), 1)
    print(f"{baud:6d} baud: {len(buf):5d} B  NMEA '$G' {nmea:3d}  UBX sync {ubx:3d}  printable {printable:.0%}")
    if nmea:
        lines = [ln for ln in buf.split(b"\r\n") if ln.startswith(b"$G")]
        for ln in lines[:8]:
            print("   ", ln[:90].decode("ascii", "replace"))
