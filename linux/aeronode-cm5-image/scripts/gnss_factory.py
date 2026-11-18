#!/usr/bin/env python3
"""Restore a u-blox receiver to factory configuration, then cold hardware reset.

usage: gnss_factory.py [/dev/ttyAMA0] [baud]     (baud = the CURRENT UBX baud, e.g. 230400)

WRITES TO THE RECEIVER:
  UBX-CFG-CFG  clear+load all sections, devices BBR+Flash  -> saved config back to defaults
  UBX-CFG-RST  navBbrMask 0xFFFF (cold), resetMode 0 (hardware reset)
After the reset the receiver comes up on its defaults (NMEA @ 38400 for DAN-F10N).
Stop anything else using the port first (ArduPilot would reconfigure it straight back).
"""
import struct
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 230400


def ubx(cls, mid, payload=b""):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


def wait_ack(s, cls, mid, timeout=2.0):
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        buf += s.read(1024)
        for kind, tag in ((0x01, "ACK"), (0x00, "NAK")):
            if b"\xb5\x62\x05" + bytes([kind]) + b"\x02\x00" + bytes([cls, mid]) in buf:
                return tag
    return None


with serial.Serial(port, baud, timeout=0.1) as s:
    s.reset_input_buffer()
    cfg = ubx(0x06, 0x09, struct.pack("<IIIB", 0x00001F1F, 0, 0x00001F1F, 0x03))
    s.write(cfg)
    print("CFG-CFG clear+load (BBR+Flash):", wait_ack(s, 0x06, 0x09) or "no reply")
    s.write(ubx(0x06, 0x04, struct.pack("<HBB", 0xFFFF, 0x00, 0x00)))
    s.flush()
    print("CFG-RST cold hardware reset sent (no ACK expected)")

time.sleep(2)
for b in (38400, 9600, 230400):
    with serial.Serial(port, b, timeout=0.2) as s:
        s.reset_input_buffer()
        data = b""
        t0 = time.time()
        while time.time() - t0 < 2.5:
            data += s.read(4096)
    print(f"after reset @ {b:6d}: {len(data):5d} B  NMEA {data.count(b'$G'):3d}  UBX {data.count(bytes([0xb5, 0x62])):3d}")
