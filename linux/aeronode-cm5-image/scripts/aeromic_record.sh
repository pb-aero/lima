#!/usr/bin/env bash
# aeromic_record.sh — ALWAYS-ON recorder for the Blackbox board's onboard I2S mic (ADAU7002 overlay,
# ALSA card "aeromic"). Peter 2026-11-19: "make logging always on as well as mic record".
#
# Capture: arecord (its 0.5 s ALSA buffer; ffmpeg's own alsa input xran 7x in 14 s on BB1) ->
# ffmpeg keeps the LEFT channel (the mic; right is a constant 0x1) -> 24-bit mono FLAC, one file per
# AEROMIC_SEGMENT_S seconds (default 60, so a power cut loses at most ~1 min), named by UTC start time.
# Measured on BB1: 16.0 s captured -> 15.98 s decoded (no loss), ~145 MB/h in a quiet room.
# Known quirk: ffmpeg's segment muxer leaves the FLAC header's total-samples blank (duration "N/A" in
# ffprobe); the audio decodes fully.
#
# The disk cap is aeromic_prune.sh (run before each start and by aeromic-prune.timer).
# Judge this mic above ~200 Hz: sub-200 Hz drift dominates (MEMORY.md, 2026-11-17).
set -euo pipefail

DIR=${AEROMIC_DIR:-/home/node/aeronode/logs/aeromic}
SEG=${AEROMIC_SEGMENT_S:-60}
DEV=${AEROMIC_DEVICE:-hw:CARD=aeromic,DEV=0}

grep -q '\baeromic\b' /proc/asound/cards || {
  echo "REFUSING TO START: no ALSA card named aeromic (dtoverlay=adau7002-simple,card-name=aeromic in config.txt?)"
  exit 1
}
mkdir -p "$DIR"
echo "aeromic: recording $DEV -> $DIR (${SEG} s FLAC files)"

arecord -q -D "$DEV" -f S32_LE -c 2 -r 48000 -t raw --buffer-time=500000 \
  | TZ=UTC ffmpeg -hide_banner -nostdin -loglevel warning \
      -f s32le -ar 48000 -ac 2 -i pipe:0 \
      -af "pan=mono|c0=c0" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 \
      -f segment -segment_time "$SEG" -reset_timestamps 1 -strftime 1 \
      "$DIR/aeromic_%Y%m%dT%H%M%SZ.flac"
