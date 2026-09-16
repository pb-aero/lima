# ADAU1372 EVB -> Pi 5: one single-ended mic on AIN0, analog accel X/Y/Z on AIN1/2/3

**Status: PLAN, 2026-09-16. Nothing in here has been measured on this hardware yet.**
Every claim is tagged. `[ds]` = ADAU1372 datasheet Rev. 0 (92 pp), `[drv]` = mainline ASoC driver
`sound/soc/codecs/adau1372.c` (raspberrypi/linux `rpi-6.12.y`), `[repo]` = measured earlier in this
repo, `[assumed]` = my guess, flagged.

Peter's constraints, given 2026-09-16: link board is the **EVAL-ADUSB2EBZ USBi**, host is a
**Pi 5 (RP1)**, accel content of interest is **AC vibration above ~20 Hz** (no static tilt).

---

## 1. The channel plan

| Pin | Source | Codec path | Notes |
|---|---|---|---|
| AIN0 | electret / single-ended mic | single-ended **with PGA**, MICBIAS0 | PGA −12…+35.25 dB, 0.75 dB steps, plus a 10 dB boost bit `[ds][drv]` |
| AIN1 | accel X | single-ended **line** (PGA bypassed) | |
| AIN2 | accel Y | single-ended line | |
| AIN3 | accel Z | single-ended line | |

Signal chain per channel `[drv]`: `AINx -> PGAx -> ADCx -> Decimatorx -> Output ASRCx -> serial slot n`.

**Polarity gotcha `[ds]`:** signals through the PGA come out **inverted**; the plain single-ended
line path does not. So the mic is inverted relative to the three accel channels. Harmless for
spectra, fatal for anything that cross-correlates mic against accel — fix it in software.

---

## 2. What the USBi is, and what it is not

The EVB's `J1` control header mates with the **EVAL-ADUSB2EBZ** USBi `[fetched: UG-807]`. That board
is a **USB -> I2C/SPI control bridge for SigmaStudio**. It carries **no audio**, and its host side is
SigmaStudio on Windows — it is not a Pi audio interface. Audio leaves the EVB on the serial-audio
header (BCLK / LRCLK / ADC_SDATA0) and has to reach the Pi's I2S pins on its own.

Two arrangements work:

- **(a) Pi owns everything — recommended.** Pi I2C to the EVB control header, Pi I2S to the serial
  audio header, mainline `adi,adau1372` ASoC driver. Nearly every setting needed here is an ALSA
  control (§4), so SigmaStudio is not required at all.
- **(b) SigmaStudio configures, Pi only listens.** Registers set over the USBi from a Windows PC,
  Pi reads I2S with a dummy codec (the pattern already proven here for the ADAU1860 `[repo]`).

**Do not run both at once.** If SigmaStudio writes registers behind the kernel's regmap cache, the
ALSA controls read back the value the kernel *thinks* is there while the part does something else —
the silent-no-op failure this repo has been bitten by before.

---

## 3. Analog side

### 3.1 Single-ended wiring `[ds]`

- **Tie each `AINxREF` to the `CM` pin** (datasheet Figure 52, single-ended line inputs). The pin
  description also accepts `AINxREF` ac-coupled to ground through 10 µF; both put the reference at
  the common mode. **What the EVB actually does is unverified** — I could not pull UG-807 from this
  network (analog.com times out and every mirror I tried 403s). Check the board/schematic before
  assuming.
- **Line mode = PGA off:** set `PGA_ENx = 0` and leave `PGA_POP_DISx = 1` in `POP_SUPPRESS` (0x29).
  Both are already the **reset state** (`PGA_CONTROL_x` reset 0x40, `POP_SUPPRESS` reset 0x3F), so
  for AIN1/2/3 the correct configuration is "don't touch it" — but read the registers back and prove
  it rather than trusting the reset column.
- **Mic on AIN0:** PGA enabled, `MICBIAS0` on, 2 kΩ series into the pin (datasheet Figure 51).
  MICBIAS level is `0.9 × AVDD` or `0.65 × AVDD` via `MIC_GAIN0` (0x2D). **The Linux driver does not
  expose that bit** — it only exposes the enable. Default is 0.9 × AVDD.
