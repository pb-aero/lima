#!/usr/bin/env python3
"""bq25798_logger.py — battery + input logging from the Blackbox board's BQ25798 charger (I2C-1, 0x6B).

Peter 2026-11-19: "Yes, log it". The board has NO fuel gauge; the charger's own ADC measures
VBAT, IBAT (charge +, discharge -), VBUS/IBUS, VAC1/2, VSYS, TS and the die temperature. This logs
them every --period s to a CSV (fsync'd every row, so the last reading before a power cut survives)
and keeps a running coulomb count (mAh in/out since the logger started).

WRITES — exactly three, none touches charging limits (VREG/ICHG/IINDPM/VSYSMIN are never written):
  REG2E ADC_Control  = 0x90  ADC_EN=1, continuous, 14-bit, no averaging         [SLUSDV2C 7.5.1.42]
  REG14 bit5 EN_IBAT = 1     (read-modify-write) discharge current in battery-only mode, slightly higher Iq [7.5.1.17]
  REG10 bit3 WD_RST  = 1     (read-modify-write) kick the I2C watchdog                   [7.5.1.13]
ADC_EN and EN_IBAT are "reset by WATCHDOG": if this logger stops, the watchdog (40 s default) expires and
the charger returns to exactly its pin-set defaults — fail-safe. If the watchdog is disabled (REG10[2:0]=0,
e.g. after the 2026-11-17 OTG test), the kick is a harmless no-op.

--once  : read and print one sample, WRITE NOTHING (the ADC may be off -> zeros; it says so).

Register map, byte order and scales from TI SLUSDV2C (Jun 2026): 16-bit ADC registers, MSB at the lower
offset; IBUS/IBAT/TDIE two's complement; 1 mA / 1 mV steps; TS 0.0976563 %/LSB; TDIE 0.5 C/LSB.
"""
import argparse
import os
import sys
import time

from smbus2 import SMBus

ADDR = 0x6B
CHG_STAT = ["not charging", "trickle", "pre-charge", "fast (CC)", "taper (CV)", "reserved", "top-off", "done"]
VBUS_STAT = {0: "no input", 1: "USB SDP", 2: "USB CDP", 3: "USB DCP", 4: "HVDCP", 5: "unknown adapter",
             6: "non-standard adapter", 7: "OTG", 8: "not qualified", 0xB: "powered from VBUS"}
FIELDS = ["ts_utc", "up_s", "vbat_mv", "ibat_ma", "vbus_mv", "ibus_ma", "vac1_mv", "vac2_mv", "vsys_mv",
          "ts_pct", "tdie_c", "chg_stat", "vbus_stat", "pg", "faults", "mah_in", "mah_out"]


def s16(b: bytes) -> int:
    v = b[0] << 8 | b[1]
    return v - 0x10000 if v & 0x8000 else v


def u16(b: bytes) -> int:
    return b[0] << 8 | b[1]


def rd(bus, reg, n=1):
    return bytes(bus.read_i2c_block_data(ADDR, reg, n))


def setup(bus):
    """Enable the ADC + discharge sensing and kick the watchdog. Charging limits are never touched."""
    if rd(bus, 0x2E)[0] != 0x90:
        bus.write_byte_data(ADDR, 0x2E, 0x90)
    r14 = rd(bus, 0x14)[0]
    if not r14 & 0x20:
        bus.write_byte_data(ADDR, 0x14, r14 | 0x20)
    bus.write_byte_data(ADDR, 0x10, rd(bus, 0x10)[0] | 0x08)


def sample(bus) -> dict:
    a = rd(bus, 0x31, 18)          # 0x31..0x42: IBUS IBAT VBUS VAC1 VAC2 VBAT VSYS TS TDIE
    st = rd(bus, 0x1B, 5)          # Charger_Status_0..4
    f = rd(bus, 0x20, 2)           # FAULT_Status_0..1
    return {
        "ibus_ma": s16(a[0:2]), "ibat_ma": s16(a[2:4]), "vbus_mv": u16(a[4:6]), "vac1_mv": u16(a[6:8]),
        "vac2_mv": u16(a[8:10]), "vbat_mv": u16(a[10:12]), "vsys_mv": u16(a[12:14]),
        "ts_pct": round(u16(a[14:16]) * 0.0976563, 1), "tdie_c": s16(a[16:18]) * 0.5,
        "chg_stat": CHG_STAT[(st[1] >> 5) & 7], "vbus_stat": VBUS_STAT.get((st[1] >> 1) & 0xF, f"code {(st[1] >> 1) & 0xF}"),
        "pg": int(bool(st[0] & 0x08)), "faults": f"{f[0]:02X}{f[1]:02X}",
        "_adc_en": bool(rd(bus, 0x2E)[0] & 0x80),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/home/node/aeronode/logs/battery.csv")
    ap.add_argument("--period", type=float, default=2.0)
    ap.add_argument("--once", action="store_true", help="one read, no writes")
    ap.add_argument("--max-mb", type=float, default=50.0, help="rotate the CSV to .1 when bigger at start")
    args = ap.parse_args()

    with SMBus(1) as bus:
        part = rd(bus, 0x48)[0]
        if (part >> 3) & 7 != 3:
            sys.exit(f"0x6B REG48=0x{part:02X}: not a BQ25798 (part number {(part >> 3) & 7}, expected 3)")
        if args.once:
            s = sample(bus)
            print(("ADC is ON" if s.pop("_adc_en") else "ADC is OFF (values are stale/zero; nothing written)"))
            for k, v in s.items():
                print(f"  {k:9s} {v}")
            return

        if os.path.exists(args.out) and os.path.getsize(args.out) > args.max_mb * 1e6:
            os.replace(args.out, args.out + ".1")
        new = not os.path.exists(args.out)
        fh = open(args.out, "a", buffering=1)
        if new:
            fh.write(",".join(FIELDS) + "\n")
        setup(bus)
        time.sleep(0.5)                 # first continuous conversion
        print(f"bq25798 logger: {args.out} every {args.period:g} s", flush=True)
        mah_in = mah_out = 0.0
        last_t = None
        last_state = None
        while True:
            t0 = time.monotonic()
            try:
                setup(bus)              # re-arm after any watchdog/POR reset + kick the watchdog
                s = sample(bus)
            except OSError as e:
                print(f"bq25798 logger: I2C error {e}; retrying", flush=True)
                time.sleep(args.period)
                continue
            s.pop("_adc_en")
            if last_t is not None:
                dh = (t0 - last_t) / 3600.0
                if s["ibat_ma"] >= 0:
                    mah_in += s["ibat_ma"] * dh
                else:
                    mah_out += -s["ibat_ma"] * dh
            last_t = t0
            s["mah_in"], s["mah_out"] = round(mah_in, 2), round(mah_out, 2)
            s["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() % 1 * 1000):03d}"
            s["up_s"] = round(time.clock_gettime(time.CLOCK_BOOTTIME), 1)
            fh.write(",".join(str(s[k]) for k in FIELDS) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            state = (s["chg_stat"], s["vbus_stat"], s["pg"], s["faults"])
            if state != last_state:
                print(f"bq25798: {s['chg_stat']}, input {s['vbus_stat']}, power-good {s['pg']}, faults {s['faults']}; "
                      f"VBAT {s['vbat_mv']} mV, IBAT {s['ibat_ma']} mA, VBUS {s['vbus_mv']} mV", flush=True)
                last_state = state
            time.sleep(max(0.0, args.period - (time.monotonic() - t0)))


if __name__ == "__main__":
    main()
