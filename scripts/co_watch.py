#!/usr/bin/env python3
"""co_watch.py - live read of the Blackbox board CO channel (TGS5141 -> TLV8811 -> ADS1115 AIN0 @ 0x48).
~2 mV per ppm (2 nA/ppm x 1 MOhm), uncalibrated. Usage: co_watch.py [seconds]. Logs to /tmp/co_watch.log."""
import sys, time, smbus2

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
b = smbus2.SMBus(1); A = 0x48
RANGES = [(5, 0.256), (2, 2.048), (1, 4.096)]  # (PGA bits, full scale V)


def read(pga, fsr):
    cfg = 0x8000 | (4 << 12) | (pga << 9) | 0x0100 | (4 << 5) | 0x0003  # AIN0-GND, single-shot, 128 SPS
    b.write_i2c_block_data(A, 0x01, [cfg >> 8, cfg & 0xFF]); time.sleep(0.012)
    while not (b.read_i2c_block_data(A, 0x01, 2)[0] & 0x80):
        time.sleep(0.002)
    hi, lo = b.read_i2c_block_data(A, 0x00, 2); raw = (hi << 8) | lo
    raw = raw - 65536 if raw & 0x8000 else raw
    return raw * fsr / 32768, raw


def auto():
    for pga, fsr in RANGES:  # finest range that is not near full scale
        v, raw = read(pga, fsr)
        if abs(raw) < 30000:
            return v, fsr
    return v, fsr


log = open("/tmp/co_watch.log", "w")
t0 = time.time(); base = []
print(f"CO watch for {DUR:.0f} s - first 10 s = baseline. ~2 mV/ppm, uncalibrated.", flush=True)
try:
    while time.time() - t0 < DUR:
        v, fsr = auto(); t = time.time() - t0; mv = v * 1e3
        if t < 10:
            base.append(mv)
        b0 = sum(base) / len(base) if base else 0.0
        d = mv - b0
        bar = "#" * min(60, max(0, int(d / 2)))
        line = f"{t:6.1f}s  {mv:8.2f} mV  ~{mv / 2:6.1f} ppm  {d:+8.2f} mV vs base  ±{fsr:.3f}V  {bar}"
        print(line, flush=True); log.write(line + "\n"); log.flush()
        time.sleep(max(0.0, 0.5 - (time.time() - t0 - t)))
finally:
    b.write_i2c_block_data(A, 0x01, [0x85, 0x83])  # power-up config, as bb_check expects
    print("done; ADC config restored", flush=True)
