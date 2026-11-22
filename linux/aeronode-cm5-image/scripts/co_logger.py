#!/usr/bin/env python3
"""co_logger.py — the Blackbox board's CO channel onto AeroNode's Live page, plus a CSV log.

Peter 2026-11-22: "Add CO to the web page" -> "Own CO service" (not a patch to ALFA's AeroNode collector).

SIGNAL CHAIN [repo: schematic p.6; MEMORY 2026-11-17/19]: TGS5141-P00 electrochemical CO cell (~2 nA/ppm) ->
TLV8811 transimpedance, R36 1 MOhm || C44 1 uF (tau 1 s) -> ADS1115 AIN0, I2C-1 0x48. So ~2 mV/ppm NOMINAL.
  * UNCALIBRATED: TGS5141 sensitivity spreads ~2:1, so co_ppm is INDICATIVE (x0.5..x2). Cross-sensitive to H2 and
    ethanol. Response proven with a blown-out match on 2026-11-19 (+27.7 mV peak, right polarity).
  * Clean air sits only a few mV above the 0 V rail (4-9 mV seen). A negative offset or a dead cell ALSO reads 0 V,
    so "railed" (co_mv < --rail-mv) means "can't tell clean air from a fault" and sets valid = false.
  * co_ppm = max(0, (co_mv - --zero-mv) / --mv-per-ppm), zero 5 mV, 2 mV/ppm.

WHAT IT DOES, every --period s (1 s):
  * reads AIN0 single-ended, single-shot 128 SPS, auto-ranging (+-0.256 / 2.048 / 4.096 V), --avg reads averaged;
  * appends a row to --out (~/aeronode/logs/co.csv, fsync'd);
  * publishes AeroNode's own message shape {"type":"sensor","sensor":"co","ts":...,"data":{...}} (sync/protocol.py
    make_msg) to <topic_prefix>/<AERONODE_DEVICE_ID>/co on the local broker. The Live page's "More streams" section
    draws a tile for every stream listed in config.toml [collector.store_rates] — so BB1's config.toml carries
    `co = 1` there. LIVE ONLY: the collector does not ingest this stream, so it is NOT in flights.db / session
    history; the CSV is the record.
  * no broker -> keeps logging the CSV and retries in the background.
It writes only the ADS1115's config register (single-shot conversions) and on exit restores the power-up config
0x8583 (what bb_check expects). ArduPilot does not use the ADS1115 on BB1 (hwdef has no ADS1115 line).
"""
import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

from smbus2 import SMBus

ADDR = 0x48
RANGES = [(5, 0.256), (2, 2.048), (1, 4.096)]          # (PGA bits, full scale V), finest first
FIELDS = ["ts_utc", "up_s", "co_mv", "range_v", "co_ppm", "railed", "valid", "mqtt"]


def read_ain0(bus, pga: int, fsr: float):
    cfg = 0x8000 | (4 << 12) | (pga << 9) | 0x0100 | (4 << 5) | 0x0003   # OS, AIN0-GND, PGA, single-shot, 128 SPS
    bus.write_i2c_block_data(ADDR, 0x01, [cfg >> 8, cfg & 0xFF])
    time.sleep(0.009)
    for _ in range(20):
        if bus.read_i2c_block_data(ADDR, 0x01, 2)[0] & 0x80:
            break
        time.sleep(0.002)
    hi, lo = bus.read_i2c_block_data(ADDR, 0x00, 2)
    raw = (hi << 8) | lo
    raw = raw - 65536 if raw & 0x8000 else raw
    return raw * fsr / 32768.0, raw


def read_auto(bus, n: int):
    """Finest range that is not near full scale, then n reads averaged on it. Returns (volts, full-scale V)."""
    for pga, fsr in RANGES:
        v, raw = read_ain0(bus, pga, fsr)
        if abs(raw) < 30000:
            break
    vals = [v] + [read_ain0(bus, pga, fsr)[0] for _ in range(max(0, n - 1))]
    return sum(vals) / len(vals), fsr


def device_id(env_path: str, fallback: str) -> str:
    try:
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("AERONODE_DEVICE_ID="):
                    return line.split("=", 1)[1].strip().strip('"\'') or fallback
    except OSError:
        pass
    return fallback


