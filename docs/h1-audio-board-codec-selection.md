# H1 audio board — codec selection for analog accel + analog mic

**Date:** 2026-09-06 · **Agent:** LIMA · **Status:** research, no decision taken.

Peter, 2026-09-06: *"I'm not sure the ADAU1761 will have enough features. We need to connect an
analog accelerometer and an analog mic to whichever chip we choose, as well as connect it to the Pi
via I2S and the AD2428."*

Provenance: `[fetched]` = read from the vendor PDF myself, page cited · `[derived]` = arithmetic
shown · `[gap]` = not established, do not assume.

**analog.com is unreachable from this machine** — HTTP/2 `INTERNAL_ERROR` to curl, Akamai
*Access Denied* to a real browser. Control fetch to raw.githubusercontent.com returned 200 in
0.45 s, so it is ADI specifically, not the network. All ADI PDFs below came from mirrors; revisions
are stated so they can be re-checked against ADI when the block clears.

---

## 1. The two hard limits on the ADAU1761

`[fetched]` ADAU1761 datasheet Rev. A (92 pp, docs.rs-online.com mirror):

**Two ADC channels, not six.** The features page reads *"24-bit stereo audio ADC and DAC"* (p.1) and
p.20 confirms *"The stereo ADC and stereo DAC each have..."*. The *"6 analog input pins"* on the same
page are **input pins into mixers and muxes ahead of a stereo ADC** (Figure 32, input mixers), not six
converters. LINP/LINN/RINP/RINN/LAUX/RAUX all fold down into two channels.

**One serial-clock domain.** p.42, verbatim:

> Because there is only one set of serial data clocks, the input and output ports must always be
> both master or both slave.

So the ADAU1761 cannot present the CM5 and the AD2428W as two independent links. Everything shares
one BCLK/LRCLK. TDM4 and TDM8 are supported; in TDM8 it can be master only up to fS = 48 kHz
(Table 24, p.42).

**Channel budget.** One analog mic + a **single-axis** accelerometer = exactly 2, zero spare. One
analog mic + a **three-axis** accelerometer = 4, and the part cannot do it.

### What the ADAU1761 is genuinely good at, and the 1860 is not

| | ADAU1761 `[fetched]` Rev. A | ADAU1860 `[fetched]` Rev. 0 |
|---|---|---|
| Electret mic bias | **MICBIAS pin**, 0.65 × AVDD or 0.90 × AVDD, selectable high-performance mode (p.31) | **None.** Only `CM`, a 0.85 V common-mode reference explicitly *"as long as these circuits are not drawing current"* (pin G4) |
| Mic gain | PGA −12 dB to +35.25 dB **plus** 0/20 dB boost ⇒ ~55 dB (Fig. 33) | PGA **0 to 24 dB** (p.5) |
| Digital I/O | **1.8 V to 3.65 V** — direct 3.3 V to a CM5 | IOVDD **1.1 V to 1.98 V** — needs level shifting to 3.3 V |
| Package | 32-lead 5 mm × 5 mm LFCSP | 56-ball **0.35 mm pitch** WLCSP, 2.980 × 2.679 mm — HDI, laser microvias |

## 2. Candidates, with the numbers that decide it

| | **ADAU1761** | **ADAU1860** | **ADAU1979** |
|---|---|---|---|
| Analog in | **2** (stereo ADC) | **3**, diff or single-ended, mic **or line**, each with optional PGA | **4** differential |
| Serial ports | **1** | **2 × 16-channel**, to TDM16 | 1 |
| Analog out | stereo + HP drivers | 1 differential (HP or line) | **none** |
| DSP | SigmaDSP 28/56-bit, 50 MIPS | FastDSP + Tensilica HiFi 3z | none |
| Full-scale in | line 21 kΩ @ 0 dB | **0.49 V rms** SE / 0.98 V rms diff | **4.5 V rms** diff |
| ADC HPF | default on, **2 Hz** @ 48 kHz, disable-able (R19 bit 5) | optional, **1 / 4 / 8 Hz** | selectable |
| Rates | 8–96 kHz | ADC 12–768 kHz; SPT 8–768 kHz | 8–192 kHz |
| Supply / IO | 1.8–3.65 V | AVDD 1.8 V, IOVDD 1.1–1.98 V | **single 3.3 V** |
| Package | 32-ld LFCSP 5×5 | 56-ball 0.35 mm WLCSP | 40-ld LFCSP |

`[fetched]` ADAU1860 Rev. 0 (30 pp, docs.ampnuts.ru mirror) — the same abridged datasheet as
`linux/adau1860-pi5/`; **it still carries no register map**, so the serial-port width `[gap]` from
2026-09-02 is still open. ADAU1979 Rev. A: *"four high performance ADCs with 4.5 V rms capable
**ac-coupled** inputs"*, applications list includes *"Active noise cancellation systems"*.

### The architectural point

The ADAU1860's **two serial ports** are the feature the 1761 does not have. SPT0 to the CM5, SPT1 to
the AD2428W, DSP in between — that is a real bridge, and it is where DVNC parameter frames could be
generated or consumed on-chip rather than shuttled through the CM5. It is also the part already in
both cups, so one part family across the product.

The price is three things, all board-level: no mic bias, 24 dB of mic gain instead of 55, and a
1.98 V I/O ceiling against a 3.3 V CM5.

`[fetched, third-party]` The Clockworks A2B-I2S module datasheet (v5r200326) says the AD2428's
IOVDD is *"Jumper selects between AD2428 internal regulator voltages, defaults to 3.3V"*. If the
AD2428W can be set to 1.8 V IO, an ADAU1860↔AD2428W link needs no shifting and only the CM5 side
does. **`[gap]` — confirm in the AD242x datasheet/TRM before designing to it.** This is a
third-party board vendor, not ADI.

