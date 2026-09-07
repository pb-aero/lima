#!/usr/bin/env bash
# One-command cold bring-up of the ADAU1860 on the Pi. Run ON the Pi, unprivileged.
#
#   ./bringup.sh              # configure, verify, report
#   ./bringup.sh play FILE    # configure then play a 4ch S32_LE 48 kHz raw file
#
# WHY THIS EXISTS: the codec's configuration is VOLATILE and it has its own
# supply. Any power cycle of the board -- including ones you did not intend --
# drops every register back to reset: DAC muted, headphone LDO off, no clock
# generation. Everything still reads back cleanly over I2C, `aplay` still opens
# the device, and you get EIO and silence. Measured twice on 2026-09-07.
#
# ORDER MATTERS AND IS NOT NEGOTIABLE:
#   1. The part must be COLD. CLK_CTRL1, PLL_PGA_PWR and CHIP_PWR go read-only
#      once the power domains are up and SOFT_FULL_RESET does not clear them --
#      only a power cycle does.
#   2. SAI_MODE must be set to STEREO BEFORE the first PCM open of the boot.
#      RP1 will not lock to the ADAU1860's narrow TDM frame sync, and a failed
#      attempt leaves the DMA channel stuck for the whole boot, so even a
#      correct second attempt then fails. One framing attempt per boot.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ADDR="${ADDR:-0x67}"; BUS="${BUS:-1}"; FS="${FS:-48000}"; SLOTS="${SLOTS:-4}"; DEV="${DEV:-hw:0,0}"

python3 "$HERE/adau1860_init.py" --bus "$BUS" --addr "$ADDR" --fs "$FS" --slots "$SLOTS" \
        --apply --dac-test | grep -E "OK|MISMATCH|STATUS2|IDs" || true

python3 - "$ADDR" "$BUS" <<'PY'
import sys
from smbus2 import SMBus, i2c_msg
A = int(sys.argv[1], 0); BUS = int(sys.argv[2])
SPT0_CTRL1, STATUS2 = 0x4000C0E0, 0x4000C402
DAC_CTRL2, HPLDO, PWR = 0x4000C051, 0x4000C066, 0x4000C004
def rd(b, r):
    w = i2c_msg.write(A, r.to_bytes(4, "big")); q = i2c_msg.read(A, 1)
    b.i2c_rdwr(w, q); return list(q)[0]
def wr(b, r, v): b.i2c_rdwr(i2c_msg.write(A, r.to_bytes(4, "big") + bytes([v])))
with SMBus(BUS) as b:
    wr(b, SPT0_CTRL1, rd(b, SPT0_CTRL1) & ~1)        # SAI_MODE -> STEREO
    s2 = rd(b, STATUS2)
    ok = ((s2 >> 7) & 1) and ((s2 >> 4) & 1) and (s2 & 1) \
         and not ((rd(b, DAC_CTRL2) >> 6) & 1) and (rd(b, HPLDO) & 1) and ((rd(b, PWR) >> 4) & 1)
    print(f"SAI_MODE=STEREO  STATUS2=0x{s2:02X} "
          f"(POWER_UP={(s2>>7)&1} SPT0_LOCK={(s2>>4)&1} PLL_LOCK={s2&1})  "
          f"MUTE={(rd(b,DAC_CTRL2)>>6)&1} HPLDO_EN={rd(b,HPLDO)&1} PB0_EN={(rd(b,PWR)>>4)&1}")
    if not ok:
        sys.exit("NOT READY. If STATUS2 is 0x00 the part is cold and this should have "
                 "worked; if the clock registers MISMATCHed above, the part was already "
                 "powered up -- POWER CYCLE the board and run this again.")
    print("READY -- slot 0 reaches DAC channel 0. Slots 1 and 3 are discarded (STEREO framing).")
PY

if [ "${1:-}" = "play" ] && [ -n "${2:-}" ]; then
  echo "playing $2"
  aplay -D "$DEV" -f S32_LE -c "$SLOTS" -r "$FS" -t raw "$2"
fi