- Unused analog pins: tie to `CM` or ac-couple to ground.

### 3.2 Levels `[ds]`

Full scale, single-ended, scales with AVDD: **AVDD / 3.63 V rms** — 0.90 V rms (2.54 V p-p) at
AVDD = 3.3 V, 0.49 V rms at 1.8 V. **Confirm which AVDD the EVB is strapped to before sizing
anything** — it is a factor of 1.8 in headroom.

Input impedance is gain-dependent: 14.3 kΩ for the line input at 0 dB, and for the PGA
32.0 kΩ at −12 dB, 20 kΩ at 0 dB, 0.68 kΩ at +35.25 dB; `Rin(kΩ) = 40 / (10^(gain/20) + 1)`.

**The accelerometer almost certainly needs a buffer.** A typical analog accel (ADXL335 class) has a
~32 kΩ output impedance `[assumed — tell me the part]`. Driving 14.3 kΩ directly loses about two
thirds of the signal and drags the coupling-cap corner up with it. One rail-to-rail unity-gain
follower per axis at the sensor end fixes both.

Sanity check with a 300 mV/g sensor `[assumed]`: ±1 g of vibration = 300 mV peak = 0.21 V rms =
−12.6 dBFS at AVDD 3.3 V. Comfortable, no PGA gain needed on the accel channels.

### 3.3 Frequency response

The accel's DC offset (~AVDD/2) is blocked by the input coupling capacitor, and the codec biases its
inputs at AVDD/2 anyway — **static tilt is not recoverable**, which matches the >20 Hz requirement.

The ADC high-pass is selectable **Off / 1 Hz / 4 Hz / 8 Hz** `[ds][drv]`, but it is configured **per
pair**: `ADC 0+1` and `ADC 2+3`. Mic (ADC0) and accel X (ADC1) therefore share one setting. At a
20 Hz floor this costs nothing — set both pairs to 1 Hz.

The real low corner is the series coupling capacitor against Rin, not the digital filter, and its
value on the EVB is unknown here. **Measure it** (§6, step 5) instead of calculating it from a
schematic you haven't read.

ADCs run internally at 96 or 192 kHz with ASRCs onto the serial port rate `[ds]`.

---

## 4. Slot routing, and the ALSA controls that do it

Driver reset defaults `[drv]` already give the wanted map: `SOUT_SOURCE_0_1 = 0x54`,
`SOUT_SOURCE_2_3 = 0x76` (slots 0-3 <- Output ASRC0-3) and the ASRC sources point at the matching
decimators, so **ADC0..ADC3 land in TDM slots 0..3**. Verify; do not assume.

Controls worth setting explicitly (see `setup-inputs.sh`):

| Control | Value |
|---|---|
| `PGA 0 Capture Switch` | on (mic) |
| `PGA 1/2/3 Capture Switch` | off (line mode for the accel axes) |
| `PGA 0 Capture Volume` | start at 0 dB, raise to taste |
| `ADC 0..3 Capture Switch` | on |
| `ADC 0+1 / 2+3 High-Pass-Filter` | `1 Hz` |
| `Decimator 0+1 / 2+3 Capture Mux` | `ADC` (not `DMIC`) |
| `Output ASRC0..3 Capture Mux` | `Decimator0..3` |
| `Serial Output 0..3 Capture Mux` | `Output ASRC0..3` |

`MICBIAS0` is a DAPM **supply** with no route of its own, so no `amixer` control turns it on — it has
to be pulled up by a machine route in the overlay (`"Mic Jack", "MICBIAS0"`). Without that the mic
gets no bias and the channel is silent-but-alive.

---

## 5. Transport — the part most likely to bite

The EVB clocks itself from its own oscillator, so the **codec is the clock provider** and the Pi is
the consumer. On a Pi 5 that is not a configuration choice: `dwc-i2s.c` fixes the direction from a
synthesis parameter, so you must select the consumer block, `i2s_clk_consumer` = `rp1_i2s1`
`[repo, measured 2026-09-02]`.

TDM4 / 32-bit / 48 kHz is in the driver's allowed rate set for TDM4 `[drv]` and gives BCLK
6.144 MHz, LRCLK 48 kHz.