def open_csv(path: str, max_mb: float):
    if os.path.exists(path):
        with open(path) as f:
            hdr = f.readline().strip()
        if hdr != ",".join(FIELDS):
            os.replace(path, path + time.strftime(".old-%Y%m%dT%H%M%SZ", time.gmtime()))
        elif os.path.getsize(path) > max_mb * 1e6:
            os.replace(path, path + ".1")
    new = not os.path.exists(path)
    fh = open(path, "a", buffering=1)
    if new:
        fh.write(",".join(FIELDS) + "\n")
    return fh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/home/node/aeronode/logs/co.csv")
    ap.add_argument("--period", type=float, default=1.0)
    ap.add_argument("--avg", type=int, default=4, help="ADC reads averaged per sample")
    ap.add_argument("--max-mb", type=float, default=20.0, help="rotate the CSV to .1 above this (checked hourly)")
    ap.add_argument("--zero-mv", type=float, default=5.0, help="clean-air reading, mV (uncalibrated)")
    ap.add_argument("--mv-per-ppm", type=float, default=2.0, help="nominal 2 nA/ppm x 1 MOhm")
    ap.add_argument("--rail-mv", type=float, default=1.0, help="below this the reading is 'railed' (valid=false)")
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic-prefix", default="aeronode")
    ap.add_argument("--env", default="/home/node/aeronode/.env", help="AeroNode .env (AERONODE_DEVICE_ID)")
    ap.add_argument("--device-id", default="", help="override the device id in the topic")
    ap.add_argument("--no-mqtt", action="store_true")
    ap.add_argument("--once", action="store_true", help="print one reading, write and publish nothing")
    args = ap.parse_args()

    bus = SMBus(1)
    if args.once:
        v, fsr = read_auto(bus, args.avg)
        mv = v * 1e3
        print(f"CO AIN0 {mv:.2f} mV (+-{fsr} V range) ~{max(0.0, (mv - args.zero_mv) / args.mv_per_ppm):.1f} ppm "
              f"indicative{' — RAILED' if mv < args.rail_mv else ''}")
        return

    dev = args.device_id or device_id(args.env, "BB1")
    topic = f"{args.topic_prefix}/{dev}/co"
    client = None
    if not args.no_mqtt:
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"co-logger-{dev}")
            client.reconnect_delay_set(1, 30)
            client.connect_async(args.broker, args.port, keepalive=30)
            client.loop_start()
        except Exception as e:  # noqa: BLE001 — the CSV must keep going without MQTT
            print(f"co_logger: MQTT unavailable ({e}); CSV only", flush=True)
            client = None

    fh = open_csv(args.out, args.max_mb)
    print(f"co_logger: {args.out} every {args.period:g} s; MQTT {topic if client else 'off'}", flush=True)
    last_report = 0.0
    n = 0
    err = None
    try:
        while True:
            t0 = time.monotonic()
            try:
                v, fsr = read_auto(bus, args.avg)
                err = None
            except OSError as e:
                if str(e) != err:
                    print(f"co_logger: I2C error {e}; retrying", flush=True)
                err = str(e)
                time.sleep(args.period)
                continue
            mv = v * 1e3
            railed = mv < args.rail_mv
            ppm = max(0.0, (mv - args.zero_mv) / args.mv_per_ppm)
            data = {"co_ppm": round(ppm, 1), "co_mv": round(mv, 2), "range_v": fsr, "railed": railed,
                    "valid": not railed, "calibrated": False, "mv_per_ppm": args.mv_per_ppm,
                    "zero_mv": args.zero_mv}
            sent = False
            if client is not None and client.is_connected():
                msg = json.dumps({"type": "sensor", "sensor": "co",
                                  "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                                  "data": data}, separators=(",", ":"))
                sent = client.publish(topic, msg, qos=0).rc == 0
            ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() % 1 * 1000):03d}"
            row = [ts, round(time.clock_gettime(time.CLOCK_BOOTTIME), 1), data["co_mv"], fsr, data["co_ppm"],
                   int(railed), int(not railed), int(sent)]
            fh.write(",".join(str(x) for x in row) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            n += 1
            if n % 3600 == 0 and os.path.getsize(args.out) > args.max_mb * 1e6:
                fh.close()
                fh = open_csv(args.out, args.max_mb)
            if t0 - last_report >= 600:
                print(f"co_logger: {mv:.2f} mV ~{ppm:.1f} ppm (indicative){' RAILED' if railed else ''}, "
                      f"MQTT {'ok' if sent else 'not sent'}", flush=True)
                last_report = t0
            time.sleep(max(0.0, args.period - (time.monotonic() - t0)))
    finally:
        try:
            bus.write_i2c_block_data(ADDR, 0x01, [0x85, 0x83])     # power-up config, as bb_check expects
        except OSError:
            pass
        if client is not None:
            client.loop_stop()
        print("co_logger: stopped; ADS1115 config restored", flush=True)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
