# RP1 I2S has four data lanes — 8 channels without TDM

**Date:** 2026-09-04 · **Agent:** LIMA · bench `scopenode`, Pi 5 Rev 1.1, kernel 6.12.47.
All `[measured]` on hardware.

## The finding

`i2s1` is not a single data line. `[measured]` from `pinctrl funcs`:

| Lane | SDI | SDO |
|---|---|---|
| 0 | GPIO20 | GPIO21 |
| 1 | GPIO22 | GPIO23 |
| 2 | GPIO24 | GPIO25 |
| 3 | GPIO26 | GPIO27 |

plus `I2S1_SCLK` on GPIO18 and `I2S1_WS` on GPIO19. (`i2s0` offers the same ten pins; `i2s2` is
scattered across GPIO28-33 and 42-47 but has no DMA, so it remains unusable.)

**This explains the driver's 2/4/6/8 channel restriction, which had looked arbitrary.** It is
**1/2/3/4 stereo lanes** — not a TDM slot count. Each lane carries its own stereo pair on its own
wire.

## Why it matters

Earlier work established that **the RP1 will not lock to a narrow TDM frame sync** — a hard blocker
for carrying more than two channels. Multi-lane sidesteps it completely:

> **8 channels, ordinary 50%-duty frame sync, and the bit clock stays at the stereo rate.**

At 48 kHz the bit clock is **3.072 MHz for 8 channels**, because each lane carries 2×32 bits — not
the 12.288 MHz an 8-slot TDM frame would need. Fewer edges, easier signal integrity, and no
dependence on the frame-sync behaviour that does not work.

## Measured

Channel sweep, 2 s of audio per run, `hw:i2s1x4,0`, codec as clock master at 48 kHz:

| Channels | Lanes | `aplay` | elapsed (expect 2.00 s) |
|---|---|---|---|
| 2 | 1 | exit 0 | 2.13 s |
| 4 | 2 | exit 0 | 2.13 s |
| 6 | 3 | exit 0 | 2.05 s |
| 8 | 4 | exit 0 | 2.05 s |

Capture, and both directions at once:

| Test | Result |
|---|---|
| 2ch capture | exit 0, 768,000 bytes exact |
| 8ch capture | exit 0, 3,072,000 bytes exact |
| **8ch TX + 8ch RX simultaneously** | **both exit 0, 4,608,000 bytes exact** |

That is 16 channels of concurrent traffic on one block at a 3.072 MHz bit clock.

## The lanes genuinely carry data — controlled test

Streams running is not proof the pins are used. Sampling the four SDO pins directly:

| | SDO0 (21) | SDO1 (23) | SDO2 (25) | SDO3 (27) |
|---|---|---|---|---|
| idle | static | static | static | static |
| **2-channel play** | **toggling** | static | static | static |
| **8-channel play** | **toggling** | **toggling** | **toggling** | **toggling** |

The 2-channel row is the negative control: lanes 1-3 stay dead when unused and come alive only at 8
channels. Without it, "all four toggle" would prove nothing.

## How to use it

`i2s1-4lane-overlay.dts` here. The essential part is a pinctrl group claiming all ten pins, because
the stock `rp1_i2s1_18_21` group claims only four:

```dts
fragment@0 {
    target = <&rp1_gpio>;
    __overlay__ {
        i2s1_all: i2s1_all {
            function = "i2s1";
            pins = "gpio18","gpio19","gpio20","gpio21","gpio22",
                   "gpio23","gpio24","gpio25","gpio26","gpio27";
            bias-disable;
        };
    };
};
```
then point the controller's `pinctrl-0` at it. Needs `dummy_duplex.ko` for a full-duplex link.

## Caveat

**The ADAU1860 is wired to lane 0 only** — its SPT0 has one SDATA_IN and one SDATA_OUT. Lanes 1-3
are proven working on the Pi side but are **not connected to anything** on this bench. Using them
needs either more codec serial ports wired up, or other devices sharing the clock.

`[assumed]` — not verified — that a second ADAU1860 serial port (SPT1) or a second device could be
hung off lanes 1-3 sharing BCLK/WS. The Pi side is proven; the codec-side wiring is not.
