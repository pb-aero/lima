#!/usr/bin/env python3
"""led_test.py - flash the Blackbox AeroNode board's RGB LED (LED3, IN-S126TBSRGB) through the LP5815 (U8, I2C-1 0x2D).

out0 = red, out1 = green, out2 = blue (schematic HW 0.0.2 rev 1, sheet 6). Register sequence from TI LP5815 datasheet
SNVSCP2B section 8.2.3.2: 00h CHIP_EN (03h = enable + instant-blink off), 01h MAX_CURRENT (0 = 25.5 mA range),
14h-16h dot current, 02h output enable, 04h manual mode, 0Fh UPDATE_CMD = 55h, 18h-1Ah manual PWM.
Low current on purpose: DC 50h = ~8 mA per colour. Leaves the chip in standby (CHIP_EN = 0) however it exits.
Run on BB1: python3 led_test.py
"""
import time
import smbus2

b = smbus2.SMBus(1)
A = 0x2D
w = lambda r, v: b.write_byte_data(A, r, v)
rd = lambda r: b.read_byte_data(A, r)


def rgb(r, g, bl):
    w(0x18, r); w(0x19, g); w(0x1A, bl)


try:
    w(0x00, 0x03)
    time.sleep(0.002)
    w(0x01, 0x00)
    for reg in (0x14, 0x15, 0x16):
        w(reg, 0x50)
    w(0x02, 0x07)
    w(0x04, 0x00)
    w(0x0F, 0x55)
    for cyc in range(3):
        for name, c in (("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255))):
            rgb(*c); print(f"cycle {cyc + 1}: {name}", flush=True); time.sleep(0.6)
        rgb(0, 0, 0); time.sleep(0.2)
    for k in range(3):
        rgb(255, 255, 255); print(f"white blink {k + 1}", flush=True); time.sleep(0.4)
        rgb(0, 0, 0); time.sleep(0.4)
    print("FLAG 40h:", hex(rd(0x40)), "(bit0 = POR, normal after power-up; bit1 = TSD)")
finally:
    rgb(0, 0, 0); w(0x02, 0x00); w(0x0F, 0x55); w(0x00, 0x00)
    print("off, chip in standby")
