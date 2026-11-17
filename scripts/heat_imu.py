#!/usr/bin/env python3
"""heat_imu.py - hold the AeroImu thermal island at a set temperature with the board heater (GPIO12).

Blackbox AeroNode HW 0.0.2 rev 1. heater_control = GPIO12 -> J11.5 -> heater on the thermal island (5 W, NO hardware
cut-off). Feedback = the ICM-45686's own temperature (same island). Run as root under systemd-run with an
ExecStopPost that forces GPIO12 low, so the pin goes low however this process ends.

Usage: heat_imu.py [setpoint_C] [hold_s]      defaults 35.0 C, 900 s
Exit codes: 0 done, 2 over-temperature, 3 IMU read fault, 4 heater not reaching the IMU, 5 CPU hot, 6 signal.
"""
import math, signal, subprocess, sys, time

sys.path.insert(0, "/home/node/aeronode/scripts/bb")
import bb_check as bb  # noqa: E402  (IMU SPI path, already proven on this board)

SET = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0
HOLD_S = float(sys.argv[2]) if len(sys.argv) > 2 else 900.0
T_CUT = 40.0          # hard cut on the IMU temperature
CPU_CUT = 80.0
# Tuned from run 1 (2026-11-17): ~1.8 s at full power took the island 26 -> 40.8 C, and it cools with tau ~20-30 s.
# So the island is ~0.6-0.8 J/K and +9 C needs ~0.3 W (~6 % duty). 10 % max settles a few C below the 40 C cut.
DUTY_MAX = 0.10       # never more than 10 % heater power
KP, KI = 0.02, 0.0005 # duty per degC, duty per degC*s
I_MAX = 0.08
PERIOD = 0.5          # time-proportioning window, s (10 % = 50 ms pulses)
RATE_MAX = 1.0        # degC/s: skip heating while the IMU climbs faster than this
STALL_ON_S = 10.0     # full-power-equivalent seconds of heating that must give >= STALL_RISE
STALL_RISE = 1.0


def heater(on: bool) -> None:
    subprocess.run(["pinctrl", "set", "12", "op", "dh" if on else "dl"], check=True)


def cpu_c() -> float:
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.read()) / 1000.0


def stop(code: int, why: str) -> None:
    heater(False)
    try:
        bb.imu_write(hw, 0x10, 0x00)  # sensors back off, as bb_check leaves them
    except Exception:
        pass
    print(f"STOP {code}: {why}; heater pin -> {subprocess.run(['pinctrl', 'get', '12'], capture_output=True, text=True).stdout.strip()}", flush=True)
    sys.exit(code)


hw = bb.Hw()
signal.signal(signal.SIGTERM, lambda *_: stop(6, "SIGTERM"))
signal.signal(signal.SIGINT, lambda *_: stop(6, "SIGINT"))

try:
    heater(False)
    who = [bb.imu_read(hw, 0x72, 1)[0] for _ in range(3)]
    if who != [0xE9] * 3:
        stop(3, f"WHO_AM_I {who}, expected 0xE9")
    bb.imu_write(hw, 0x10, 0x0F)  # PWR_MGMT0: accel + gyro LN, so TEMP_DATA updates
    time.sleep(0.2)

    def temp() -> float:
        t = bb.read_imu(hw)["temp_c"]
        if not (-20.0 < t < 85.0) or math.isnan(t):
            stop(3, f"IMU temperature reads {t}")
        return t

    t0 = temp()
    print(f"start: IMU {t0:.2f} C, setpoint {SET:.1f} C, hard cut {T_CUT:.1f} C, max duty {DUTY_MAX:.0%}, hold {HOLD_S:.0f} s", flush=True)
    if t0 >= SET:
        stop(0, "already at or above the setpoint")

    integ, on_s, start, reached, last_log, k = 0.0, 0.0, time.time(), None, 0.0, 0
    t_prev, tm_prev = t0, time.time()
    while True:
        t = temp()
        now = time.time()
        rate = (t - t_prev) / max(1e-3, now - tm_prev)
        t_prev, tm_prev = t, now
        if t >= T_CUT:
            stop(2, f"IMU {t:.2f} C >= {T_CUT} C")
        if cpu_c() >= CPU_CUT:
            stop(5, f"CPU {cpu_c():.1f} C")
        err = SET - t
        if reached is None and t >= SET - 0.2:
            reached = time.time()
            print(f"reached {t:.2f} C after {reached - start:.0f} s; holding {HOLD_S:.0f} s", flush=True)
        if abs(err) < 3.0:  # integrate only within 3 C of the setpoint (anti-windup)
            integ = min(I_MAX, max(0.0, integ + KI * err * PERIOD))
        duty = min(DUTY_MAX, max(0.0, KP * err + integ))
        if rate > RATE_MAX:
            duty = 0.0
        if reached is None and on_s >= STALL_ON_S and t - t0 < STALL_RISE:
            stop(4, f"{on_s:.0f} s of heating raised the IMU only {t - t0:+.2f} C")
        if duty > 0:
            heater(True); time.sleep(duty * PERIOD)
        heater(False); time.sleep((1 - duty) * PERIOD)
        on_s += duty * PERIOD
        k += 1
        if time.time() - last_log >= 5:
            last_log = time.time()
            print(f"t={time.time() - start:6.0f}s IMU {t:6.2f} C  duty {duty:4.1%}  I {integ:.3f}  rate {rate:+.2f} C/s  heater-on {on_s:5.1f}s  CPU {cpu_c():.1f} C", flush=True)
        if reached is not None and time.time() - reached >= HOLD_S:
            stop(0, f"held {HOLD_S:.0f} s at {SET:.1f} C")
except SystemExit:
    raise
except BaseException as e:  # any surprise: heater off first
    stop(3, f"{type(e).__name__}: {e}")
finally:
    heater(False)
