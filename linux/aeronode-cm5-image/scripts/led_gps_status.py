#!/usr/bin/env python3
"""led_gps_status.py — the Blackbox board's RGB LED shows GPS state: RED blink while looking for a fix, GREEN blink
once there is one.

Peter 2026-11-22: "make the red led of the rgb led blink while gps is looking for a fix and then switch to a green
led blink once there is a fix".

LED: LED3 IN-S126TBSRGB via TI LP5815 (U8, I2C-1 0x2D): out0 red, out1 green, out2 blue (blue never lit on BB1 —
unused here). Init per TI SNVSCP2B §8.2.3.2, same as scripts/led_test.py (measured 2026-11-17): 00h<-03h CHIP_EN,
01h<-00h 25.5 mA range, 14h-16h dot current (--dc, 0x50 ~8 mA), 02h<-03h outputs R+G, 04h<-00h manual, 0Fh<-55h
UPDATE_CMD; then manual PWM in 18h (R) / 19h (G). CHIP_EN is re-checked every 30 s and the init re-run if the chip lost
it (brownout/POR). On exit: LED off, chip back in standby.

GPS: the AeroNode collector's live MQTT stream <prefix>/<AERONODE_DEVICE_ID>/gps_raw (ArduPilot GPS_RAW_INT, 10 Hz).
Only data.fix_type is used. FIX = fix_type >= --min-fix (3 = 3D fix) in a message no older than --stale-s (3 s).
Anything else — no fix, 2D fix, no messages (FC/collector/broker down) — is "looking": red. The journal says which.
"""
import argparse
import json
import signal
import sys
import threading
import time

from smbus2 import SMBus

ADDR = 0x2D
state = {"fix_type": None, "rx": 0.0, "lock": threading.Lock()}


def device_id(env_path: str, fallback: str) -> str:
    try:
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("AERONODE_DEVICE_ID="):
                    return line.split("=", 1)[1].strip().strip('"\'') or fallback
    except OSError:
        pass
    return fallback


class Led:
    def __init__(self, bus: SMBus, dc: int):
        self.bus, self.dc = bus, dc

    def w(self, reg: int, val: int) -> None:
        self.bus.write_byte_data(ADDR, reg, val)

    def init(self) -> None:
        self.w(0x00, 0x03)
        time.sleep(0.002)
        self.w(0x01, 0x00)
        for reg in (0x14, 0x15, 0x16):
            self.w(reg, self.dc)
        self.w(0x02, 0x03)              # red + green outputs
        self.w(0x04, 0x00)              # manual PWM mode
        self.w(0x0F, 0x55)              # UPDATE_CMD (required for the config to take)
        self.set(0, 0)

    def alive(self) -> bool:
        return self.bus.read_byte_data(ADDR, 0x00) & 0x01 == 1

    def set(self, r: int, g: int) -> None:
        self.w(0x18, r)
        self.w(0x19, g)
        self.w(0x1A, 0)

    def off(self) -> None:
        self.set(0, 0)
        self.w(0x02, 0x00)
        self.w(0x0F, 0x55)
        self.w(0x00, 0x00)


def on_message(_c, _u, msg) -> None:
    try:
        ft = json.loads(msg.payload)["data"].get("fix_type")
    except (ValueError, KeyError, TypeError, AttributeError):
        return
    with state["lock"]:
        state["fix_type"], state["rx"] = ft, time.monotonic()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic-prefix", default="aeronode")
    ap.add_argument("--env", default="/home/node/aeronode/.env")
    ap.add_argument("--device-id", default="")
    ap.add_argument("--min-fix", type=int, default=3, help="GPS_RAW_INT fix_type counted as a fix (3 = 3D)")
    ap.add_argument("--stale-s", type=float, default=3.0, help="no gps_raw for this long = no fix known")
    ap.add_argument("--period-s", type=float, default=1.0, help="blink period")
    ap.add_argument("--on-s", type=float, default=0.5, help="LED on-time per period")
    ap.add_argument("--pwm", type=int, default=255, help="brightness 0-255 within the dot current")
    ap.add_argument("--dc", type=int, default=0x50, help="LP5815 dot current code (0x50 ~ 8 mA)")
    args = ap.parse_args()

    import paho.mqtt.client as mqtt
    dev = args.device_id or device_id(args.env, "BB1")
    topic = f"{args.topic_prefix}/{dev}/gps_raw"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"led-gps-{dev}")
    client.on_message = on_message
    client.on_connect = lambda c, *_: c.subscribe(topic, qos=0)
    client.reconnect_delay_set(1, 30)
    client.connect_async(args.broker, args.port, keepalive=30)
    client.loop_start()

    bus = SMBus(1)
    led = Led(bus, args.dc)
    need_init, last_check, last_desc = True, 0.0, None
    print(f"led-gps: following {topic}; red blink = looking for a fix, green blink = fix (fix_type >= "
          f"{args.min_fix})", flush=True)
    try:
        while True:
            now = time.monotonic()
            with state["lock"]:
                ft, age = state["fix_type"], now - state["rx"] if state["rx"] else None
            if age is None or age > args.stale_s:
                fix, desc = False, "looking — no GPS data on MQTT"
            elif ft is not None and ft >= args.min_fix:
                fix, desc = True, f"FIX (fix_type {ft})"
            else:
                fix, desc = False, f"looking — fix_type {ft}"
            if desc != last_desc:
                print(f"led-gps: {desc} -> {'GREEN' if fix else 'RED'} blink", flush=True)
                last_desc = desc
            lit = (now % args.period_s) < args.on_s
            try:
                if need_init:
                    led.init()
                    need_init = False
                elif now - last_check >= 30:
                    last_check = now
                    if not led.alive():
                        print("led-gps: LP5815 lost CHIP_EN (reset?) — re-initialising", flush=True)
                        led.init()
                led.set(args.pwm if (lit and not fix) else 0, args.pwm if (lit and fix) else 0)
            except OSError as e:
                if not need_init:
                    print(f"led-gps: I2C error {e}; re-initialising", flush=True)
                need_init = True
                time.sleep(1.0)
                continue
            # wake at the next on/off edge (at most 0.25 s, so a fix change shows quickly)
            t = now % args.period_s
            edge = args.on_s - t if t < args.on_s else args.period_s - t
            time.sleep(max(0.02, min(0.25, edge)))
    finally:
        try:
            led.off()
        except OSError:
            pass
        client.loop_stop()
        print("led-gps: stopped; LED off, LP5815 in standby", flush=True)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
