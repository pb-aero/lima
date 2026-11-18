#!/usr/bin/env python3
"""Compare the GNSS receiver's own uptime (UBX-NAV-STATUS msss) with Linux uptime.

usage: ubx_uptime.py [/dev/ttyAMA0] [baud]
Sends only the UBX-NAV-STATUS poll request (a read). Never prints position.
"""
import struct
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 230400
POLL = b"\xb5\x62\x01\x03\x00\x00\x04\x0d"  # UBX-NAV-STATUS poll

with serial.Serial(port, baud, timeout=0.2) as s:
    buf = b""
    t0 = time.time()
    while time.time() - t0 < 6:
        s.write(POLL)
        time.sleep(0.3)
        buf += s.read(4096)
        i = buf.find(b"\xb5\x62\x01\x03")
        if i >= 0 and len(buf) >= i + 6 + 16:
            p = buf[i + 6:i + 6 + 16]
            fix, flags, ttff, msss = p[4], p[5], *struct.unpack_from("<II", p, 8)
            up = float(open("/proc/uptime").read().split()[0])
            print(f"receiver msss {msss/1000:8.1f} s (since its own startup/reset)")
            print(f"linux uptime  {up:8.1f} s")
            print(f"receiver ttff {ttff/1000:8.1f} s  gpsFix {fix}  gpsFixOk {flags & 1}")
            print("VERDICT:", "GNSS restarted with this boot" if msss / 1000 <= up + 5
                  else "GNSS kept running across the reboot")
            sys.exit(0)
print("no NAV-STATUS reply")
sys.exit(1)
