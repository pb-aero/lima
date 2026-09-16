#!/usr/bin/env bash
# setup-inputs.sh - ADAU1372: AIN0 = single-ended mic (PGA + MICBIAS0),
#                              AIN1/2/3 = single-ended LINE (PGA bypassed) for accel X/Y/Z.
#
# *** UNTESTED DRAFT, 2026-09-16. Control names come from reading
#     sound/soc/codecs/adau1372.c, not from a running card. Run `amixer -c ... contents`
#     first and fix any name that differs before trusting this script. ***
set -euo pipefail

CARD="${1:-adau1372}"
MIC_GAIN_DB="${2:-0}"        # PGA gain for AIN0, -12.00 .. +35.25 dB in 0.75 dB steps

s() { amixer -c "$CARD" -q cset name="$1" "$2"; }

# --- input mode -------------------------------------------------------------
# PGA on for the mic only. For a single-ended LINE input the datasheet wants
# PGA_ENx = 0 (reset state) - so AIN1/2/3 are explicitly switched off here.
s 'PGA 0 Capture Switch' on
s 'PGA 1 Capture Switch' off
s 'PGA 2 Capture Switch' off
s 'PGA 3 Capture Switch' off

amixer -c "$CARD" -q sset 'PGA 0 Capture Volume' "${MIC_GAIN_DB}dB" || \
  echo "note: set 'PGA 0 Capture Volume' by index if dB addressing is refused"
s 'PGA 0 Boost Capture Volume' 0     # 10 dB boost bit, off

# --- ADCs -------------------------------------------------------------------
for n in 0 1 2 3; do s "ADC $n Capture Switch" on; done

# High-pass is per PAIR: ADC0+1 (mic + accel X) and ADC2+3 (accel Y + Z).
# Options: Off / 1 Hz / 4 Hz / 8 Hz.
s 'ADC 0+1 High-Pass-Filter' '1 Hz'
s 'ADC 2+3 High-Pass-Filter' '1 Hz'

# --- routing: ADC -> decimator -> output ASRC -> TDM slot -------------------
s 'Decimator 0+1 Capture Mux' 'ADC'
s 'Decimator 2+3 Capture Mux' 'ADC'
for n in 0 1 2 3; do
  s "Output ASRC$n Mux" "Decimator$n"
  s "Serial Output $n Capture Mux" "Output ASRC$n"
done

echo "--- read back ---"
amixer -c "$CARD" contents | grep -A2 -E "PGA [0-3] Capture Switch|High-Pass|Capture Mux" || true
echo
echo "Now prove the slot map: inject a tone into ONE pin and confirm it appears in that"
echo "channel and NOWHERE else.  arecord -c 4 -f S32_LE -r 48000 -d 2 -v test.wav"
