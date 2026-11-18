#!/usr/bin/env python3
"""Cold-start BB1's u-blox GNSS THROUGH ArduPlane: UBX-CFG-RST navBbrMask 0xFFFF (clear ephemeris, almanac,
position, time...), resetMode 0x02 (controlled GNSS-only restart; config survives). Sent as one
MAVLink GPS_INJECT_DATA packet. For time-to-first-fix tests. usage: gnss_cold_reset_mav.py [udpin:...]"""
import struct
import sys

from pymavlink import mavutil


def ubx(cls, mid, payload):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


m = mavutil.mavlink_connection(sys.argv[1] if len(sys.argv) > 1 else "udpin:127.0.0.1:14552", source_system=252)
if not m.wait_heartbeat(timeout=30):
    sys.exit("FAIL: no heartbeat")
f = ubx(0x06, 0x04, struct.pack("<HBB", 0xFFFF, 0x02, 0))
m.mav.gps_inject_data_send(m.target_system, m.target_component, len(f), f.ljust(110, b"\0"))
print("sent CFG-RST cold (0xFFFF, GNSS-only)")