**The scar to respect `[repo, measured 2026-09-02/07]`:** with the ADAU1860 on this same silicon, RP1
would not lock to a narrow TDM frame sync, the codec had to fall back to stereo framing, and only
slots 0 and 2 ever arrived — 4 channels became 2. Assume nothing better here until it is measured.

Why this case may genuinely differ: datasheet Table 20 lets the ADAU1372 run TDM with `LR_MODE = 0`,
i.e. a **50%-duty LRCLK**, and that is exactly what the mainline driver programs when the DAI format
is `i2s` and `dai-tdm-slot-num = 4` (it only sets `LR_MODE = 1` for `dsp_a`/`dsp_b`) `[ds][drv]`.
That is a different signal from the one RP1 rejected. **Untested.**

Two traps found while reading the code, both of which produce silence rather than an error:

1. **TDM slot masks are mandatory.** `adau1372_set_tdm_slot()` writes `SOUT_CONTROL0 = ~tx_mask`; a
   missing mask means `tx_mask = 0`, so it writes 0xFF and **disables every output slot**. On the
   CPU side `dw_i2s_set_tdm_slot()` rejects an empty mask outright and insists `rx_mask == tx_mask`
   and `slot_width == 32` `[drv]`. So the overlay must carry `dai-tdm-slot-tx-mask` **and**
   `-rx-mask` = `<1 1 1 1>` on both DAIs.
2. **The second data lane is closed by the driver.** `ADC_SDATA_CH` (0x17) already splits channels
   0/1 to ADC_SDATA0 and 2/3 to ADC_SDATA1, which would give 4 channels as two plain stereo lanes
   and dodge TDM entirely — but the pin is shared (`ADC_SDATA1/CLKOUT/MP6`), its reset function is
   "push-button volume down" (`MODE_MP6` reset 0x11), and **the driver deliberately writes
   `MODE_MP6 = 0x12` = CLKOUT at probe** `[ds][drv]`. Using it needs a one-line driver patch
   (`MODE_MP6 = 0x00`, Serial Output 1) plus a second RP1 RX lane — GPIO 22/24/26 can mux to `i2s1`
   `[pinctrl-rp1.c]`, but whether this dwc instance supports >2 channels is unverified.

**Fallback if TDM4 fails:** plain stereo I2S, mic + one axis, and accept two channels — the ADAU1860
outcome. Better than a 4-channel capture where two slots are quietly zero.

---

## 6. Test plan (positive and negative controls)

1. `i2cdetect -y 1` -> the codec answers at **0x3C-0x3F** depending on the ADDR1/ADDR0 strapping
   `[ds]`. Fix the overlay's `reg` to what actually answers.
2. Load the overlay; `arecord -l` shows the card; `arecord -c 4 -f S32_LE -r 48000 -d 2 x.wav -v` and
   **read back what ALSA negotiated** — channels 4, rate 48000, not "close enough".
3. **Positive + negative control per channel:** inject a 1 kHz tone at a known level into AIN1 only.
   It must appear in channel 1 **and the other three must stay at the noise floor**. Repeat per pin.
   This is the only way to prove the slot map; the register defaults are a hypothesis.
4. Level calibration: feed 0.90 V rms (if AVDD = 3.3 V) and confirm ~0 dBFS, then back off 6 dB.
5. Low-frequency corner: chirp 1 -> 100 Hz into an accel channel and find the −3 dB point. This
   measures the EVB's coupling caps, which no datasheet will tell you.
6. Axis identity: tap each axis in turn and confirm which channel moves. Slot order is not axis
   order until proven.

---

## 7. Open / unverified

- `[gap]` **UG-807 (EVB user guide) not read** — coupling cap values, AINxREF wiring, input
  connectors, MCLK oscillator frequency and the link/jumper defaults are all still unknown here.
  Everything in §3.1 and the 12.288 MHz in the overlay is provisional until it is.
- `[gap]` **AVDD strapping on the EVB** (1.8 V or 3.3 V) — sets full scale and MICBIAS level.
- `[gap]` **Accelerometer part number and output impedance.**
- `[gap]` **Does RP1 lock to the ADAU1372's 50%-duty TDM4 frame?** The whole 4-channel plan rests on
  this one measurement.
