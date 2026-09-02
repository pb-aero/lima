#!/usr/bin/env bash
# Run ON THE PI. Proves whether samples reach the ADAU1860.
#
#   stage 1:  sudo ./run_on_pi.sh install     # build + install overlay, edit config.txt, then REBOOT
#   stage 2:  sudo ./run_on_pi.sh probe       # I2C comms + ID check. Changes nothing.
#   stage 3:  sudo ./run_on_pi.sh test        # configure the codec and push a tone
#
# Stages 1 and 2 are safe to run blind. Stage 3 writes codec registers; they are
# volatile and a power cycle clears them.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ADDR="${ADDR:-0x64}"
BUS="${BUS:-1}"
FS="${FS:-48000}"
SLOTS="${SLOTS:-4}"
BOOTDIR=/boot/firmware
[ -d "$BOOTDIR" ] || BOOTDIR=/boot

say() { printf '\n=== %s\n' "$*"; }

case "${1:-}" in
install)
  say "checking prerequisites"
  command -v dtc >/dev/null || { echo "installing device-tree-compiler"; apt-get install -y device-tree-compiler; }
  python3 -c 'import smbus2' 2>/dev/null || { echo "installing smbus2"; pip3 install --break-system-packages smbus2; }

  say "building the overlay"
  dtc -@ -I dts -O dtb -o "$HERE/adau1860-pi5-tx.dtbo" "$HERE/adau1860-pi5-tx-overlay.dts"
  install -m644 "$HERE/adau1860-pi5-tx.dtbo" "$BOOTDIR/overlays/"
  echo "installed -> $BOOTDIR/overlays/adau1860-pi5-tx.dtbo"

  say "config.txt"
  cfg="$BOOTDIR/config.txt"
  cp -n "$cfg" "$cfg.bak-adau1860" && echo "backed up to $cfg.bak-adau1860"
  grep -q '^dtparam=i2c_arm=on' "$cfg" || echo 'dtparam=i2c_arm=on' >> "$cfg"
  grep -q '^dtoverlay=adau1860-pi5-tx' "$cfg" || echo 'dtoverlay=adau1860-pi5-tx' >> "$cfg"
  echo "--- anything else claiming GPIO18-21 or the audio block? ---"
  grep -nE '^dtparam=audio|^dtoverlay=.*(i2s|audio|dac|hifiberry|iqaudio|allo)' "$cfg" || echo "(nothing conflicting)"
  say "REBOOT NOW, then run: sudo $0 probe"
  ;;

probe)
  say "I2C bus $BUS"
  command -v i2cdetect >/dev/null || apt-get install -y i2c-tools
  i2cdetect -y "$BUS" || true
  echo "(expect a device at 0x64-0x67; ADDR0/ADDR1 pins pick which)"
  say "ADAU1860 identity via 32-bit subaddress"
  python3 "$HERE/adau1860_init.py" --bus "$BUS" --addr "$ADDR" --probe
  say "sound card"
  aplay -l || true
  ;;

test)
  say "planned register writes (dry run)"
  python3 "$HERE/adau1860_init.py" --bus "$BUS" --addr "$ADDR" --fs "$FS" --slots "$SLOTS" --dac-test
  say "applying"
  python3 "$HERE/adau1860_init.py" --bus "$BUS" --addr "$ADDR" --fs "$FS" --slots "$SLOTS" --dac-test --apply
  card=$(aplay -l | sed -n 's/^card \([0-9]*\): \([^ ]*\) .*/\2/p' | grep -i adau | head -1 || true)
  [ -n "$card" ] || { echo "no adau card in aplay -l -- overlay not loaded? run 'install' and reboot"; exit 1; }
  say "sending 10 s of 1 kHz on slot 0 to hw:$card,0"
  echo "Listen on / scope the analog output. A tone means the samples arrived."
  python3 "$HERE/send_test_pattern.py" --seconds 10 --rate "$FS" \
    | aplay -D "hw:$card,0" -f S32_LE -c "$SLOTS" -r "$FS" -t raw
  ;;

*)
  sed -n '2,12p' "$0"; exit 1 ;;
esac
