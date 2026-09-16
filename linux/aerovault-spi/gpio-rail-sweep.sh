#!/bin/bash
# A pin with function "none" reports no level, so drive it to INPUT first, then pull it
# both ways. Floating -> follows the pull. Strapped to a rail -> refuses to follow.
lvl() { pinctrl get "$1" | grep -oE '\| *(hi|lo)' | grep -oE 'hi|lo'; }
echo "== free pins (safe to pull) =="
for p in 6 7 12 13 16 17 22 23 24 25 26 27; do
  sudo pinctrl set "$p" ip pu; sleep 0.05; a=$(lvl "$p")
  sudo pinctrl set "$p" ip pd; sleep 0.05; b=$(lvl "$p")
  sudo pinctrl set "$p" ip pn
  if   [ "$a" = hi ] && [ "$b" = lo ]; then v="floating — nothing attached"
  elif [ "$a" = hi ] && [ "$b" = hi ]; then v="*** HELD HIGH — tied to 3V3 ***"
  elif [ "$a" = lo ] && [ "$b" = lo ]; then v="*** HELD LOW — tied to GND ***"
  else v="odd ($a/$b)"; fi
  printf "  GPIO%-3s pu=%-3s pd=%-3s  %s\n" "$p" "$a" "$b" "$v"
done
echo "== pins in use: level only, not touched =="
pinctrl get 0-27 | grep -vE "GPIO(6|7|12|13|16|17|22|23|24|25|26|27) "
