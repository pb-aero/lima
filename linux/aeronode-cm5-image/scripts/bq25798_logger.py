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

STATE OF CHARGE (an ESTIMATE — this is not a fuel gauge). Pack per Peter 2026-11-19: Li-ion, 7.2 V nominal
(= 2 cells in series; he read "4S" — 4 cells, so 2S2P), 5 Ah. Charger is strapped 2S, VREG 8.40 V.
  * At logger start: SoC from the open-circuit voltage, OCV = VBAT - IBAT x R (R = --r-ohm, 0.30 ohm
    measured from the 2026-11-19 unplug step: 0.29-0.34 ohm incl. wiring/BATFET), per cell, through a
    GENERIC Li-ion (NMC/NCA) rest curve [assumed — the pack's own curve is unknown].
  * ON BATTERY (no input): coulomb counting from the IBAT ADC — verified right when discharging.
  * CHARGING: the IBAT ADC UNDER-READS here (2026-11-19: ~0.1 A shown while the power balance and the VBAT
    step said ~0.33 A), so the charge current is ESTIMATED as (VBUS*IBUS - P_sys) * eta / VBAT, with BB1's
    own input-side draw P_sys (default 2.85 W, measured with charging paused) re-learned whenever input is
    present but not charging. SoC then follows the IR-corrected voltage (smoothed, never backwards while
    charging, capped at 97 % in the CV/taper phase where the voltage is pinned at VREG).
  * 100 % when the charger reports DONE. Input present + not charging: held. Every start re-anchors from
    voltage (a power cut may hide a charge in between).
  * min_left (discharging) / min_to_full (charging) from a ~1 min average of that battery current.
  * ibat_ma stays the raw ADC value; ichg_est_ma / mah_in use the estimate while charging.
Expect it to be off by ~10 % until a first full charge anchors it; worst near empty and on the 3.6-3.8 V/cell
plateau.

WEB PAGE (Peter 2026-11-19: "show the battery percent on the aeronode web page"): every --db-every samples a
row goes into AeroNode's existing `power_ups` table in data/device_health.db — the table the PiPower5 UPS would
fill (absent on BB1). aeronode-web's /api/device/battery reads its newest row (stale after 60 s) and the Device
page shows it as "UPS battery %" — no AeroNode code or UI change. Mapping: input = VBUS/IBUS, output = VSYS,
battery = VBAT/IBAT (charge +), battery_percent = the estimate above, power_source 'external' when the charger
reports power-good else 'battery', charging = an active charge phase. A DB error never stops the CSV log.

Register map, byte order and scales from TI SLUSDV2C (Jun 2026): 16-bit ADC registers, MSB at the lower
offset; IBUS/IBAT/TDIE two's complement; 1 mA / 1 mV steps; TS 0.0976563 %/LSB; TDIE 0.5 C/LSB.
"""
import argparse
import os
import sqlite3
import sys
import time

from smbus2 import SMBus

ADDR = 0x6B
CHG_STAT = ["not charging", "trickle", "pre-charge", "fast (CC)", "taper (CV)", "reserved", "top-off", "done"]
VBUS_STAT = {0: "no input", 1: "USB SDP", 2: "USB CDP", 3: "USB DCP", 4: "HVDCP", 5: "unknown adapter",
             6: "non-standard adapter", 7: "OTG", 8: "not qualified", 0xB: "powered from VBUS"}
FIELDS = ["ts_utc", "up_s", "vbat_mv", "ibat_ma", "vbus_mv", "ibus_ma", "vac1_mv", "vac2_mv", "vsys_mv",
          "ts_pct", "tdie_c", "chg_stat", "vbus_stat", "pg", "faults", "mah_in", "mah_out",
          "p_in_w", "ichg_est_ma", "ocv_cell_mv", "soc_pct", "soc_src", "ibat_avg_ma", "min_left", "min_to_full"]

# Generic Li-ion (NMC/NCA) open-circuit voltage per cell -> % [assumed; typical 18650 rest curve]
OCV_CURVE = [(3000, 0), (3300, 2), (3450, 5), (3550, 10), (3620, 15), (3670, 20), (3700, 30), (3730, 40),
             (3770, 50), (3820, 60), (3880, 70), (3950, 80), (4040, 90), (4100, 95), (4200, 100)]


def soc_from_ocv(cell_mv: float) -> float:
    if cell_mv <= OCV_CURVE[0][0]:
        return 0.0
    for (v0, p0), (v1, p1) in zip(OCV_CURVE, OCV_CURVE[1:]):
        if cell_mv <= v1:
            return p0 + (p1 - p0) * (cell_mv - v0) / (v1 - v0)
    return 100.0


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


CHARGING_PHASES = {"trickle", "pre-charge", "fast (CC)", "taper (CV)", "top-off"}


def db_insert(path: str, s: dict) -> None:
    """One power_ups row (AeroNode schema.py) — what the web page's battery card reads."""
    now = time.time()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)) + f".{int(now % 1 * 1000):03d}"   # naive UTC
    soc = s.get("soc_pct")
    with sqlite3.connect(path, timeout=5) as conn:
        conn.execute(
            "INSERT INTO power_ups (ts, ts_ms, input_voltage_mv, input_current_ma, output_voltage_mv, "
            "output_current_ma, battery_voltage_mv, battery_current_ma, battery_percent, power_source, "
            "usb_plugged, charging, shutdown_request) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, int(now * 1000), s["vbus_mv"], s["ibus_ma"], s["vsys_mv"], None, s["vbat_mv"],
             s["ichg_est_ma"] if s.get("ichg_est_ma") not in ("", None) else s["ibat_ma"],
             round(soc) if soc != "" and soc is not None else None, "external" if s["pg"] else "battery",
             s["pg"], int(s["chg_stat"] in CHARGING_PHASES), 0))
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/home/node/aeronode/logs/battery.csv")
    ap.add_argument("--period", type=float, default=2.0)
    ap.add_argument("--once", action="store_true", help="one read, no writes")
    ap.add_argument("--max-mb", type=float, default=50.0, help="rotate the CSV to .1 when bigger at start")
    ap.add_argument("--capacity-mah", type=float, default=5000.0)
    ap.add_argument("--cells", type=int, default=2, help="cells in SERIES")
    ap.add_argument("--r-ohm", type=float, default=0.30, help="pack resistance for the OCV correction")
    ap.add_argument("--eta", type=float, default=0.90, help="charger efficiency for the charge-current estimate")
    ap.add_argument("--p-sys-w", type=float, default=2.85,
                    help="BB1's own draw seen at the input, W (measured 2.85 W at 1.5 GHz with charging paused); "
                         "re-measured live whenever input is present and the charger is not charging")
    ap.add_argument("--db", default="/home/node/aeronode/data/device_health.db",
                    help="AeroNode health DB for the web page's battery card ('' = off)")
    ap.add_argument("--db-every", type=int, default=5, help="write a power_ups row every N samples")
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

        if os.path.exists(args.out):
            with open(args.out) as f:
                old_header = f.readline().strip()
            if old_header != ",".join(FIELDS):          # columns changed: keep the old file aside
                os.replace(args.out, args.out + time.strftime(".old-%Y%m%dT%H%M%SZ", time.gmtime()))
            elif os.path.getsize(args.out) > args.max_mb * 1e6:
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
        soc = None                      # % estimate (float)
        soc_src = ""
        v_soc_avg = None                # smoothed voltage-based % while charging
        p_sys_in = args.p_sys_w         # system draw seen at the INPUT (W), recalibrated when not charging
        i_avg = None                    # ~1 min average of the battery current actually used (mA)
        alpha = 2.0 / (30 + 1)          # ~1 min EMA at 2 s samples
        last_report = 0.0
        n_samples = 0
        db_err = None
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
            # Which current to trust. IBAT ADC: right when DISCHARGING (matched the board's draw), but it
            # UNDER-READS while charging (2026-11-19: ~0.1 A shown vs ~0.33 A by power balance). So while
            # charging, estimate the charge current from the input power instead:
            #   I_chg = (VBUS*IBUS - P_sys_in) * eta / VBAT
            # where P_sys_in (BB1's own draw, seen at the input) is re-measured whenever input is present
            # but the charger is not charging (e.g. after DONE).
            p_in = s["vbus_mv"] * s["ibus_ma"] / 1e6
            charging = bool(s["pg"]) and s["chg_stat"] in CHARGING_PHASES
            if s["pg"] and s["chg_stat"] in ("not charging", "done") and p_in > 0.5:
                p_sys_in += 0.1 * (p_in - p_sys_in)
            if charging and s["vbat_mv"] > 0:
                i_used = max(0.0, (p_in - p_sys_in) * args.eta / (s["vbat_mv"] / 1000.0) * 1000.0)
            elif not s["pg"]:
                i_used = float(s["ibat_ma"])          # battery only: the ADC is trustworthy here
            else:
                i_used = 0.0                          # input present, not charging: pack idle
            s["p_in_w"], s["ichg_est_ma"] = round(p_in, 2), (round(i_used) if charging else "")

            if last_t is not None:
                dh = (t0 - last_t) / 3600.0
                if i_used >= 0:
                    mah_in += i_used * dh
                else:
                    mah_out += -i_used * dh
                if soc is not None and not s["pg"]:       # discharging: coulomb counting
                    soc -= 100.0 * (-i_used if i_used < 0 else 0.0) * dh / args.capacity_mah
            last_t = t0
            s["mah_in"], s["mah_out"] = round(mah_in, 2), round(mah_out, 2)

            ocv_cell = (s["vbat_mv"] - i_used * args.r_ohm) / args.cells
            s["ocv_cell_mv"] = round(ocv_cell)
            if s["vbat_mv"] <= 0:
                pass
            elif s["chg_stat"] == "done":
                soc, soc_src = 100.0, "full"
            elif soc is None:
                soc, soc_src = soc_from_ocv(ocv_cell), "voltage"
            elif charging:
                # voltage-based while charging (IR-corrected with the estimated current), smoothed, never
                # moving backwards; in the CV/taper phase the voltage is pinned near VREG, so cap at 97 %
                v = soc_from_ocv(ocv_cell)
                if s["chg_stat"] in ("taper (CV)", "top-off"):
                    v = min(v, 97.0)
                v_soc_avg = v if v_soc_avg is None else v_soc_avg + 0.05 * (v - v_soc_avg)
                soc, soc_src = max(soc, v_soc_avg), "charging (voltage)"
            elif not s["pg"]:
                soc_src = "battery (coulomb)"
            if not charging:
                v_soc_avg = None
            if soc is not None:
                soc = min(100.0, max(0.0, soc))
            s["soc_pct"], s["soc_src"] = (round(soc, 1) if soc is not None else ""), soc_src
            i_avg = i_used if i_avg is None else i_avg + alpha * (i_used - i_avg)
            s["ibat_avg_ma"] = round(i_avg)
            s["min_left"] = round(soc / 100 * args.capacity_mah / -i_avg * 60) if soc is not None and i_avg < -50 else ""
            s["min_to_full"] = (round((100 - soc) / 100 * args.capacity_mah / i_avg * 60)
                                if soc is not None and i_avg > 50 else "")
            if t0 - last_report >= 600 and soc is not None:   # a journal line every 10 min
                left = (f", ~{s['min_left']} min left" if s["min_left"] != "" else
                        f", ~{s['min_to_full']} min to full" if s["min_to_full"] != "" else "")
                print(f"bq25798: battery ~{s['soc_pct']} % ({s['soc_src']}), VBAT {s['vbat_mv']} mV, "
                      f"battery current avg {s['ibat_avg_ma']} mA, input {s['p_in_w']} W, "
                      f"system ~{p_sys_in:.2f} W{left}", flush=True)
                last_report = t0
            s["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() % 1 * 1000):03d}"
            s["up_s"] = round(time.clock_gettime(time.CLOCK_BOOTTIME), 1)
            fh.write(",".join(str(s[k]) for k in FIELDS) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            n_samples += 1
            if args.db and n_samples % args.db_every == 1:
                try:
                    db_insert(args.db, s)
                    db_err = None
                except sqlite3.Error as e:
                    if str(e) != db_err:
                        print(f"bq25798 logger: web DB write failed: {e} (CSV unaffected)", flush=True)
                    db_err = str(e)
            state = (s["chg_stat"], s["vbus_stat"], s["pg"], s["faults"])
            if state != last_state:
                print(f"bq25798: {s['chg_stat']}, input {s['vbus_stat']}, power-good {s['pg']}, faults {s['faults']}; "
                      f"VBAT {s['vbat_mv']} mV, IBAT {s['ibat_ma']} mA, VBUS {s['vbus_mv']} mV", flush=True)
                last_state = state
            time.sleep(max(0.0, args.period - (time.monotonic() - t0)))


if __name__ == "__main__":
    main()
