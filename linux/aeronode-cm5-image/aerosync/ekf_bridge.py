#!/usr/bin/env python3
"""
EKF-state bridge: ArduPilot MAVLink -> AeroSync.

RUNS ON THE AERONODE CM5 alongside arduplane.  Subscribes to the MAVLink
endpoint that arduplane.service publishes, extracts the EKF3 state, and emits
it as JSON.

    ./ekf_bridge.py --in udp:127.0.0.1:14550 --out stdout
    ./ekf_bridge.py --in udp:127.0.0.1:14550 --out udp:192.168.4.2:9870
    ./ekf_bridge.py --in udp:127.0.0.1:14550 --out stdout --hz 25

WHAT "EKF DATA" ACTUALLY IS HERE
-------------------------------
ArduPilot has no "dump the EKF" message.  The EKF3 state reaches the outside
world as a set of MAVLink messages, and this is the mapping:

    ATTITUDE            roll/pitch/yaw + body rates   <- EKF output, wound
                        forward to NOW by calcOutputStates() every main loop
    GLOBAL_POSITION_INT lat/lon/alt/vel               <- EKF position solution
    LOCAL_POSITION_NED  NED position + velocity       <- EKF local frame
    EKF_STATUS_REPORT   health flags + variances      <- the EKF's own opinion
                                                         of itself
    VFR_HUD             airspeed/groundspeed/climb

Attitude is NOT delayed by the EKF fusion horizon.  [repo] EKF3 fuses at a
delayed horizon (maxTimeDelay_ms) but calcOutputStates() runs OUTSIDE the
runUpdates block and winds the answer forward to now on every main loop.  The
real attitude age is one main-loop period -- and SCHEDULER_DEFAULT_LOOP_RATE
is 50 Hz for plane, so ~20 ms, before any link latency.

STALENESS IS NOT OPTIONAL
-------------------------
Every field carries the age of the message it came from, and a field whose
source has gone quiet is emitted as null with a fault, never as its last
value.  A feed that keeps rendering its final reading is lying about being
alive.  Set --max-age to taste.
"""
import argparse
import json
import socket
import sys
import time

try:
    from pymavlink import mavutil
except ImportError:
    sys.exit("pip install pymavlink  (or: sudo apt install -y python3-pymavlink)")

# EKF_STATUS_REPORT.flags -- MAV_ESTIMATOR_TYPE bitmask, ardupilotmega dialect
EKF_FLAGS = [
    (1 << 0,  "attitude"),
    (1 << 1,  "velocity_horiz"),
    (1 << 2,  "velocity_vert"),
    (1 << 3,  "pos_horiz_rel"),
    (1 << 4,  "pos_horiz_abs"),
    (1 << 5,  "pos_vert_abs"),
    (1 << 6,  "pos_vert_agl"),
    (1 << 7,  "const_pos_mode"),
    (1 << 8,  "pred_pos_horiz_rel"),
    (1 << 9,  "pred_pos_horiz_abs"),
    (1 << 10, "uninitialized"),
]

# message -> how long its data stays meaningful, in seconds
MAX_AGE_DEFAULT = {
    "ATTITUDE": 0.5,
    "GLOBAL_POSITION_INT": 1.5,
    "LOCAL_POSITION_NED": 1.5,
    "EKF_STATUS_REPORT": 2.0,
    "VFR_HUD": 1.0,
    "GPS_RAW_INT": 3.0,
}


class Latest:
    """Last message of each type, with arrival time. Nothing is ever faked."""

    def __init__(self, max_age):
        self._m = {}
        self.max_age = max_age

    def put(self, msg):
        self._m[msg.get_type()] = (time.monotonic(), msg)

    def get(self, mtype):
        """Returns (msg, age) or (None, age_or_None) when stale/never-seen."""
        got = self._m.get(mtype)
        if got is None:
            return None, None
        t, msg = got
        age = time.monotonic() - t
        if age > self.max_age.get(mtype, 2.0):
            return None, age
        return msg, age


def decode_ekf_flags(flags):
    named = {name: bool(flags & bit) for bit, name in EKF_FLAGS}
    # uninitialized is the one that invalidates everything else.
    named["_healthy"] = (not named["uninitialized"]) and named["attitude"]
    return named


