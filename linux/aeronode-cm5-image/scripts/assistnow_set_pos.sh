#!/bin/bash
# Store a ROUGH position for BB1's GNSS assistance, hidden. Rounded to 0.1 deg (~10 km), accuracy 20 km.
# Never echoed. assistnow_inject.py sends it as MGA-INI-POS_LLH; --save-pos later replaces it from a real fix.
set -u
D=/home/node/.config/aeronode/assistnow
mkdir -p "$D" && chmod 700 "$D"
read -rsp "Latitude, decimal degrees (south is negative, e.g. -33.9), hidden: " LAT; echo
read -rsp "Longitude, decimal degrees (east is positive, e.g. 18.4), hidden: " LON; echo
OUT=$(awk -v a="$LAT" -v o="$LON" 'BEGIN{
  if (a !~ /^-?[0-9]+(\.[0-9]+)?$/ || o !~ /^-?[0-9]+(\.[0-9]+)?$/ || a+0<-90 || a+0>90 || o+0<-180 || o+0>180) exit 1;
  printf "%.1f %.1f 20000\n", a, o }') || { echo "Those don't look like decimal degrees. Nothing saved; run again."; exit 1; }
unset LAT LON
umask 077; printf '%s' "$OUT" > "$D/coarse_pos"; unset OUT
echo "Saved, rounded to 0.1 deg, accuracy 20 km ($D/coarse_pos, mode $(stat -c %a "$D/coarse_pos")). You can close this tab."
