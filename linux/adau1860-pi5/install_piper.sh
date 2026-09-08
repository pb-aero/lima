#!/usr/bin/env bash
# Install Piper neural TTS on the Pi. Run ON THE PI. Idempotent.
#
# WHY A VENV, not --break-system-packages: Debian 13 marks its Python
# externally-managed (PEP 668) and this machine's system Python also carries the
# ArduPilot toolchain. piper-tts pulls onnxruntime, numpy and protobuf; letting
# those overwrite distro packages on a box whose flight-software build depends on
# them is a trade with no upside. The venv costs ~200 MB and is disposable.
set -euo pipefail
VENV="${VENV:-$HOME/piper-venv}"
VOICES="${VOICES:-$HOME/piper-voices}"
DEFAULT_VOICES="${DEFAULT_VOICES:-en_GB-alba-medium en_US-lessac-medium en_GB-northern_english_male-medium}"

# ffmpeg does the 22.05k -> 48k resample; the codec runs at 48 kHz only.
command -v ffmpeg >/dev/null || { echo "installing ffmpeg"; sudo apt-get install -y ffmpeg; }

[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" -q install --upgrade pip
"$VENV/bin/pip" -q install piper-tts
"$VENV/bin/pip" show piper-tts | sed -n '1,2p'

mkdir -p "$VOICES"
for v in $DEFAULT_VOICES; do
  [ -f "$VOICES/$v.onnx.json" ] && { echo "have $v"; continue; }
  echo "downloading $v (~63 MB medium model; the .json lands LAST, so its"
  echo "  absence is the honest completion check -- a 12 MB .onnx is a part file)"
  "$VENV/bin/python" -m piper.download_voices --data-dir "$VOICES" "$v"
done

echo
echo "voices ready:"; ls "$VOICES"/*.onnx.json 2>/dev/null | xargs -n1 basename | sed 's/\.onnx\.json//;s/^/  /'
echo
echo "browse more:  $VENV/bin/python -m piper.download_voices        # lists all"
echo "speak:        ./piper_say.sh \"hello\"                          # needs bringup.sh done this boot"
