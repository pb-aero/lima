#!/usr/bin/env python3
"""power_button_shutdown.py — DOUBLE-press the CM5 power button -> clean shutdown.

Peter 2026-11-22: "Yes, double-press", after finding BB1 does NOT shut down safely from its button:
  * AeroNode deliberately ignores the power key — /etc/systemd/logind.conf.d/ignore-power-key.conf
    (HandlePowerKey=ignore; "a flight recorder must not die to a bumped button": a chassis button by the Ethernet
    jack caused two accidental shutdowns in 2026-08). That file is ALFA's and is left untouched.
  * So a press did nothing and power then went with no shutdown (journal 2026-11-22 09:29:02 "Power key pressed
    short", journal ends 3 s later, no stop sequence) — in effect a power cut.
This keeps single presses ignored (bump-proof) and turns TWO presses within --window-s (1.5 s) into
`sudo -n /usr/bin/systemctl poweroff`, which stops ArduPilot, the collector and the loggers properly.

Reads the kernel input device itself (no extra library): the gpio-keys device named "pwr_button" (/dev/input/event0
on BB1), struct input_event = timeval (2 x 8 bytes) + type u16 + code u16 + value s32. EV_KEY=1, KEY_POWER=116,
value 1 = press. A second press counts only between --min-gap-s (0.15 s, contact bounce) and --window-s after the
first. logind keeps reading the same device (no exclusive grab), so its own "Power key pressed" log lines stay.
--dry-run logs "would power off" instead (for testing).
"""
import argparse
import glob
import os
import struct
import subprocess
import sys
import signal
import time

EV_KEY, KEY_POWER = 1, 116
EVENT = struct.Struct("llHHi")           # 64-bit: tv_sec, tv_usec, type, code, value (24 bytes)


def find_device(name: str):
    for path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            with open(path) as f:
                if f.read().strip() == name:
                    return "/dev/input/" + path.split("/")[4]
        except OSError:
            pass
    return None


def log(msg: str) -> None:
    print(f"power-button: {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="pwr_button", help="input device name (/sys/class/input/event*/device/name)")
    ap.add_argument("--window-s", type=float, default=1.5, help="second press must come within this, s")
    ap.add_argument("--min-gap-s", type=float, default=0.15, help="ignore a second press sooner than this (bounce)")
    ap.add_argument("--dry-run", action="store_true", help="log 'would power off' instead of powering off")
    args = ap.parse_args()

    warned = False
    while True:
        dev = find_device(args.name)
        if dev is None:
            if not warned:
                log(f"no input device named {args.name!r}; retrying every 10 s")
                warned = True
            time.sleep(10)
            continue
        warned = False
        log(f"watching {dev} ({args.name}): press twice within {args.window_s:g} s to shut down"
            + (" [DRY RUN]" if args.dry_run else ""))
        last_press = None
        try:
            with open(dev, "rb", buffering=0) as f:
                while True:
                    buf = f.read(EVENT.size)
                    if len(buf) < EVENT.size:
                        raise OSError("short read")
                    _, _, etype, code, value = EVENT.unpack(buf)
                    if etype != EV_KEY or code != KEY_POWER or value != 1:
                        continue
                    now = time.monotonic()
                    gap = None if last_press is None else now - last_press
                    if gap is not None and args.min_gap_s <= gap <= args.window_s:
                        log(f"double press ({gap:.2f} s apart) — "
                            + ("would power off [DRY RUN]" if args.dry_run else "powering off"))
                        last_press = None
                        if not args.dry_run:
                            r = subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"],
                                               capture_output=True, text=True, timeout=30)
                            if r.returncode != 0:
                                log(f"poweroff failed (rc {r.returncode}): {(r.stderr or r.stdout).strip()}")
                    elif gap is not None and gap < args.min_gap_s:
                        continue                                  # bounce: keep the first press's time
                    else:
                        log("single press — ignored (press twice within "
                            f"{args.window_s:g} s to shut down)")
                        last_press = now
        except OSError as e:
            log(f"{dev}: {e}; reopening in 5 s")
            time.sleep(5)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