def build_frame(latest):
    """One output record. Missing/stale -> null + a named fault."""
    out = {
        "t_unix": time.time(),
        "schema": "aerosync.ekf/1",
        "source": "ardupilot-ekf3",
        "faults": [],
    }

    def fault(what, age):
        out["faults"].append(
            {"field": what, "reason": "no_data" if age is None else "stale",
             "age_s": None if age is None else round(age, 3)}
        )

    att, age = latest.get("ATTITUDE")
    out["attitude_age_s"] = None if age is None else round(age, 4)
    if att:
        out["attitude"] = {
            "roll_rad": att.roll, "pitch_rad": att.pitch, "yaw_rad": att.yaw,
            "rollspeed": att.rollspeed, "pitchspeed": att.pitchspeed,
            "yawspeed": att.yawspeed,
        }
    else:
        out["attitude"] = None
        fault("attitude", age)

    gpi, age = latest.get("GLOBAL_POSITION_INT")
    if gpi:
        out["position"] = {
            "lat_deg": gpi.lat * 1e-7, "lon_deg": gpi.lon * 1e-7,
            "alt_amsl_m": gpi.alt * 1e-3, "alt_rel_m": gpi.relative_alt * 1e-3,
            "vx_ms": gpi.vx * 1e-2, "vy_ms": gpi.vy * 1e-2, "vz_ms": gpi.vz * 1e-2,
            "hdg_deg": None if gpi.hdg == 65535 else gpi.hdg * 1e-2,
        }
    else:
        out["position"] = None
        fault("position", age)

    ned, age = latest.get("LOCAL_POSITION_NED")
    if ned:
        out["local_ned"] = {"x": ned.x, "y": ned.y, "z": ned.z,
                            "vx": ned.vx, "vy": ned.vy, "vz": ned.vz}
    else:
        out["local_ned"] = None
        fault("local_ned", age)

    ekf, age = latest.get("EKF_STATUS_REPORT")
    if ekf:
        out["ekf_status"] = {
            "flags": decode_ekf_flags(ekf.flags),
            "velocity_variance": ekf.velocity_variance,
            "pos_horiz_variance": ekf.pos_horiz_variance,
            "pos_vert_variance": ekf.pos_vert_variance,
            "compass_variance": ekf.compass_variance,
            "terrain_alt_variance": ekf.terrain_alt_variance,
        }
        # An EKF that says it is uninitialised is not a slow EKF; it is not a
        # solution at all. Surface it as a fault, not a quiet false reading.
        if not out["ekf_status"]["flags"]["_healthy"]:
            out["faults"].append({"field": "ekf_status",
                                  "reason": "ekf_not_healthy",
                                  "flags": out["ekf_status"]["flags"]})
    else:
        out["ekf_status"] = None
        fault("ekf_status", age)

    hud, age = latest.get("VFR_HUD")
    if hud:
        out["air"] = {"airspeed_ms": hud.airspeed, "groundspeed_ms": hud.groundspeed,
                      "alt_m": hud.alt, "climb_ms": hud.climb}
    else:
        out["air"] = None
        fault("air", age)

    out["valid"] = not out["faults"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", default="udp:127.0.0.1:14550",
                    help="MAVLink input, pymavlink connection string")
    ap.add_argument("--out", default="stdout",
                    help="stdout | udp:HOST:PORT")
    ap.add_argument("--hz", type=float, default=10.0, help="output rate")
    ap.add_argument("--max-age", type=float, default=None,
                    help="override every staleness limit, seconds")
    ap.add_argument("--request-rate", type=int, default=25,
                    help="Hz to ask the autopilot to stream at")
    args = ap.parse_args()

    max_age = dict(MAX_AGE_DEFAULT)
    if args.max_age is not None:
        max_age = {k: args.max_age for k in max_age}

    sink = None
    if args.out != "stdout":
        if not args.out.startswith("udp:"):
            sys.exit("--out must be 'stdout' or 'udp:HOST:PORT'")
        _, host, port = args.out.split(":", 2)
        sink = (socket.socket(socket.AF_INET, socket.SOCK_DGRAM), (host, int(port)))

    print(f"# connecting to {args.src}", file=sys.stderr)
    m = mavutil.mavlink_connection(args.src)
    m.wait_heartbeat()
    print(f"# heartbeat from sysid={m.target_system} compid={m.target_component}",
          file=sys.stderr)

    # Ask for a data rate. ArduPilot honours SRx_* params too; this is the
    # per-link request and is the reason attitude can arrive faster than the
    # default 4 Hz ATTITUDE stream.
    m.mav.request_data_stream_send(
        m.target_system, m.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, args.request_rate, 1)

    latest = Latest(max_age)
    period = 1.0 / args.hz
    next_out = time.monotonic()

    while True:
        msg = m.recv_match(blocking=True, timeout=0.2)
        if msg is not None and msg.get_type() in max_age:
            latest.put(msg)

        now = time.monotonic()
        if now >= next_out:
            next_out = now + period
            line = json.dumps(build_frame(latest), separators=(",", ":"))
            if sink:
                sink[0].sendto(line.encode(), sink[1])
            else:
                print(line, flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
