#!/usr/bin/env python3
"""Read-only: decode UBX NAV-PVT (fixType, numSV, hAcc, pDOP) and NAV-SAT (C/N0 summary).

usage: ubx_pvt.py [/dev/ttyAMA0] [baud] [secs] [--poll-sat]
Never prints position. Writes nothing unless --poll-sat, which sends only the UBX-NAV-SAT
poll request (a read; no configuration change). Also decodes MON-RF (jamming/antenna).
"""
import struct
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 230400
secs = float(sys.argv[3]) if len(sys.argv) > 3 else 15

GNSS = {0: "GPS", 1: "SBAS", 2: "GAL", 3: "BDS", 5: "QZSS", 6: "GLO", 7: "NavIC"}
buf = b""
seen = {}
t0 = time.time()
with serial.Serial(port, baud, timeout=0.2) as s:
    while time.time() - t0 < secs:
        buf += s.read(4096)
        while True:
            i = buf.find(b"\xb5\x62")
            if i < 0 or len(buf) < i + 6:
                break
            cls, mid, ln = buf[i + 2], buf[i + 3], struct.unpack_from("<H", buf, i + 4)[0]
            if len(buf) < i + 8 + ln:
                break
            p = buf[i + 6:i + 6 + ln]
            ck_a = ck_b = 0
            for c in buf[i + 2:i + 6 + ln]:
                ck_a = (ck_a + c) & 0xFF
                ck_b = (ck_b + ck_a) & 0xFF
            ok = buf[i + 6 + ln] == ck_a and buf[i + 7 + ln] == ck_b
            buf = buf[i + 8 + ln:]
            if not ok:
                continue
            seen[(cls, mid)] = seen.get((cls, mid), 0) + 1
            if (cls, mid) == (0x01, 0x07) and ln >= 92:
                fix, flags, nsv = p[20], p[21], p[23]
                hacc = struct.unpack_from("<I", p, 40)[0] / 1000
                pdop = struct.unpack_from("<H", p, 76)[0] / 100
                print(f"{time.time()-t0:5.1f}s NAV-PVT fixType {fix} gnssFixOK {flags & 1} numSV {nsv:2d} "
                      f"hAcc {hacc:7.1f} m pDOP {pdop:.2f}")
            elif (cls, mid) == (0x01, 0x35) and ln >= 8:
                n = p[5]
                used, cn0 = {}, []
                for k in range(n):
                    o = 8 + 12 * k
                    if o + 12 > ln:
                        break
                    gid, cno, fl = p[o], p[o + 2], struct.unpack_from("<I", p, o + 8)[0]
                    if cno:
                        cn0.append(cno)
                    if fl & 0x08:
                        used[GNSS.get(gid, gid)] = used.get(GNSS.get(gid, gid), 0) + 1
                cn0.sort(reverse=True)
                print(f"{time.time()-t0:5.1f}s NAV-SAT tracked {len(cn0)} used {used} top C/N0 {cn0[:8]}")
                per = {}
                for k in range(n):
                    o = 8 + 12 * k
                    if o + 12 > ln:
                        break
                    gname = GNSS.get(p[o], p[o])
                    per.setdefault(gname, []).append(p[o + 2])
                for gname, cl in sorted(per.items()):
                    print(f"        {gname:5s} {len(cl):2d} sv  C/N0 {sorted(cl, reverse=True)}")
            elif (cls, mid) == (0x0A, 0x38) and ln >= 4 and seen[(cls, mid)] <= 2:
                for b in range(p[1]):
                    o = 4 + 24 * b
                    if o + 24 > ln:
                        break
                    jam = p[o + 1] & 3
                    noise, agc = struct.unpack_from("<HH", p, o + 12)
                    print(f"{time.time()-t0:5.1f}s MON-RF block {p[o]} jammingState {jam} antStatus {p[o+2]} "
                          f"antPower {p[o+3]} noisePerMS {noise} agcCnt {agc} jamInd {p[o+16]}")
        if "--poll-sat" in sys.argv and not seen.get((0x01, 0x35)) and time.time() - t0 > 1:
            s.write(b"\xb5\x62\x01\x35\x00\x00\x36\xa3")  # UBX-NAV-SAT poll (read request)
            time.sleep(0.3)
print("message counts:", {f"{c:02x}-{m:02x}": n for (c, m), n in sorted(seen.items())})
