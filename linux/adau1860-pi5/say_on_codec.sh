#!/usr/bin/env bash
# Speak text through the ADAU1860's headphone output. Run ON THE MAC.
#
#   ./say_on_codec.sh "hello there"
#   ./say_on_codec.sh -v Moira -r 190 "a different voice, faster"
#   echo "long text" | ./say_on_codec.sh -
#
# The TTS is macOS `say` (no engine on the Pi); the Mac renders 48 kHz 32-bit mono,
# say_to_slots.py packs it into slots 0 and 2, scp carries it, aplay clocks it out.
#
# PRECONDITION: the codec must already be brought up in the CURRENT boot --
# STATUS2=0xF1, SAI_MODE=STEREO, DAC unmuted, HPLDO on. Run bringup.sh on the Pi
# from a COLD board first. This script deliberately writes no codec registers:
# a second framing attempt in a poisoned boot fails no matter how correct it is.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PI="${PI:-node@192.168.0.99}"; DEV="${DEV:-hw:0,0}"; VOICE="${VOICE:-Daniel}"
RATE=""; PEAK="${PEAK:--6}"

while getopts "v:r:p:" o; do case $o in
  v) VOICE=$OPTARG;; r) RATE="-r $OPTARG";; p) PEAK=$OPTARG;;
esac; done
shift $((OPTIND-1))
TEXT="${1:?usage: say_on_codec.sh [-v voice] [-r wpm] [-p peak_dbfs] \"text\" (or - for stdin)}"
[ "$TEXT" = "-" ] && TEXT="$(cat)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
say -v "$VOICE" $RATE --data-format=LEI32@48000 -o "$TMP/s.wav" "$TEXT"
python3 "$HERE/say_to_slots.py" --peak-dbfs "$PEAK" "$TMP/s.wav" "$TMP/s.raw"

scp -q "$TMP/s.raw" "$PI:/tmp/say.raw"
ssh "$PI" "S=\$(date +%s%N)
  aplay -q -D $DEV -f S32_LE -c 4 -r 48000 -t raw /tmp/say.raw
  echo \"aplay exit=\$? elapsed=\$(( (\$(date +%s%N)-S)/1000000 )) ms\"
  rm -f /tmp/say.raw"
