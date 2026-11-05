#!/usr/bin/env python3
"""Offline proof that the bridge's staleness and EKF-health guards FIRE.

Runs anywhere -- no MAVLink link, no hardware.  pymavlink is stubbed if absent.

  python3 test_ekf_bridge.py

A guard with no test is a comment, so each case states its control:
  POSITIVE -- the guard must fire
  NEGATIVE -- the guard must NOT fire on good data
"""
import sys, types, time, os

# Stub pymavlink so the module imports on a machine without it. We only
# exercise build_frame(), which never touches the link.
if "pymavlink" not in sys.modules:
    try:
        import pymavlink  # noqa
    except ImportError:
        pkg = types.ModuleType("pymavlink")
        mu = types.ModuleType("pymavlink.mavutil")
        mu.mavlink = types.SimpleNamespace(MAV_DATA_STREAM_ALL=0)
        mu.mavlink_connection = lambda *a, **k: None
        pkg.mavutil = mu
        sys.modules["pymavlink"] = pkg
        sys.modules["pymavlink.mavutil"] = mu

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ekf_bridge import Latest, build_frame, MAX_AGE_DEFAULT, decode_ekf_flags


class Msg:
    def __init__(self, mtype, **kw):
        self._t = mtype
        self.__dict__.update(kw)
    def get_type(self):
        return self._t


def attitude(roll=0.1, pitch=0.2, yaw=0.3):
    return Msg("ATTITUDE", roll=roll, pitch=pitch, yaw=yaw,
               rollspeed=0.0, pitchspeed=0.0, yawspeed=0.0)

def ekf_status(flags):
    return Msg("EKF_STATUS_REPORT", flags=flags, velocity_variance=0.1,
               pos_horiz_variance=0.1, pos_vert_variance=0.1,
               compass_variance=0.1, terrain_alt_variance=0.0)

FLAGS_HEALTHY = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)
FLAGS_UNINIT  = 1 << 10

fails = []
def check(name, control, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        fails.append(name)
    print(f"[{tag}] ({control}) {name}{'  -- ' + detail if detail else ''}")


# --- 1. NEGATIVE control: fresh attitude must pass through, unflagged -------
L = Latest(dict(MAX_AGE_DEFAULT))
L.put(attitude(roll=0.5))
f = build_frame(L)
check("fresh ATTITUDE is emitted", "NEGATIVE",
      f["attitude"] is not None and abs(f["attitude"]["roll_rad"] - 0.5) < 1e-9,
      f"roll_rad={f['attitude'] and f['attitude']['roll_rad']}")
check("fresh ATTITUDE raises no attitude fault", "NEGATIVE",
      not any(x["field"] == "attitude" for x in f["faults"]))
check("attitude age is reported", "NEGATIVE",
      f["attitude_age_s"] is not None and f["attitude_age_s"] < 0.1,
      f"age={f['attitude_age_s']}s")

# --- 2. POSITIVE control: a STALE attitude must become null + fault --------
# This is the whole point: it must NOT keep emitting roll=0.5.
L2 = Latest({"ATTITUDE": 0.05})          # 50 ms limit
L2.put(attitude(roll=0.5))
time.sleep(0.12)                          # now 120 ms old -> stale
f2 = build_frame(L2)
check("stale ATTITUDE is NOT the last value", "POSITIVE",
      f2["attitude"] is None,
      "emitted null, did not repeat roll=0.5" if f2["attitude"] is None
      else f"LEAKED {f2['attitude']}")
check("stale ATTITUDE raises a 'stale' fault with an age", "POSITIVE",
      any(x["field"] == "attitude" and x["reason"] == "stale"
          and x["age_s"] is not None for x in f2["faults"]),
      str([x for x in f2["faults"] if x["field"] == "attitude"]))
check("frame is marked invalid when anything is stale", "POSITIVE",
      f2["valid"] is False)

# --- 3. POSITIVE control: never-seen vs stale must be distinguishable ------
L3 = Latest(dict(MAX_AGE_DEFAULT))
f3 = build_frame(L3)                      # nothing ever put
check("never-seen field reports 'no_data', not 'stale'", "POSITIVE",
      any(x["field"] == "attitude" and x["reason"] == "no_data"
          for x in f3["faults"]))
check("never-seen field reports age None", "POSITIVE",
      all(x["age_s"] is None for x in f3["faults"] if x["field"] == "attitude"))

# --- 4. POSITIVE control: EKF uninitialised must be a fault ----------------
# The failure this exists to catch: an EKF that has not initialised still
# publishes attitude numbers. They must not read as a solution.
L4 = Latest(dict(MAX_AGE_DEFAULT))
L4.put(attitude()); L4.put(ekf_status(FLAGS_UNINIT))
f4 = build_frame(L4)
check("EKF 'uninitialized' raises ekf_not_healthy", "POSITIVE",
      any(x.get("reason") == "ekf_not_healthy" for x in f4["faults"]))
check("EKF uninitialised => frame invalid", "POSITIVE", f4["valid"] is False)

# --- 5. NEGATIVE control: a healthy EKF must NOT be flagged ---------------
L5 = Latest(dict(MAX_AGE_DEFAULT))
L5.put(ekf_status(FLAGS_HEALTHY))
f5 = build_frame(L5)
check("healthy EKF flags raise no ekf_not_healthy", "NEGATIVE",
      not any(x.get("reason") == "ekf_not_healthy" for x in f5["faults"]))
check("decode_ekf_flags marks healthy correctly", "NEGATIVE",
      decode_ekf_flags(FLAGS_HEALTHY)["_healthy"] is True)
check("decode_ekf_flags marks uninit NOT healthy", "POSITIVE",
      decode_ekf_flags(FLAGS_UNINIT)["_healthy"] is False)

# --- 6. the over-block check: a good frame with everything present --------
L6 = Latest(dict(MAX_AGE_DEFAULT))
L6.put(attitude()); L6.put(ekf_status(FLAGS_HEALTHY))
L6.put(Msg("GLOBAL_POSITION_INT", lat=-338000000, lon=184000000, alt=50000,
           relative_alt=10000, vx=100, vy=0, vz=0, hdg=9000))
L6.put(Msg("LOCAL_POSITION_NED", x=1.0, y=2.0, z=-3.0, vx=1.0, vy=0.0, vz=0.0))
L6.put(Msg("VFR_HUD", airspeed=25.0, groundspeed=24.0, alt=50.0, climb=0.1))
f6 = build_frame(L6)
check("a fully-populated frame is valid (no over-blocking)", "NEGATIVE",
      f6["valid"] is True, f"faults={f6['faults']}")
check("hdg 65535 would decode as None", "NEGATIVE",
      f6["position"]["hdg_deg"] == 90.0, f"hdg={f6['position']['hdg_deg']}")
check("lat scaling is 1e-7 deg", "NEGATIVE",
      abs(f6["position"]["lat_deg"] - (-33.8)) < 1e-9,
      f"lat={f6['position']['lat_deg']}")

print()
if fails:
    print(f"{len(fails)} CHECK(S) FAILED: {fails}")
    sys.exit(1)
print("all checks passed")
