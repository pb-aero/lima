#!/usr/bin/env bash
# aeromic_prune.sh — keep the always-on AeroMic recordings under a size cap AND the disk above a
# free-space floor, deleting the OLDEST files first. Never deletes the newest file (the one being
# written). Run by aeromic-record.service (ExecStartPre) and aeromic-prune.timer (every 10 min).
#
# Budget (BB1, 29 GB eMMC, ~20 GB free on 2026-11-19): audio capped at 8 GB (~25-55 h depending on how
# loud it is); ArduPilot's own LOG_FILE_MB_FREE (500 MB) prunes its .BIN logs at each new log.
set -euo pipefail

DIR=${AEROMIC_DIR:-/home/node/aeronode/logs/aeromic}
CAP_MB=${AEROMIC_CAP_MB:-8000}
FLOOR_MB=${AEROMIC_FREE_FLOOR_MB:-2000}

[ -d "$DIR" ] || exit 0
cd "$DIR"
deleted=0
while :; do
  mapfile -t files < <(ls -1 aeromic_*.flac 2>/dev/null | sort)
  (( ${#files[@]} > 1 )) || break
  used=$(du -sm . | cut -f1)
  free=$(df -Pm . | awk 'NR==2{print $4}')
  (( used > CAP_MB || free < FLOOR_MB )) || break
  rm -f -- "${files[0]}"
  deleted=$((deleted + 1))
done
echo "aeromic prune: deleted $deleted; $(ls -1 aeromic_*.flac 2>/dev/null | wc -l) files, $(du -sm . | cut -f1) MB (cap $CAP_MB); disk free $(df -Pm . | awk 'NR==2{print $4}') MB (floor $FLOOR_MB)"
