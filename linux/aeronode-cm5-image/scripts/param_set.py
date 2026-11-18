#!/usr/bin/env python3
"""Set (or just read) ArduPilot parameters and read them back.

usage: param_set.py <conn> NAME[=VALUE] [NAME[=VALUE] ...]
e.g.   param_set.py udpin:127.0.0.1:14552 SCHED_LOOP_RATE=400
"""
import sys
import time

from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1], source_system=253)
if m.wait_heartbeat(timeout=20) is None:
    sys.exit("no heartbeat")
for arg in sys.argv[2:]:
    name, _, val = arg.partition("=")
    if val:
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(val),
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    else:
        m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    t0 = time.time()
    got = None
    while time.time() - t0 < 5:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        if msg and msg.param_id == name:
            got = msg.param_value
            break
    print(f"{name} = {got:g}" if got is not None else f"{name}: NO READBACK")
