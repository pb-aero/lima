#!/usr/bin/env python3
"""One-time AssistNow setup + a direct, ACK-checked injection on a u-blox M10/F10 (BB1: DAN-F10N).

Run ON BB1 with arduplane STOPPED (this script must be the only reader of the GNSS UART).
    sudo systemctl stop arduplane
    /home/node/aeronode/.venv/bin/python assistnow_bootstrap.py
    sudo systemctl start arduplane

1. Polls UBX-SEC-UNIQID and UBX-MON-VER (full frames, hex) from the receiver.
2. If there are no saved credentials yet: POSTs them with the Thingstream ZTP token
   (~/.config/aeronode/assistnow/ztp_token, written by assistnow_set_token.sh) to the
   profile's ZTP endpoint and saves the JSON reply (holds the chipcode) next to it, mode 600.
3. Downloads AssistNow data (Live orbits; falls back to Predictive) with the chipcode.
4. Turns on MGA ACKs in RAM, sends every UBX frame paced, and counts MGA-ACK-DATA0 replies
   (positive control that the receiver really accepted the data), then turns ACKs off again.

Secrets (ZTP token, chipcode) are never printed. Position is never requested or printed.
"""
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import serial

PORT, BAUD = "/dev/ttyAMA0", 230400
D = os.path.expanduser("~/.config/aeronode/assistnow")
ZTP_URL = "https://api.thingstream.io/ztp/assistnow/credentials"
DATA_URL = "https://assistnow.services.u-blox.com/GetAssistNowData.ashx"
GNSS = "gps,gal,bds,qzss"  # what an F10 tracks; GLONASS data would be wasted
K_ACKAIDING = 0x10110025   # CFG-NAVSPG-ACKAIDING (L)


def ubx(cls, mid, payload=b""):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


def frames(buf):
    """Split a byte string into complete UBX frames (with header and checksum)."""
    out, i = [], 0
    while True:
        i = buf.find(b"\xb5\x62", i)
        if i < 0 or len(buf) < i + 6:
            return out, buf[i:] if i >= 0 else b""
        ln = struct.unpack_from("<H", buf, i + 4)[0]
        if len(buf) < i + 8 + ln:
            return out, buf[i:]
        out.append(buf[i:i + 8 + ln])
        i += 8 + ln


class Rx:
    def __init__(self):
        self.s = serial.Serial(PORT, BAUD, timeout=0.05)
        self.buf = b""

    def read_frames(self, secs):
        got, end = [], time.time() + secs
        while time.time() < end:
            self.buf += self.s.read(4096)
            f, self.buf = frames(self.buf)
            got += f
        return got

    def poll(self, cls, mid, tries=4):
        for _ in range(tries):
            self.s.write(ubx(cls, mid))
            for f in self.read_frames(0.6):
                if f[2] == cls and f[3] == mid:
                    return f
        return None

    def valset_ram(self, key, val_u1):
        self.s.write(ubx(0x06, 0x8A, struct.pack("<BBH", 0, 0x01, 0) + struct.pack("<IB", key, val_u1)))
        for f in self.read_frames(0.6):
            if f[2] == 0x05 and f[6] == 0x06 and f[7] == 0x8A:
                return f[3] == 0x01  # ACK-ACK
        return None


def redact(text, *secrets):
    for s in secrets:
        if s:
            text = text.replace(s, "<redacted>")
    return text


def find_key(obj, name):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == name:
                return v
            r = find_key(v, name)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, name)
            if r is not None:
                return r
    return None


