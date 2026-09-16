# ADAU1372 on the Pi's own I2C — confirmed, clocking, transporting. ADCs silent.

`[measured]` 2026-09-16 on `aeronode.local` (Pi 5, 6.18.39+rpt-rpi-2712), after Peter wired the EVB's
control port to the Pi's **i2c-1** and confirmed the USBi's **D1 (I2C mode) LED is lit**.

## Confirmed: it is an ADAU1372, at 0x3C

`i2cdetect -y 1` now shows **0x3c** (and 0x51 — see the warning below). Six of seven datasheet reset
values read back exactly, over 16-bit register addressing (`i2ctransfer -y 1 w2@0x3c 0x00 0xRR r1`):

| reg | read | datasheet reset | |
|---|---|---|---|
| 0x1B ADC_CONTROL0 | 0x19 | 0x19 | OK |
| 0x1C ADC_CONTROL1 | 0x19 | 0x19 | OK |
| 0x23 PGA_CONTROL_0 | 0x40 | 0x40 | OK |
| 0x2E DAC_CONTROL1 | 0x18 | 0x18 | OK |
| 0x31 OP_STAGE_MUTES | 0x0F | 0x0F | OK |
| 0x3E MODE_MP6 | 0x11 | 0x11 | OK |
| **0x29 POP_SUPPRESS** | **0x00** | **0x3F** | **mismatch — see correction 1** |

That cannot happen by accident. **The part is alive and the control port works.**

## The control port is gated on the internal clock — with a clean negative control

Writes to `ADC0_VOLUME` (0x1F) did **not** stick until `CLK_CTRL` (0x00) was written. With
`CLK_CTRL = 0x03` or `0x01` (MCLK enabled), `0x55` and `0x33` both read back exactly; with
`CLK_CTRL = 0x00` (MCLK disabled) the same writes read back `0x00`. So the EVB oscillator **is
running**, and the datasheet's "most registers are inaccessible unless the internal clock is enabled"
is literally true.

`[gap]` This does **not** discriminate 12.288 MHz from 24.576 MHz — register access works under both
`CC_MDIV` settings. The EVB's MCLK frequency is still unknown; the overlay assumes 12.288 MHz.

## The codec drives the I2S clocks, and the Pi locks to them

With `SAI_1` (0x33) `SAI_MS = 1`:

| pin | before | after |
|---|---|---|
| GPIO18 `I2S1_SCLK` | lo × 80 | **hi=39 lo=41** |
| GPIO19 `I2S1_WS` | lo × 80 | **hi=41 lo=39** |

A dead line reads 80/0; a running clock scatters. `arecord -f S32_LE -c 2 -r 48000 -d 2` on the
existing `adauduplex` dummy-codec card then ran clean — 96000 frames, no XRUN, no EIO. **Worth
noting against the 2026-09-07 ADAU1860 scar: the Pi locked to this codec's clocks first time.**

## The transport is proven end to end — by loopback, not by assumption

Routing `SOUT_SOURCE_0_1` (0x13) `= 0x98` sends **Serial Input 0/1 straight back out** on slots 0/1.
Playing a 1 kHz tone on GPIO21 while recording GPIO20 returned **peak −0.5 dBFS on slot0 and
−0.9 dBFS on slot1**.

So: Pi TX → codec `DAC_SDATA` → codec `ADC_SDATA0` → Pi RX all work, **both data pins are wired
correctly**, and the serial port, framing and slot mapping are good. This is the measurement that
turns "it might be wiring" into "it is not wiring".

## What does NOT work: the ADC path returns exact zeros

With the full chain configured — `ADC_SDATA0` pin set to serial output, output ASRC enabled,
decimators powered, muxes routed, PGAs unmuted — capture is **0 nonzero samples out of 96000**, on
both slots. Even with **PGA0 at +35.25 dB into a floating input**, which must produce obvious noise
if the analog front end and ADC are alive.

Registers verified in place at the time: `0x00=0x03 0x13=0x54 0x18=0x54 0x1a=0x02 0x1b=0x01
0x1d=0x03 0x23=0xBF 0x32=0x00 0x33=0x01 0x34=0x00 0x39=0x00 0x44=0xFF`.

**Leading hypothesis `[assumed]`: the EVB's analog supply (AVDD) is not present or not linked.**
Every digital function works perfectly — control port, oscillator, serial port, clock generation,
data output. Only the analog-to-digital path produces literally nothing. A missing AVDD (or an
unfitted supply link) fits that split exactly. Worth a meter before any more register archaeology.

Second candidate: something in the hand-rolled init sequence is still wrong, which is why the next
step is to let the **mainline driver** run its own validated init rather than keep guessing.

## Two corrections to CONFIG-PLAN.md

**Correction 1 — `POP_SUPPRESS` (0x29) does not reset to 0x3F; it reads 0x00.** Verified readable and
writable: writing 0x3F reads 0x3F, writing 0x0F reads 0x0F, so this is a real value and not a dead
register. The plan said that for single-ended line inputs on AIN1/2/3 "the correct configuration is
*don't touch it*" because `PGA_POP_DISx` was already 1 at reset. **That was wrong.** Those bits are
0, and the datasheet asks for them to be set for a single-ended line input, so they must be written
explicitly. The datasheet's own reset column for this register disagrees with the silicon.

**Correction 2 — two registers must be written that the plan never mentioned**, both of which the
mainline driver sets at probe and neither of which is obvious from the register map:

- **`MODE_MP1` (0x39) resets to 0x10 = "push-button volume up".** The pin is `ADC_SDATA0/MP1`, so
  until it is set to **0x00 (Serial Output 0)** the codec's only data output pin is not a data
  output at all. A capture will run perfectly and return silence.
- **`ASRC_MODE` (0x1a) bit 1 `ASRC_OUT_EN` resets to 0.** The whole ADC capture path runs through the
  output ASRCs, so with this clear nothing reaches the serial port. The driver models it as the
  `Output ASRC Supply` DAPM widget.

## Warning: 0x51 on i2c-1 is the USBi's own EEPROM

AN-1006 states the USBi carries an EEPROM at **0x51** holding its VID/PID and firmware, and warns
against a second EEPROM at that address. With the ribbon attached while the Pi drives the bus, that
EEPROM now sits on the Pi's I2C bus: **a stray write to 0x51 would brick the USBi.** It also means
two potential masters on one bus. **Unplug the USBi ribbon when the Pi owns the bus.**

## State the codec was left in

`SOUT_SOURCE_0_1` restored to `0x54` (ASRC0/ASRC1), `POP_SUPPRESS` left at `0x0F`, PGA0 at +35.25 dB,
`CLK_CTRL = 0x03`, `SAI_MS = 1`. All of it is volatile — a power cycle returns the part to reset.

## Staged, not yet run

`adau1372-pi5.dtbo` is built and installed in `/boot/firmware/overlays/`; `config.txt` is backed up.
Loading it needs `dtoverlay=adau1860-duplex` (line 81) commented out, because that overlay holds the
same `i2s_clk_consumer` block and GPIO18-21 — and that needs a reboot and Peter's say-so.
