#!/bin/bash
# Read this Mac's location (Location Services) and store it ROUNDED to 0.1 deg (~10 km, accuracy 20 km)
# on BB1 as the GNSS assistance starting guess. Never prints the position.
# usage: mac_pos_to_bb1.sh [user@host]
H=${1:-node@192.168.0.118}
P=$(/opt/homebrew/bin/CoreLocationCLI -format '%latitude %longitude %h_accuracy' 2>&1)
if ! printf '%s' "$P" | grep -qE '^-?[0-9]+\.[0-9]+ -?[0-9]+\.[0-9]+'; then
  echo "No location from macOS: $(printf '%s' "$P" | sed -E 's/-?[0-9]+\.[0-9]{3,}/<num>/g' | head -2)"; exit 1
fi
ACC=$(printf '%s' "$P" | awk '{printf "%.0f", $3}')
printf '%s' "$P" | awk '{printf "%.1f %.1f 20000\n", $1, $2}' | ssh -o BatchMode=yes "$H" \
  'D=~/.config/aeronode/assistnow; umask 077; cat > $D/coarse_pos.tmp && mv $D/coarse_pos.tmp $D/coarse_pos && echo "BB1: rough position saved ($(wc -c < $D/coarse_pos) bytes, mode $(stat -c %a $D/coarse_pos))"'
unset P
echo "Mac location accuracy was ${ACC} m; stored rounded to 0.1 deg. You can close this tab."
