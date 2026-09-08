#!/usr/bin/env bash
# Neural text-to-speech out of the ADAU1860's headphone jack. Runs ENTIRELY ON THE PI.
#
#   ./piper_say.sh "hello there"
#   ./piper_say.sh -v en_US-lessac-medium "a different voice"
#   ./piper_say.sh -s 1.15 "slower"            # length-scale: >1 slower, <1 faster
#   echo "long text" | ./piper_say.sh -
#
# PIPELINE, fully streaming -- no temp files, speech starts before synthesis ends:
#
#   piper --output-raw           mono S16_LE at the MODEL's rate (22.05 kHz for medium)
#     | ffmpeg -af aresample=soxr  -> mono S32_LE at 48 kHz, the codec's only rate
#     | pack_slots.py            -> 4-slot frames, audio in slots 0 and 2
#     | aplay -c 4               -> I2S -> ADAU1860 DAC -> P30
#
# The model rate is READ FROM THE VOICE CONFIG, never assumed: medium voices are
# 22050 Hz but low/high tiers differ, and feeding ffmpeg the wrong input rate is a
# pitch shift that sounds like a working system.
#
# PRECONDITION: the codec must already be up in the CURRENT boot -- STATUS2=0xF1,
# SAI_MODE=STEREO, DAC unmuted, HPLDO on. Run bringup.sh from a COLD board first.
# This script writes NO codec registers: one framing attempt per boot is the rule,
# and a second attempt fails in a poisoned boot however correct it is.
set -euo pipefail
VENV="${VENV:-$HOME/piper-venv}"
VOICES="${VOICES:-$HOME/piper-voices}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VOICE="${VOICE:-en_GB-alba-medium}"; DEV="${DEV:-hw:0,0}"
GAIN="${GAIN:--6}"; SCALE=""; SILENCE="0.3"

while getopts "v:s:g:q:" o; do case $o in
  v) VOICE=$OPTARG;; s) SCALE="--length-scale $OPTARG";;
  g) GAIN=$OPTARG;;  q) SILENCE=$OPTARG;;
esac; done
shift $((OPTIND-1))
TEXT="${1:?usage: piper_say.sh [-v voice] [-s length-scale] [-g gain_db] \"text\" (- for stdin)}"
[ "$TEXT" = "-" ] && TEXT="$(cat)"

CFG="$VOICES/$VOICE.onnx.json"
[ -f "$CFG" ] || { echo "no such voice: $CFG" >&2
                   echo "have: $(ls "$VOICES" 2>/dev/null | grep -o '.*\.onnx$' | sed 's/\.onnx//' | tr '\n' ' ')" >&2
                   echo "get one: $VENV/bin/python -m piper.download_voices --data-dir $VOICES <name>" >&2
                   exit 1; }
SR=$("$VENV/bin/python" -c "import json,sys;print(json.load(open(sys.argv[1]))['audio']['sample_rate'])" "$CFG")

"$VENV/bin/python" -m piper -m "$VOICES/$VOICE.onnx" --output-raw \
      --sentence-silence "$SILENCE" $SCALE -- "$TEXT" \
  | ffmpeg -hide_banner -loglevel error \
      -f s16le -ar "$SR" -ac 1 -i - \
      -af aresample=resampler=soxr:precision=28 -ar 48000 -ac 1 -f s32le - \
  | "$VENV/bin/python" "$HERE/pack_slots.py" --gain-db "$GAIN" \
  | aplay -q -D "$DEV" -f S32_LE -c 4 -r 48000 -t raw -
