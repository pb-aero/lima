#!/usr/bin/env python3
"""Listen to ArduPlane over MAVLink for N seconds and summarise what it says.

usage: mav_probe.py [conn] [seconds]   default udpin:127.0.0.1:14551 30
Prints: heartbeat, every STATUSTEXT, sensor present/enabled/healthy bits,
the latest ATTITUDE / RAW_IMU / SCALED_PRESSURE / EKF_STATUS_REPORT, and rates.
"""
import math
import sys
import time
from collections import Counter

from pymavlink import mavutil

conn = sys.argv[1] if len(sys.argv) > 1 else "udpin:127.0.0.1:14551"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

m = mavutil.mavlink_connection(conn, source_system=254)
hb = m.wait_heartbeat(timeout=40)
if hb is None:
    print("NO HEARTBEAT within 40 s")
    sys.exit(2)
print(f"HEARTBEAT sys={m.target_system} type={hb.type} autopilot={hb.autopilot} "
      f"mavlink={hb.mavlink_version} mode={mavutil.mode_string_v10(hb)}")

for sid in (mavutil.mavlink.MAV_DATA_STREAM_ALL,):
    m.mav.request_data_stream_send(m.target_system, m.target_component, sid, 10, 1)
for name in sys.argv[3:]:
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)

S = mavutil.mavlink
SENS = {
    S.MAV_SYS_STATUS_SENSOR_3D_GYRO: "gyro", S.MAV_SYS_STATUS_SENSOR_3D_ACCEL: "accel",
    S.MAV_SYS_STATUS_SENSOR_3D_MAG: "mag", S.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE: "baro",
    S.MAV_SYS_STATUS_SENSOR_GPS: "gps", S.MAV_SYS_STATUS_AHRS: "ahrs",
}
last = {}
counts = Counter()
last_ekf = None
last_fix = None
t0 = time.time()
while time.time() - t0 < secs:
    msg = m.recv_match(blocking=True, timeout=1)
    if msg is None:
        continue
    t = msg.get_type()
    counts[t] += 1
    last[t] = msg
    if t == "STATUSTEXT":
        print(f"  {time.time()-t0:5.1f}s STATUSTEXT sev={msg.severity}: {msg.text}")
    elif t == "PARAM_VALUE" and msg.param_id in sys.argv[3:]:
        print(f"  PARAM {msg.param_id} = {msg.param_value:g}")
    elif t == "EKF_STATUS_REPORT" and (counts[t] % 100 == 1 or msg.flags != last_ekf):
        print(f"  {time.time()-t0:5.1f}s EKF flags 0x{msg.flags:04x}")
        last_ekf = msg.flags
    elif t == "GPS_RAW_INT" and msg.fix_type != last_fix:
        print(f"  {time.time()-t0:5.1f}s GPS fix_type {msg.fix_type} sats {msg.satellites_visible}")
        last_fix = msg.fix_type

dt = time.time() - t0
print(f"\n--- {dt:.0f} s, message rates (Hz) ---")
print("  " + ", ".join(f"{k} {v/dt:.1f}" for k, v in sorted(counts.items())))

ss = last.get("SYS_STATUS")
if ss:
    print("--- SYS_STATUS sensors: present / enabled / healthy ---")
    for bit, name in SENS.items():
        p, e, h = (bool(ss.onboard_control_sensors_present & bit),
                   bool(ss.onboard_control_sensors_enabled & bit),
                   bool(ss.onboard_control_sensors_health & bit))
        print(f"  {name:6s} {int(p)} {int(e)} {int(h)}")
    print(f"  load {ss.load/10:.1f}%  vbat {ss.voltage_battery/1000:.2f} V")
a = last.get("ATTITUDE")
if a:
    print(f"ATTITUDE roll {math.degrees(a.roll):+.2f} pitch {math.degrees(a.pitch):+.2f} "
          f"yaw {math.degrees(a.yaw):+.2f} deg")
r = last.get("RAW_IMU") or last.get("SCALED_IMU")
if r:
    print(f"{r.get_type()} acc {r.xacc} {r.yacc} {r.zacc}  gyr {r.xgyro} {r.ygyro} {r.zgyro}  "
          f"mag {r.xmag} {r.ymag} {r.zmag}")
p = last.get("SCALED_PRESSURE")
if p:
    print(f"SCALED_PRESSURE {p.press_abs:.2f} hPa  {p.temperature/100:.2f} C")
e = last.get("EKF_STATUS_REPORT")
if e:
    print(f"EKF_STATUS_REPORT flags 0x{e.flags:04x} (bit10 uninitialized={bool(e.flags & 1024)}) "
          f"vel {e.velocity_variance:.2f} pos_h {e.pos_horiz_variance:.2f} "
          f"compass {e.compass_variance:.2f}")
g = last.get("GPS_RAW_INT")
if g:  # deliberately no lat/lon: position is private and never goes in a log or commit
    print(f"GPS_RAW_INT fix_type {g.fix_type} sats {g.satellites_visible} "
          f"hdop {g.eph/100:.2f} vel {g.vel/100:.2f} m/s")
o = last.get("GPS_GLOBAL_ORIGIN")
if o:
    print("GPS_GLOBAL_ORIGIN set (EKF origin established)")
v = last.get("VIBRATION")
if v:
    print(f"VIBRATION {v.vibration_x:.3f} {v.vibration_y:.3f} {v.vibration_z:.3f}")