def shape(obj):
    """Keys of the reply with values replaced by type/length, so nothing secret is printed."""
    if isinstance(obj, dict):
        return {k: shape(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shape(v) for v in obj[:3]]
    if isinstance(obj, str):
        return f"<str {len(obj)}>"
    return type(obj).__name__


def main():
    rx = Rx()
    uniq = rx.poll(0x27, 0x03)
    ver = rx.poll(0x0A, 0x04)
    if not uniq or not ver:
        sys.exit(f"FAIL: receiver did not answer SEC-UNIQID={bool(uniq)} MON-VER={bool(ver)} at {BAUD}")
    p = ver[6:-2]
    sw, hw = p[:30].split(b"\0")[0].decode(), p[30:40].split(b"\0")[0].decode()
    ext = [p[i:i + 30].split(b"\0")[0].decode() for i in range(40, len(p), 30)]
    print(f"receiver: sw={sw} hw={hw} ext={ext}")
    print(f"SEC-UNIQID: {len(uniq)} byte frame, uniqueId {len(uniq) - 8 - 4} bytes")

    cred_path = os.path.join(D, "ztp_credentials.json")
    token = open(os.path.join(D, "ztp_token")).read().strip()
    if not os.path.exists(cred_path):
        body = json.dumps({"token": token, "messages": {"UBX-SEC-UNIQID": uniq.hex().upper(),
                                                        "UBX-MON-VER": ver.hex().upper()}}).encode()
        req = urllib.request.Request(ZTP_URL, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                reply = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            sys.exit(f"FAIL: ZTP HTTP {e.code}: {redact(e.read().decode(errors='replace')[:600], token)}")
        cred = json.loads(reply)
        old = os.umask(0o077)
        with open(cred_path, "w") as f:
            json.dump(cred, f)
        os.umask(old)
        print(f"ZTP: HTTP {status}, registered; reply shape {json.dumps(shape(cred))}")
    else:
        cred = json.load(open(cred_path))
        print("ZTP: using saved credentials")
    chipcode = find_key(cred, "chipcode")
    if not chipcode:
        sys.exit(f"FAIL: no 'chipcode' in reply; shape {json.dumps(shape(cred))}")

    data = None
    for want in ("ualm,ulorb_l1,utime,ukion,usvht", "ualm,uporb_1,utime,ukion,usvht"):
        q = urllib.parse.urlencode({"chipcode": chipcode, "data": want, "gnss": GNSS}, safe=",")
        try:
            t0 = time.time()
            with urllib.request.urlopen(f"{DATA_URL}?{q}", timeout=30) as r:
                data = r.read()
            print(f"data: '{want}' -> {len(data)} bytes in {time.time() - t0:.1f} s")
            break
        except urllib.error.HTTPError as e:
            print(f"data: '{want}' -> HTTP {e.code}: {redact(e.read().decode(errors='replace')[:300], chipcode, token)}")
    if not data:
        sys.exit("FAIL: no assistance data")
    fr, rest = frames(data)
    kinds = {}
    for f in fr:
        kinds[f"{f[2]:02X}-{f[3]:02X}"] = kinds.get(f"{f[2]:02X}-{f[3]:02X}", 0) + 1
    print(f"frames: {len(fr)} (trailing junk {len(rest)} B), by class-id {kinds}, largest {max(map(len, fr))} B")

    ack_on = rx.valset_ram(K_ACKAIDING, 1)
    print(f"MGA ACKs on (RAM): {ack_on}")
    acks = {}
    sent = 0
    rx.read_frames(0.2)
    for f in fr:
        rx.s.write(f)
        sent += 1
        for a in rx.read_frames(0.02):
            if a[2] == 0x13 and a[3] == 0x60 and len(a) >= 16:
                k = (a[6], a[8])  # (type 1=accepted 0=not used, infoCode)
                acks[k] = acks.get(k, 0) + 1
    for a in rx.read_frames(1.5):
        if a[2] == 0x13 and a[3] == 0x60 and len(a) >= 16:
            k = (a[6], a[8])
            acks[k] = acks.get(k, 0) + 1
    rx.valset_ram(K_ACKAIDING, 0)
    accepted = sum(v for (t, _), v in acks.items() if t == 1)
    print(f"sent {sent} frames; MGA-ACK (type,infoCode)->count {acks}; accepted {accepted}")
    print("RESULT", "OK" if accepted else ("SENT-UNCONFIRMED" if ack_on is not True else "NONE-ACCEPTED"))


if __name__ == "__main__":
    main()
