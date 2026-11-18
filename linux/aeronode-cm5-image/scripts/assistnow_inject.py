#!/usr/bin/env python3
"""Feed u-blox AssistNow data to BB1's GNSS THROUGH ArduPlane (MAVLink GPS_INJECT_DATA), no port takeover.

usage: assistnow_inject.py [--pos-only] [--no-fetch] [--mav udpin:127.0.0.1:14552]

  1. MGA-INI-TIME_UTC built from this host's clock (only if chrony says it is synchronised).
  2. MGA-INI-POS_LLH: a COARSE position (default: centre of South Africa, +-1000 km), or the values in
     ~/.config/aeronode/assistnow/coarse_pos ("lat lon acc_m", mode 600). Never printed.
  3. Unless --pos-only: AssistNow data (Live orbits, falling back to Predictive) fetched with the chipcode
     from assistnow_bootstrap.py and cached to ~/.config/aeronode/assistnow/last.ubx; with --no-fetch or
     no internet, the cache is used if it is under 24 h old. The server's own MGA-INI-TIME is dropped.

ArduPilot writes each GPS_INJECT_DATA packet to the receiver UART only if it fits in the TX buffer, and
otherwise drops it silently (GPS_Backend.cpp:117), so every packet carries exactly ONE whole UBX frame
(all MGA frames are <= 96 B) and packets are paced. No ACK comes back through ArduPilot: the proof is
the receiver's behaviour (NAV-SAT / time to fix), or assistnow_bootstrap.py's direct ACK count.
"""
import datetime
import json
import os
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from pymavlink import mavutil

D = os.path.expanduser("~/.config/aeronode/assistnow")
CACHE = os.path.join(D, "last.ubx")
DATA_URL = "https://assistnow.services.u-blox.com/GetAssistNowData.ashx"
GNSS = "gps,gal,bds,qzss"
DEFAULT_POS = (-29.0, 24.5, 1_000_000.0)  # centre of South Africa, 1000 km: coarse on purpose
GPS_UTC_LEAP_S = 18
PACE_S = 0.015


def ubx(cls, mid, payload=b""):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


def frames(buf):
    out, i = [], 0
    while True:
        i = buf.find(b"\xb5\x62", i)
        if i < 0 or len(buf) < i + 8:
            return out
        ln = struct.unpack_from("<H", buf, i + 4)[0]
        if len(buf) < i + 8 + ln:
            return out
        out.append(buf[i:i + 8 + ln])
        i += 8 + ln


def clock_synced():
    try:
        out = subprocess.run(["chronyc", "-n", "tracking"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return False
    return "Leap status     : Normal" in out and "Reference ID    : 00000000" not in out


def mga_ini_time_utc(tacc_s=1.0):
    now = datetime.datetime.now(datetime.timezone.utc)
    p = struct.pack("<BBBbHBBBBBBIHHI", 0x10, 0, 0, GPS_UTC_LEAP_S, now.year, now.month, now.day,
                    now.hour, now.minute, now.second, 0, now.microsecond * 1000,
                    int(tacc_s), 0, int((tacc_s % 1) * 1e9))
    return ubx(0x13, 0x40, p)


def mga_ini_pos_llh(lat, lon, acc_m, alt_m=0.0):
    p = struct.pack("<BBHiiiI", 0x01, 0, 0, int(round(lat * 1e7)), int(round(lon * 1e7)),
                    int(alt_m * 100), int(acc_m * 100))
    return ubx(0x13, 0x40, p)


def coarse_pos():
    try:
        lat, lon, acc = (float(x) for x in open(os.path.join(D, "coarse_pos")).read().split()[:3])
        return lat, lon, max(acc, 1000.0), "saved"
    except Exception:
        return (*DEFAULT_POS, "default")


def fetch():
    cred = json.load(open(os.path.join(D, "ztp_credentials.json")))
    chip = cred["chipcode"]
    for want in ("ualm,ulorb_l1,ukion,usvht", "ualm,uporb_1,ukion,usvht"):
        q = urllib.parse.urlencode({"chipcode": chip, "data": want, "gnss": GNSS}, safe=",")
        try:
            with urllib.request.urlopen(f"{DATA_URL}?{q}", timeout=20) as r:
                data = r.read()
            print(f"fetch '{want}': {len(data)} B")
            old = os.umask(0o077)
            with open(CACHE + ".tmp", "wb") as f:
                f.write(data)
            os.replace(CACHE + ".tmp", CACHE)
            os.umask(old)
            return data
        except urllib.error.HTTPError as e:
            print(f"fetch '{want}': HTTP {e.code} {e.read()[:160].decode(errors='replace').replace(chip, '<chipcode>')}")
        except Exception as e:
            print(f"fetch '{want}': {type(e).__name__}")
            break
    return None


def main():
    args = sys.argv[1:]
    mav = next((a for a in args if a.startswith("udp")), "udpin:127.0.0.1:14552")
    out = []
    if clock_synced():
        out.append(mga_ini_time_utc())
    else:
        print("clock NOT synchronised: sending no time (orbits are useless without it)")
    lat, lon, acc, src = coarse_pos()
    out.append(mga_ini_pos_llh(lat, lon, acc))
    print(f"position aid: {src}, accuracy {acc / 1000:.0f} km")
    if "--pos-only" not in args:
        data = None if "--no-fetch" in args else fetch()
        if data is None and os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < 86400:
            data = open(CACHE, "rb").read()
            print(f"using cache, {(time.time() - os.path.getmtime(CACHE)) / 3600:.1f} h old")
        if data:
            fr = [f for f in frames(data) if not (f[2] == 0x13 and f[3] == 0x40 and f[6] == 0x10)]
            out += fr
    big = [len(f) for f in out if len(f) > 110]
    if big:
        sys.exit(f"FAIL: frame(s) over 110 B: {big}")
    m = mavutil.mavlink_connection(mav, source_system=252)
    hb = m.wait_heartbeat(timeout=10)
    if not hb:
        sys.exit("FAIL: no heartbeat from ArduPlane on " + mav)
    for f in out:
        m.mav.gps_inject_data_send(m.target_system, m.target_component, len(f), f.ljust(110, b"\0"))
        time.sleep(PACE_S)
    print(f"injected {len(out)} UBX frames ({sum(map(len, out))} B) via GPS_INJECT_DATA to sys {m.target_system}")


if __name__ == "__main__":
    main()
