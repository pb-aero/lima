#!/usr/bin/env bash
# ap_run.sh <label> <binary> [secs] [extra arduplane args...]
# Start the MAVLink probe first, then ArduPlane as root for <secs>; print a short verdict.
set -u
label=$1; bin=$2; secs=${3:-40}; shift 3 || shift $#
out=~/ap-run/$label
mkdir -p ~/ap-run
pkill -x arduplane 2>/dev/null; sudo pkill -x arduplane 2>/dev/null; sleep 1
(timeout $((secs + 15)) ~/aeronode/.venv/bin/python -u ~/mav_probe.py udpin:127.0.0.1:14551 $((secs - 8)) "$@" \
    > "$out.probe" 2>&1 &)
sleep 1
cd ~ && sudo setsid nohup timeout "$secs" "$bin" --serial0 udp:127.0.0.1:14551 ${AP_EXTRA:-} -l /home/node/ap-run/logs \
    </dev/null > "$out.stdout" 2>&1 &
sleep $((secs + 3))
while pgrep -x arduplane >/dev/null; do sleep 1; done
echo "=== $label ($bin)"
echo "  stdout: $(tr '\n' ' ' < "$out.stdout" | cut -c1-120)"
echo "  config errors: $(grep -c 'Config Error' "$out.probe")"
grep -E 'STATUSTEXT|PARAM ' "$out.probe" | grep -v 'Config Error' | sort -u -k3 | head -20
grep -E '^  (gyro|accel|mag|baro|gps|ahrs) ' "$out.probe"
grep -E '^(HEARTBEAT|ATTITUDE|RAW_IMU|SCALED_PRESSURE|EKF_STATUS_REPORT|NO HEARTBEAT)' "$out.probe"
