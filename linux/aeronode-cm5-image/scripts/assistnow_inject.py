#!/usr/bin/env python3
"""Feed u-blox AssistNow data to BB1's GNSS THROUGH ArduPlane (MAVLink GPS_INJECT_DATA), no port takeover.

usage: assistnow_inject.py --serial [--no-fetch]        (BEFORE ArduPlane: time+position+orbits, ACK-checked)
       assistnow_inject.py [--save-pos|--save-only] [udpin:...]  (via ArduPlane: time+position only)

Run by assistnow-inject.service every time arduplane.service starts (so: every boot).
  1. Waits for an ArduPlane heartbeat (up to 120 s) and, if the network is up, for chrony to sync (90 s).
  2. MGA-INI-TIME_UTC built from this host's clock, only when chrony says it is synchronised.
  3. MGA-INI-POS_LLH: COARSE position from ~/.config/aeronode/assistnow/coarse_pos ("lat lon acc_m", 600),
     else the centre of South Africa +-1000 km. Never printed.
  4. Unless --pos-only: AssistNow orbits (Live, falling back to Predictive 3-day) fetched with the chipcode
     from assistnow_bootstrap.py and cached in last.ubx; offline or --no-fetch -> the cache if < 3 days old.
     The server's own MGA-INI-TIME is dropped (ours is fresher).
  5. --save-pos: then waits up to 20 min for a 3D fix with hAcc < 50 m (MAVLink GPS_RAW_INT) and saves it
     ROUNDED to 0.1 deg with a 20 km accuracy to coarse_pos, for the next boot. Never printed.

ArduPilot writes each GPS_INJECT_DATA packet to the receiver UART only if it fits in the TX buffer and
otherwise drops it silently (GPS_Backend.cpp:117), so every packet carries exactly ONE whole UBX frame
(all MGA frames are <= 96 B) and packets are paced. No ACK comes back through ArduPilot.
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
POSF = os.path.join(D, "coarse_pos")
DATA_URL = "https://assistnow.services.u-blox.com/GetAssistNowData.ashx"
GNSS = "gps,gal,bds,qzss"
WANT = ("ualm,ulorb_l1,utime,ukion,usvht", "ualm,uporb_3,utime,ukion,usvht")  # utime is REQUIRED: without it ~105/178 frames come back "no time"
DEFAULT_POS = (-29.0, 24.5, 1_000_000.0)  # centre of South Africa, 1000 km: coarse on purpose
CACHE_MAX_S = 3 * 86400
GPS_UTC_LEAP_S = 18
PACE_S = 0.015


def log(msg):
    print(msg, flush=True)


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


def net_up():
    try:
        urllib.request.urlopen("https://assistnow.services.u-blox.com/", timeout=5)
        return True
    except urllib.error.HTTPError:
        return True  # reached the server; status does not matter
    except Exception:
        return False


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
        lat, lon, acc = (float(x) for x in open(POSF).read().split()[:3])
        return lat, lon, max(acc, 1000.0), "saved"
    except Exception:
        return (*DEFAULT_POS, "default")


def write_private(path, data):
    old = os.umask(0o077)
    try:
        with open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
    finally:
        os.umask(old)


def fetch():
    cred = json.load(open(os.path.join(D, "ztp_credentials.json")))
    chip = cred["chipcode"]
    for want in WANT:
        q = urllib.parse.urlencode({"chipcode": chip, "data": want, "gnss": GNSS}, safe=",")
        try:
            with urllib.request.urlopen(f"{DATA_URL}?{q}", timeout=20) as r:
                data = r.read()
            log(f"fetch '{want}': {len(data)} B")
            write_private(CACHE, data)
            return data
        except urllib.error.HTTPError as e:
            log(f"fetch '{want}': HTTP {e.code} "
                f"{e.read()[:160].decode(errors='replace').replace(chip, '<chipcode>')}")
        except Exception as e:
            log(f"fetch '{want}': {type(e).__name__}")
            break
    return None


def save_pos(m, wait_s=1200):
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 1_000_000, 0, 0, 0, 0, 0)
    end = time.time() + wait_s
    while time.time() < end:
        g = m.recv_match(type="GPS_RAW_INT", blocking=True, timeout=5)
        if g and g.fix_type >= 3 and 0 < getattr(g, "h_acc", 0) < 50_000:  # h_acc in mm
            lat, lon = round(g.lat / 1e7, 1), round(g.lon / 1e7, 1)
            write_private(POSF, f"{lat:.1f} {lon:.1f} 20000\n".encode())  # 0.1 deg rounding <= ~8 km
            log("saved a coarse position (0.1 deg, 20 km) for the next boot")
            return
    log("no 3D fix with hAcc < 50 m within the wait; coarse position not updated")


def build(args, online):
    """time + coarse position + orbits (fetched or cached), as a list of whole UBX frames."""
    if online:
        for _ in range(15):
            if clock_synced():
                break
            time.sleep(2)
    out = []
    if clock_synced():
        out.append(mga_ini_time_utc())
    else:
        log("clock NOT synchronised: no time sent (orbit data needs it)")
    lat, lon, acc, src = coarse_pos()
    out.append(mga_ini_pos_llh(lat, lon, acc))
    log(f"position aid: {src}, accuracy {acc / 1000:.0f} km")
    if "--pos-only" not in args:
        data = fetch() if online else None
        fresh_fetch = data is not None
        if data is None and os.path.exists(CACHE):
            age = time.time() - os.path.getmtime(CACHE)
            if age < CACHE_MAX_S and out and out[0][6] == 0x10:
                data = open(CACHE, "rb").read()
                log(f"using cache, {age / 3600:.1f} h old")
        if data:
            fr = frames(data)
            srv_time = [f for f in fr if f[2] == 0x13 and f[3] == 0x40 and f[6] == 0x10]
            if fresh_fetch and srv_time:
                # Measured 2026-11-18: with our own MGA-INI-TIME first, 103/178 frames came back
                # "no time" (infoCode 1); with the server's (fresh download) 190/190 were accepted.
                out = [srv_time[0]] + [f for f in out if not (f[2] == 0x13 and f[3] == 0x40 and f[6] == 0x10)]
            out += [f for f in fr if not (f[2] == 0x13 and f[3] == 0x40 and f[6] == 0x10)]
        else:
            log("no orbit data (offline, no usable cache, or no synced clock)")
    return out


def find_receiver(port, wait_s=20):
    """At boot the receiver is itself still starting, and after a power cycle it is not necessarily at
    230400 (measured: 0 replies at 230400 6-14 s after boot; ArduPlane needed 10 s to detect it).
    Poll UBX-MON-VER at each baud until it answers. Returns (baud, swVersion) or (None, None)."""
    import serial
    end = time.time() + wait_s
    while time.time() < end:
        for baud in (230400, 38400, 115200, 9600):
            with serial.Serial(port, baud, timeout=0.05) as s:
                s.reset_input_buffer()
                s.write(ubx(0x0A, 0x04))
                buf, t = b"", time.time() + 0.8
                while time.time() < t:
                    buf += s.read(4096)
                    for f in frames(buf):
                        if f[2] == 0x0A and f[3] == 0x04:
                            return baud, f[6:36].split(b"\0")[0].decode(errors="replace")
        time.sleep(0.5)
    return None, None


def serial_inject(out, port="/dev/ttyAMA0", baud=None):
    """Direct UART injection, for use BEFORE ArduPlane owns the port. MGA ACKs on in RAM, counted."""
    import serial
    if baud is None:
        t0 = time.time()
        baud, sw = find_receiver(port)
        if not baud:
            log("serial: receiver did not answer MON-VER at 230400/38400/115200/9600 within 20 s")
            return 0
        log(f"serial: receiver answered at {baud} baud after {time.time() - t0:.1f} s ({sw})")
    s = serial.Serial(port, baud, timeout=0.02)
    buf = b""

    def pump(secs):
        nonlocal buf
        got, end = [], time.time() + secs
        while time.time() < end:
            buf += s.read(4096)
            f = frames(buf)
            if f:
                got += f
                buf = buf[buf.rfind(f[-1]) + len(f[-1]):]
        return got
    # CFG-NAVSPG-ACKAIDING = 1 in RAM only
    s.write(ubx(0x06, 0x8A, struct.pack("<BBHIB", 0, 0x01, 0, 0x10110025, 1)))
    pump(0.5)
    acks = {}
    for f in out:
        s.write(f)
        if f[2] == 0x13 and f[3] == 0x40:  # MGA-INI (time/position): let the receiver apply it first
            time.sleep(0.15)
        for a in pump(0.02):
            if a[2] == 0x13 and a[3] == 0x60 and len(a) >= 16:
                acks[(a[6], a[8])] = acks.get((a[6], a[8]), 0) + 1
    for a in pump(1.5):
        if a[2] == 0x13 and a[3] == 0x60 and len(a) >= 16:
            acks[(a[6], a[8])] = acks.get((a[6], a[8]), 0) + 1
    if acks.get((0, 1)):
        # Measured 2026-11-18: on a freshly cold receiver ~110/182 orbit frames come back infoCode 1
        # ("no time") although MGA-INI-TIME was ACKed; resent a few seconds later, 182/182 are accepted.
        log(f"pass 1: {acks.get((0, 1))} frames rejected 'no time'; resending after 2 s")
        time.sleep(2)
        first = acks
        acks = {}
        resend = [mga_ini_time_utc()] + [f for f in out if not (f[2] == 0x13 and f[3] == 0x40 and f[6] == 0x10)]
        for f in resend:
            s.write(f)
            if f[2] == 0x13 and f[3] == 0x40:
                time.sleep(0.15)
            for a in pump(0.02):
                if a[2] == 0x13 and a[3] == 0x60 and len(a) >= 16:
                    acks[(a[6], a[8])] = acks.get((a[6], a[8]), 0) + 1
        for a in pump(1.5):
            if a[2] == 0x13 and a[3] == 0x60 and len(a) >= 16:
                acks[(a[6], a[8])] = acks.get((a[6], a[8]), 0) + 1
        log(f"pass 1 acks {first}")
    s.write(ubx(0x06, 0x8A, struct.pack("<BBHIB", 0, 0x01, 0, 0x10110025, 0)))
    pump(0.3)
    s.close()
    ok = sum(v for (t, _), v in acks.items() if t == 1)
    log(f"serial: sent {len(out)} frames, receiver ACCEPTED {ok}; (type,infoCode)->count {acks}")
    return ok


def main():
    args = sys.argv[1:]
    if "--serial" in args:
        # Before ArduPlane (assistnow-preload.service): direct UART, ACK-checked. Proven path.
        online = "--no-fetch" not in args and net_up()
        out = build(args, online)
        ok = serial_inject(out)
        sys.exit(0 if ok else 1)
    mav = next((a for a in args if a.startswith("udp")), "udpin:127.0.0.1:14552")
    m = mavutil.mavlink_connection(mav, source_system=252)
    if not m.wait_heartbeat(timeout=120):
        sys.exit("FAIL: no heartbeat from ArduPlane on " + mav)
    log(f"ArduPlane heartbeat from sys {m.target_system}")
    # AP_GPS::inject_data() silently drops everything until the GPS driver exists (drivers[i] != nullptr),
    # i.e. until ArduPlane has detected the receiver: GPS_RAW_INT.fix_type >= 1. Measured: injecting 4 s
    # after the heartbeat lost all 178 frames. Then give ArduPlane's config burst a few seconds.
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 500_000, 0, 0, 0, 0, 0)
    t0, end = time.time(), time.time() + 180
    while time.time() < end:
        g = m.recv_match(type="GPS_RAW_INT", blocking=True, timeout=3)
        if g and g.fix_type >= 1:
            break
    else:
        sys.exit("FAIL: ArduPlane never reported the GPS as detected (GPS_RAW_INT fix_type >= 1)")
    log(f"GPS detected by ArduPlane after {time.time() - t0:.0f} s")
    time.sleep(5)

    if "--save-only" in args:
        save_pos(m)
        return
    # Through ArduPlane only the small MGA-INI frames are proven to arrive (measured: a 178-frame orbit
    # burst via GPS_INJECT_DATA was lost, the receiver never learned the orbits). Orbits go via --serial.
    out = [mga_ini_time_utc()] if clock_synced() else []
    lat, lon, acc, src = coarse_pos()
    out.append(mga_ini_pos_llh(lat, lon, acc))
    for f in out:
        m.mav.gps_inject_data_send(m.target_system, m.target_component, len(f), f.ljust(110, b"\0"))
        time.sleep(PACE_S)
    log(f"injected time={'yes' if len(out) == 2 else 'no'} + position ({src}, {acc / 1000:.0f} km) via GPS_INJECT_DATA")
    if "--save-pos" in args:
        save_pos(m)


if __name__ == "__main__":
    main()
