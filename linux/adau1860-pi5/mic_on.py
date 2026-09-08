#!/usr/bin/env python3
"""Bring up the ADAU1860 analog mic capture path: P11 -> ADC2 -> SPT0 -> I2S -> Pi.

Register addresses and bit positions are from ADI's own bitfield header
(adi_lark_bf_lark_yoda.h, Lark SDK) -- the authoritative map. The 30-page
abridged datasheet has none, which is what cost four hours in September.

WHAT P11 IS: analog input 2, a 3.5 mm TRS jack. TIP -> AINP2, RING -> AINN2,
both through 0R + 22uF. THERE IS NO MIC BIAS ON THE BOARD -- see MIC_INPUT_P11.md.
An unpowered capsule reads as silence here with every register perfect.

TWO TRAPS THIS SCRIPT EXISTS TO AVOID
  1. ADC2_MUTE (0x4000C027 bit 2) is the exact shape of the DAC0_MUTE bit that
     silenced the output path for two sessions while everything read back fine.
     It is cleared explicitly and read back.
  2. PGA2_EN lives in PLL_PGA_PWR (0x4000C005), which is one of the three
     COLD-ONLY registers -- read-only once the power domains are up, and
     SOFT_FULL_RESET does not clear it. If the part is not cold, the PGA cannot
     be enabled and this script says so instead of pretending.
"""
import argparse, sys
from smbus2 import SMBus, i2c_msg

PWR_ADC_DAC = 0x4000C004   # [2] ADC2_EN            [4] PB0_EN
PLL_PGA_PWR = 0x4000C005   # [6] PGA2_EN            COLD-ONLY
SPT_PWR     = 0x4000C007   # [0] SPT0_IN_EN  [1] SPT0_OUT_EN
ADC_FREQ    = 0x4000C01C   # [4] ADC_FREQ
ADC2_CTRL   = 0x4000C020   # [4:6] ADC2_FS          [7] ADC2_DEC_ORDER
ADC2_HPF    = 0x4000C023   # [4:5] ADC2_HPF_EN
ADC_MUTES   = 0x4000C027   # [2] ADC2_MUTE
ADC2_VOL    = 0x4000C02A   # [0:7]
PGA2_GAIN   = 0x4000C034   # [0:10]
SPT0_ROUTE0 = 0x4000C0E3   # [0:5] source select
STATUS2     = 0x4000C402

ROUTE_ADC2 = 38            # LARK numbering. LARK_LITE would be 2. See STT_PATH.md

ap = argparse.ArgumentParser()
ap.add_argument("--bus", type=int, default=1)
ap.add_argument("--addr", type=lambda s: int(s, 0), default=0x67)
ap.add_argument("--route", type=int, default=ROUTE_ADC2, help="SPT0_ROUTE0 source (sweep if silent)")
ap.add_argument("--pga-gain", type=int, default=0, help="PGA2_GAIN code, 0..2047 (0 dB..24 dB)")
ap.add_argument("--apply", action="store_true", help="write; otherwise dry run")
a = ap.parse_args()

def rd(b, r):
    w = i2c_msg.write(a.addr, r.to_bytes(4, "big")); q = i2c_msg.read(a.addr, 1)
    b.i2c_rdwr(w, q); return list(q)[0]

def wr(b, r, v):
    b.i2c_rdwr(i2c_msg.write(a.addr, r.to_bytes(4, "big") + bytes([v])))

def setbits(b, reg, mask, val, name):
    cur = rd(b, reg); new = (cur & ~mask) | (val & mask)
    if not a.apply:
        print(f"  DRY  {name:14s} 0x{reg:08X}: 0x{cur:02X} -> 0x{new:02X}"); return
    wr(b, reg, new); back = rd(b, reg)
    flag = "OK" if back == new else "MISMATCH"
    print(f"  {flag:8s} {name:14s} 0x{reg:08X}: 0x{cur:02X} -> 0x{new:02X}, read 0x{back:02X}")
    return back == new

with SMBus(a.bus) as b:
    s2 = rd(b, STATUS2)
    print(f"STATUS2=0x{s2:02X}  POWER_UP={(s2>>7)&1} SPT0_LOCK={(s2>>4)&1} PLL_LOCK={s2&1}")
    if not ((s2 >> 7) & 1 and s2 & 1):
        sys.exit("Clocks are not up. Run bringup.sh from a COLD board first.")

    pga_before = rd(b, PLL_PGA_PWR)
    print(f"PLL_PGA_PWR=0x{pga_before:02X}  PGA2_EN={(pga_before>>6)&1}  (COLD-ONLY register)")

    print("\nanalog front end")
    setbits(b, PLL_PGA_PWR, 1 << 6, 1 << 6, "PGA2_EN")
    setbits(b, PWR_ADC_DAC, 1 << 2, 1 << 2, "ADC2_EN")
    setbits(b, PGA2_GAIN,   0xFF,   a.pga_gain & 0xFF, "PGA2_GAIN")

    print("\ndigital")
    setbits(b, ADC2_CTRL, 0b111 << 4, 0b010 << 4, "ADC2_FS=48k")
    setbits(b, ADC2_HPF,  0b11  << 4, 0b01  << 4, "ADC2_HPF_EN")
    setbits(b, ADC_MUTES, 1 << 2, 0, "ADC2_MUTE=0")
    setbits(b, ADC2_VOL,  0xFF, 0x40, "ADC2_VOL=0dB")

    print("\ntransport")
    setbits(b, SPT0_ROUTE0, 0x3F, a.route & 0x3F, f"SPT0_ROUTE0={a.route}")
    setbits(b, SPT_PWR, 1 << 1, 1 << 1, "SPT0_OUT_EN")

    if a.apply:
        pga_after = rd(b, PLL_PGA_PWR)
        print()
        if not ((pga_after >> 6) & 1):
            print("PGA2_EN DID NOT LATCH. PLL_PGA_PWR is read-only while the power domains "
                  "are up.\n  -> POWER CYCLE the EVAL board, then bringup.sh, then this script.\n"
                  "  Capture may still work at 0 dB analog gain, but a low-output mic will "
                  "look identical to a dead route.")
        else:
            print("mic path up. Now PROVE it: arecord while TAPPING the mic and watch the "
                  "noise floor move.\n  A dead route, an unbiased mic and a quiet room are "
                  "indistinguishable.")
