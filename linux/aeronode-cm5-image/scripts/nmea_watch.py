#!/usr/bin/env python3
"""Read-only NMEA cold-start watcher: time to first fix, satellites used/tracked, C/N0.

usage: nmea_watch.py [/dev/ttyAMA0] [baud] [max_secs] [report_every]
Prints one summary line per report period and a FIRST FIX line. Never prints position.
Exits once a 3D fix has held for 60 s, or at max_secs.
"""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 38400
max_secs = float(sys.argv[3]) if len(sys.argv) > 3 else 2400
every = float(sys.argv[4]) if len(sys.argv) > 4 else 30

TALKER = {"GP": "GPS", "GL": "GLO", "GA": "GAL", "GB": "BDS", "BD": "BDS", "GQ": "QZSS", "GI": "NavIC"}
t0 = time.time()
first_fix = None
fix_since = None
state = {"q": 0, "nsat": 0, "hdop": None, "mode": 1}
cn0 = {}   # (constellation, prn) -> (cn0, time)
last_report = 0.0
buf = b""

with serial.Serial(port, baud, timeout=0.5) as s:
    while time.time() - t0 < max_secs:
        buf += s.read(4096)
        *lines, buf = buf.split(b"\r\n")
        now = time.time() - t0
        for raw in lines:
            line = raw.decode("ascii", "replace")
            if not line.startswith("$") or "*" not in line:
                continue
            f = line.split("*")[0].split(",")
            typ = f[0][3:]
            if typ == "GGA" and len(f) > 8:
                state["q"] = int(f[6] or 0)
                state["nsat"] = int(f[7] or 0)
                state["hdop"] = f[8] or None
            elif typ == "GSA" and len(f) > 2:
                state["mode"] = int(f[2] or 1)   # every GNGSA block carries the same fix mode
            elif typ == "GSV" and len(f) > 4:
                sys_ = TALKER.get(f[0][1:3], f[0][1:3])
                for k in range(4, len(f) - 3, 4):
                    prn, snr = f[k], f[k + 3]
                    if prn and snr:
                        cn0[(sys_, prn)] = (int(snr), now)
        if state["q"] > 0 and state["mode"] >= 3:
            if first_fix is None:
                first_fix = now
                print(f"FIRST FIX at {now:6.1f} s: quality {state['q']} used {state['nsat']} hdop {state['hdop']}",
                      flush=True)
            fix_since = fix_since or now
        else:
            fix_since = None
        if now - last_report >= every:
            last_report = now
            live = {k: v[0] for k, v in cn0.items() if now - v[1] < 10}
            per = {}
            for (sys_, _), c in live.items():
                per.setdefault(sys_, []).append(c)
            desc = " ".join(f"{k}:{len(v)}[max {max(v)}]" for k, v in sorted(per.items())) or "none"
            print(f"{now:6.1f} s  fix q{state['q']} mode{state['mode']} used {state['nsat']:2d} "
                  f"hdop {state['hdop']}  tracked C/N0>0: {desc}", flush=True)
        if fix_since is not None and now - fix_since >= 60:
            print(f"3D fix held 60 s; TTFF {first_fix:.1f} s", flush=True)
            break
print("end", f"{time.time()-t0:.0f} s", "TTFF", f"{first_fix:.1f} s" if first_fix else "NONE", flush=True)
