#!/usr/bin/env python3
"""One controlled GNSS cold-start trial on a u-blox M10/F10.

usage: gnss_trial.py LABEL RATE_MS DYNMODEL [timeout_s] [port] [baud]
  e.g. gnss_trial.py factory 1000 0      gnss_trial.py ardupilot 200 8

1. VALSET (RAM layer only, nothing saved) CFG-RATE-MEAS and CFG-NAVSPG-DYNMODEL; require ACK.
2. VALGET read-back (positive control: the receiver really holds the trial values).
3. CFG-RST navBbrMask 0xFFFF (clear ephemeris/almanac/position/time = cold) + resetMode 0x02
   (controlled GNSS-only restart, so RAM config survives). VALGET again to prove it survived.
4. Time to first fix from NMEA GGA (quality >= 1, GSA mode 3), plus the receiver's own NAV-STATUS ttff.
5. Report the mean of the 4 strongest C/N0 during the trial, as a measure of sky conditions.
Prints ONE "RESULT" line. Never prints position. The port must have no other reader.
"""
import struct
import sys
import time

import serial

label = sys.argv[1]
rate_ms = int(sys.argv[2])
dynmodel = int(sys.argv[3])
timeout_s = float(sys.argv[4]) if len(sys.argv) > 4 else 900
port = sys.argv[5] if len(sys.argv) > 5 else "/dev/ttyAMA0"
baud = 230400

K_RATE, K_DYN, K_BAUD = 0x30210001, 0x20110021, 0x40520001


def ubx(cls, mid, payload=b""):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


class Rx:
    def __init__(self, s):
        self.s, self.buf = s, b""

    def pump(self):
        self.buf += self.s.read(4096)

    def ubx_msgs(self):
        out = []
        while True:
            i = self.buf.find(b"\xb5\x62")
            if i < 0 or len(self.buf) < i + 6:
                break
            ln = struct.unpack_from("<H", self.buf, i + 4)[0]
            if len(self.buf) < i + 8 + ln:
                break
            out.append((self.buf[i + 2], self.buf[i + 3], self.buf[i + 6:i + 6 + ln]))
            self.buf = self.buf[:i] + self.buf[i + 8 + ln:]
        return out

    def nmea_lines(self):
        *lines, self.buf = self.buf.split(b"\r\n")
        return [ln[ln.find(b"$"):].decode("ascii", "replace") for ln in lines if b"$G" in ln]


def wait_ubx(rx, want, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        rx.pump()
        for cls, mid, p in rx.ubx_msgs():
            if want(cls, mid, p):
                return cls, mid, p
        rx.nmea_lines()
    return None


def valget(s, rx):
    s.write(ubx(0x06, 0x8B, struct.pack("<BBH", 0, 0, 0) + struct.pack("<II", K_RATE, K_DYN)))
    r = wait_ubx(rx, lambda c, m, p: (c, m) == (0x06, 0x8B))
    if not r:
        return None
    p, vals, o = r[2], {}, 4
    while o + 4 <= len(p):
        key = struct.unpack_from("<I", p, o)[0]
        o += 4
        size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8}[(key >> 28) & 7]
        vals[key] = int.from_bytes(p[o:o + size], "little")
        o += size
    return vals.get(K_RATE), vals.get(K_DYN)


def nmea_flowing(b):
    with serial.Serial(port, b, timeout=0.2) as t:
        t.reset_input_buffer()
        d = b""
        t0 = time.time()
        while time.time() - t0 < 1.5:
            d += t.read(4096)
    return d.count(b"$G") >= 3


# [measured 2026-11-18] At 38400 the factory NMEA set at 5 Hz SATURATES the UART and UBX replies
# are lost. So every trial runs at 230400: if the receiver is not already there, tell it (RAM only)
# to go to 1 Hz + 230400 at whatever baud it is on now. UBX *input* still works when output is full.
if not nmea_flowing(baud):
    for b in (38400, 9600, 115200):
        with serial.Serial(port, b, timeout=0.1) as t:
            t.write(ubx(0x06, 0x8A, struct.pack("<BBH", 0, 0x01, 0)
                        + struct.pack("<IH", K_RATE, 1000) + struct.pack("<II", K_BAUD, baud)))
            t.flush()
        time.sleep(0.5)
        if nmea_flowing(baud):
            break
    else:
        print(f"RESULT {label} ABORT could not move receiver to {baud}", flush=True)
        sys.exit(4)

with serial.Serial(port, baud, timeout=0.1) as s:
    rx = Rx(s)
    s.reset_input_buffer()
    s.write(ubx(0x06, 0x8A, struct.pack("<BBH", 0, 0x01, 0)
                + struct.pack("<IH", K_RATE, rate_ms) + struct.pack("<IB", K_DYN, dynmodel)))
    ack = wait_ubx(rx, lambda c, m, p: c == 0x05 and p[:2] == b"\x06\x8a")
    if not ack or ack[1] != 0x01:
        print(f"RESULT {label} ABORT valset {'NAK' if ack else 'no reply'}", flush=True)
        sys.exit(2)
    before = valget(s, rx)
    s.write(ubx(0x06, 0x04, struct.pack("<HBB", 0xFFFF, 0x02, 0)))
    t0 = time.time()
    time.sleep(1.0)
    rx.buf = b""
    after = valget(s, rx)
    if after != (rate_ms, dynmodel):
        print(f"RESULT {label} ABORT config before={before} after_reset={after} want={(rate_ms, dynmodel)}",
              flush=True)
        sys.exit(3)

    first_fix = None
    cn0_top = []
    used = hdop = None
    q = mode = 0
    while time.time() - t0 < timeout_s:
        rx.pump()
        rx.ubx_msgs()
        snrs = []
        for line in rx.nmea_lines():
            f = line.split("*")[0].split(",")
            typ = f[0][3:]
            if typ == "GGA" and len(f) > 8:
                q, used, hdop = int(f[6] or 0), f[7], f[8]
            elif typ == "GSA" and len(f) > 2:
                mode = int(f[2] or 1)
            elif typ == "GSV":
                snrs += [int(f[k + 3]) for k in range(4, len(f) - 3, 4) if f[k + 3]]
        if snrs:
            cn0_top.append(sum(sorted(snrs, reverse=True)[:4]) / min(4, len(snrs)))
        if q >= 1 and mode == 3:
            first_fix = time.time() - t0
            break

    rx_ttff = None
    if first_fix is not None:
        s.write(ubx(0x01, 0x03))
        r = wait_ubx(rx, lambda c, m, p: (c, m) == (0x01, 0x03) and len(p) >= 16)
        if r:
            rx_ttff = struct.unpack_from("<I", r[2], 8)[0] / 1000
    cn = sum(cn0_top) / len(cn0_top) if cn0_top else 0
    print(f"RESULT {label} rate={rate_ms} dyn={dynmodel} "
          f"TTFF={'%.1f' % first_fix if first_fix is not None else 'NONE'} "
          f"rx_ttff={rx_ttff} used={used} hdop={hdop} top4_cn0={cn:.1f} "
          f"cfg_after_reset={after} timeout={timeout_s:.0f}", flush=True)
