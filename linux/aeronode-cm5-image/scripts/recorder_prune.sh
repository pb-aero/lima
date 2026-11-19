#!/usr/bin/env bash
# recorder_prune.sh — ONE cyclic (ring-buffer) space shared by BB1's always-on recordings:
#   ArduPilot dataflash logs  /var/lib/ardupilot/logs/<N>.BIN    (~145 MB/h, one file per boot)
#   onboard-mic audio         ~node/aeronode/logs/aeromic/*.flac  (~140 MB/h, one file per minute)
# Peter 2026-11-19: "give this logging and audio logging cyclic space".
#
# Rule: while (their total > POOL_MB) or (disk free < FLOOR_MB), delete the OLDEST file across BOTH sets
# (by last-write time), so the pool always holds "the most recent N hours of everything" — logs and audio
# cover the same window. NEVER deleted: the newest file of each set and anything written in the last
# PROTECT_S seconds (= the files being recorded right now).
#
# Defaults (BB1: 29 GB eMMC, ~7.5 GB system + data): pool 14 GB ≈ 48 h of both at today's rates, floor 3 GB.
# Override with RECORDER_POOL_MB / RECORDER_FLOOR_MB / RECORDER_PROTECT_S; RECORDER_BIN_DIR / RECORDER_AUDIO_DIR
# move the sets (tests). --dry-run lists what it would delete and deletes nothing.
#
# Residual: an ArduPilot .BIN is one file per BOOT and the one being written is protected, so a single
# boot that runs for days can outgrow the pool on its own (everything else is deleted first). ArduPilot
# also prunes its own logs to keep LOG_FILE_MB_FREE (500 MB) free, but only when it opens a new log.
# Runs as root (the .BIN files are root's): recorder-prune.timer, every 10 min.
set -euo pipefail

BIN_DIR=${RECORDER_BIN_DIR:-/var/lib/ardupilot/logs}
AUDIO_DIR=${RECORDER_AUDIO_DIR:-/home/node/aeronode/logs/aeromic}
POOL_MB=${RECORDER_POOL_MB:-14000}
FLOOR_MB=${RECORDER_FLOOR_MB:-3000}
PROTECT_S=${RECORDER_PROTECT_S:-180}
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

now=$(date +%s)
list() {   # "<mtime> <bytes> <path>" for one set, oldest first, minus its newest file
  local dir=$1 pat=$2
  [ -d "$dir" ] || return 0
  find "$dir" -maxdepth 1 -type f -name "$pat" -printf '%T@ %s %p\n' | sort -n | head -n -1
}
newest_bytes() {   # bytes of the protected newest file of a set (counts toward the pool, never deleted)
  local dir=$1 pat=$2
  [ -d "$dir" ] || { echo 0; return; }
  find "$dir" -maxdepth 1 -type f -name "$pat" -printf '%T@ %s\n' | sort -n | tail -n 1 | awk '{print $2+0}'
}

mapfile -t cands < <( { list "$BIN_DIR" '[0-9]*.BIN'; list "$AUDIO_DIR" 'aeromic_*.flac'; } | sort -n )
total=$(( $(newest_bytes "$BIN_DIR" '[0-9]*.BIN') + $(newest_bytes "$AUDIO_DIR" 'aeromic_*.flac') ))
for c in "${cands[@]}"; do total=$(( total + $(echo "$c" | awk '{print $2}') )); done

free_mb() { df -Pm "$1" | awk 'NR==2{print $4}'; }
pool_mb=$(( total / 1048576 ))
free=$(free_mb "$BIN_DIR")
deleted=0; freed=0

for c in "${cands[@]}"; do
  (( pool_mb > POOL_MB || free < FLOOR_MB )) || break
  read -r mt sz path <<<"$c"
  (( now - ${mt%.*} >= PROTECT_S )) || continue          # still being written: never touch
  if (( DRY )); then
    echo "would delete $path ($(( sz / 1048576 )) MB)"
  else
    rm -f -- "$path"
  fi
  deleted=$(( deleted + 1 )); freed=$(( freed + sz ))
  total=$(( total - sz )); pool_mb=$(( total / 1048576 ))
  free=$(( free + sz / 1048576 ))
done

(( DRY )) && tag="DRY RUN, " || tag=""
echo "recorder prune: ${tag}deleted $deleted file(s), $(( freed / 1048576 )) MB; pool $pool_mb MB of $POOL_MB; disk free ~$free MB (floor $FLOOR_MB)"
