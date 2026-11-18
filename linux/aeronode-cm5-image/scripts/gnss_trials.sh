#!/usr/bin/env bash
# Interleaved GNSS cold-start trials. Run on BB1 with arduplane STOPPED and the receiver on
# factory config (NMEA @ 38400, scripts/gnss_factory.py). One reader of the port at a time:
# this script IS that reader -- watch progress by reading the log, never the port.
# usage: gnss_trials.sh LOG [timeout_s]
set -u
log=$1; to=${2:-900}
py=/home/node/aeronode/.venv/bin/python
t=/home/node/gnss_trial.py
echo "START $(date -u +%FT%TZ) uptime $(cut -d' ' -f1 /proc/uptime)" >> "$log"
#        label       rate  dyn
for trial in "factory 1000 0" "ardupilot 200 8" "rate5hz 200 0" "dyn_air4g 1000 8" \
             "factory 1000 0" "ardupilot 200 8" "dyn_air4g 1000 8" "rate5hz 200 0"; do
  set -- $trial
  echo "trial $1 start uptime $(cut -d' ' -f1 /proc/uptime)" >> "$log"
  "$py" "$t" "$1" "$2" "$3" "$to" >> "$log" 2>&1 || echo "trial $1 exit $?" >> "$log"
  sleep 5
done
# The last trial ends ON A FIX, so starting arduplane next lets EKF3 initialise straight away.
echo "DONE $(date -u +%FT%TZ)" >> "$log"