## 3. Traps that apply to the accelerometer whatever chip wins

1. **Every one of these inputs is AC-coupled.** ADAU1761 LINP is *"Biased at AVDD/2"* (p.13);
   ADAU1979 says *"ac-coupled"* on its front page. **No DC, no static tilt, no gravity vector.** If
   the accelerometer channel has to carry attitude as well as vibration, no audio codec works and the
   part needed is a DC-coupled SAR/Σ-Δ ADC.
2. **Disable the digital HPF, then size the coupling cap.** Our own vibration reference
   (`dsp/vibration-reference/README_FIR.md`, `[measured]` 2026-09-03) put the dominant content at
   **8.30 Hz** with a 3–25 Hz band of interest. The ADAU1860's HPF choices are 1 / 4 / 8 Hz — **4 Hz
   and 8 Hz sit inside the signal.** Turn it off and let the analog cap set the corner:
   `[derived]` C = 1/(2π·f·R) for a 3 Hz corner → **≈2.5 µF** into the 1761's 21 kΩ line input,
   **≈1.3 µF** into the 1860's 41.2 kΩ differential PGA. Both are ordinary film/ceramic parts.
3. **Headroom.** 0.49 V rms single-ended on the 1860 is 1.39 V p-p. Check the accelerometer's swing;
   an attenuator may be needed. The DC bias itself is blocked by the coupling cap regardless.
4. **48 kHz for a 25 Hz signal is ~1000× oversampled.** Fine, decimate in the DSP — but the ASRCs
   must be out of the path. That is the worst trap from the 2026-09-02 scar: an ASRC on
   accelerometer data fabricates samples and reports no error.

## 4. Open questions that decide the part

1. **How many accelerometer axes — one or three?** One axis fits the 1761 with zero spare; three does
   not fit any single codec here except the ADAU1979.
2. **Does the accelerometer channel need DC / sub-1 Hz response?** If yes, no audio codec qualifies.
3. **Is the audio board bridging two TDM links (CM5 ↔ codec ↔ A2B), or is it one shared TDM8 bus
   with all three devices in slots?** Rev G has the ADAU1761 as system clock master off a local
   12.288 MHz oscillator, which reads as one shared bus. Two links needs the 1860's two ports.
4. **Mic type** — electret (needs bias, favours the 1761) or analog MEMS (needs a supply rail, not a
   bias pin)?

**This supersedes nothing yet.** Rev G's ADAU1761 choice is John's; if the part changes, it changes
the bit map, and it has to go to him rather than be decided here.

## Sources

- ADAU1761 Rev. A — `https://docs.rs-online.com/3eb6/0900766b80de0787.pdf` (RS mirror)
- ADAU1860 Rev. 0 — `https://docs.ampnuts.ru/analog.com.datasheet/adau1860/adau1860.pdf`
- EVAL-ADAU1860 UG-2017 — `https://docs.ampnuts.ru/analog.com.datasheet/adau1860/related_data/eval-adau1860-ug-2017.pdf`
- ADAU1979 Rev. A — `https://docs.ampnuts.ru/analog.com.datasheet/adau1979/adau1979.pdf`
- Clockworks A2B-I2S module v5r200326 — `https://clk.works/wp-content/uploads/Datasheets/A2B/mod.evm_.v2.r5.pdf`
- In-repo: `docs/johns-bitmap.html`, `dsp/vibration-reference/README_FIR.md`, `linux/adau1860-pi5/DATA_OVER_I2S.md`

---

## 5. Which accelerometer? — searched 2026-09-06, and the answer is: none is specified

Peter asked. I searched `lima`, `~/aerosense` (his KiCAD working tree, read-only) and every note in
`.agent/`. **No analog accelerometer exists anywhere in this project.** Every accelerometer on file
is digital:

| Part | Where | Interface |
|---|---|---|
| **BMI088** | `~/aerosense/aeronode/aeronode.kicad_sch` (placed); also `lima:kicad/imu-board/` | SPI, digital |
| **ICM-42688-P** | `~/aerosense/aeronode/aeronode.kicad_sch` (placed) | SPI, digital |
| **ICM-45686** | AERONODE block diagram, `aeronode-lite`; `lima:kicad/imu-board/` U1 | SPI, digital |
| **MPU-9250** | `scopenode`, the 2026-09-03 vibration capture | I2C, digital |
| ADXL363 | `fp-info-cache` only — a library cache entry, **not placed on any board** | SPI, digital |

The **microphone** already on file is digital too: **ICS-43432** on `aeronode.kicad_sch`, an I²S
MEMS mic with an on-die ADC and 24-bit I²S out `[fetched]`, 50 Hz–20 kHz.

So "analog accelerometer and analog mic into the codec" is a **new architecture, not a part
substitution.** Nothing has been chosen. That reframes §1–§4: if the sensors stay digital, the
codec never sees them, the channel budget stops mattering, and the ADAU1761's stereo ADC is
adequate — the accelerometer reaches the CM5 over SPI, or over I2S as a raw sample pipe, which is
exactly what `linux/adau1860-pi5/DATA_OVER_I2S.md` was written for.

`[repo]` The AERONODE block diagram (`~/aerosense/aeronode/aerosense/aeronode-lite/`, 1 Sep) shows
an `AUDIO` block, `GPIO_RLY_MIC` / `GPIO_RLY_SPKR` (John's fail-passive changeover relays) and
`I2S1_SDI0..3` / `I2S1_SDO0..3` — the RP1 four-lane I2S from the 2026-09-02 duplex bring-up. The
audio interface sheet itself (`aeronode-audio-interface.kicad_sch`) currently contains **only
connectors**; no codec is placed.
