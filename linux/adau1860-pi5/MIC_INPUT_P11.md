# P11 on the EVAL-ADAU1860EBZ — what it is, and what will and will not work

**Date:** 2026-09-08 · **Agent:** LIMA · Peter: *"will probably use P11 on the adau1860 evb"*.

Sourced from **UG-2017** (EVAL-ADAU1860 user guide, 26 pp) — the jumper tables and, decisively,
the **Figure 8 schematic** on p.16, rendered and read at 900 dpi because the schematic pages carry
no extractable text. Crop committed at [`doc/ug2017-adc-inputs.png`](doc/ug2017-adc-inputs.png).
Electrical limits from the ADAU1860 datasheet.

## What P11 is

**`P11` = Analog Input 2 = `ADC2`.** `[fetched]` It is a **3.5 mm stereo (TRS) surface-mount jack**,
CUI `SJ-3523-SMT`, not a header — P9, P10, P11 and P30 are all this same part.

Its route to the Pi is already known: **`SPT0_ROUTEn = 38`** for `ADC2`, and **`ADC2_EN` is bit 2
of `0x4000C004`** — the same register whose bit 4 (`PB0_EN`) the DAC bring-up already writes.
See [`STT_PATH.md`](STT_PATH.md).

## The input network, traced from the schematic

```
P11 pin 1  SLEEVE ──────────────────────────────► GND
P11 pin 2  TIP    ── TP7 ─ P13 ─ R34 (0R) ─ C26 (22uF) ─ P15 ──► AINP2
P11 pin 3  RING   ── TP6 ──────  R33 (0R) ─ C25 (22uF) ───────► AINN2
```

Three facts fall out of that, and each one changes what you should buy.

### 1. There is NO microphone bias. Anywhere.

`[measured, from the schematic]` `R33` and `R34` are **0 Ω**. There is no pull-up, no bias
resistor, no plug-in-power network on the jack, and **the ADAU1860 has no `MICBIAS` pin at all** —
the datasheet pin list runs `AINP2`/`AINN2` straight into the ADC, and neither the datasheet nor
UG-2017 contains the string "MICBIAS".

**Therefore a bare electret capsule, or any standard 3.5 mm "PC/headset microphone", will produce
silence.** Those expect the host to supply plug-in power through a bias resistor. Nothing here
does. The part's "configurable as microphone or line inputs" means *it has a PGA*, not *it feeds
your mic*.

This is the 2026-09-07 muted-DAC scar in a new costume: a correct-looking configuration, every
register reading back perfectly, and no signal — because the fault is upstream of everything the
I2C bus can see.

### 2. Both inputs ARE ac-coupled — so a biased module output is safe

`C25` and `C26` are **22 µF** in series with each input. A module whose output sits on a DC bias
(most of them do) cannot push the ADC off its operating point. `[derived]` against a ~10 kΩ input
impedance that is a ~0.7 Hz corner — irrelevant for speech.

### 3. The PGA is small, so the source must already be near line level

`[fetched]` datasheet: **PGA gain range 0 to 24 dB**, full-scale input **0.49 V rms single-ended**
(0.98 V rms differential), digital gain −71.25 to +24 dB.

24 dB is ×16. An electret capsule puts out a few mV rms; ×16 lands ~−24 dBFS *at best*, and making
up the rest digitally amplifies the noise floor with it. **The gain has to happen before the jack.**

## So: buy an amplified module, not a capsule

What fits: an electret or MEMS module **with its own preamp**, powered from the Pi's 3.3 V, output
a few hundred mV rms. The common ones are the **MAX9814** (electret + automatic gain control,
40/50/60 dB selectable) and the **MAX4466** (electret + adjustable gain). Either clears the
0.49 V rms full scale comfortably — with the MAX9814 expect to *reduce* its gain rather than raise
it, and its ~1.25 V output bias is blocked by C26 anyway.

`[gap]` Specific part numbers, prices and stock are **not** verified here — I have not priced these.

## Wiring, and the one counter-intuitive bit

The default jumpers are **differential**: `P13` pin 1-2 **and** `P15` pin 1-2 `[fetched]`, UG-2017
Table 3. In that state TIP drives `AINP2` and RING drives `AINN2`.

The two single-ended options both act on the **`AINP2` (TIP) side**: `P13` 2-3 grounds `AINP2`,
`P15` 2-3 ties it to `CM`. **So UG-2017's documented single-ended mode expects the signal on the
RING**, which a plain mono plug does not drive. Worth knowing before wiring a TRS lead.

`[derived]` **Simplest thing that should work, and what I would try first:** leave both jumpers in
the **default differential** position and wire the plug as

```
module OUT  -> TIP
module GND  -> SLEEVE,  and short RING to SLEEVE at the plug
```

`AINP2` then sees the signal and `AINN2` sits at ac ground through C25 — a pseudo-differential
connection into a differential input, which is ordinary practice. This is my reading, **not** a
UG-documented mode, so treat it as the first hypothesis rather than the answer.

## The alternative the board also offers

`[measured, from Figure 7]` the EVB breaks out the **PDM digital mic** pins too: `P44` carries
`DMIC_CLK_MP0` + `DMIC01_MP1`, and `P23` carries `DMIC_CLK_MP0` + `DMIC23_MP2`. A PDM MEMS mic
needs **no bias network, no preamp and no analog gain question** — it arrives already digital, and
`DMIC0-3` route to `SPT0` at values **39-42**. If P11 turns into a fight, this is the cheaper
second path, not a rewrite.

## Positive control — do not skip it

A dead route, an unbiased mic and a quiet room are **indistinguishable**. When the mic is
connected, capture while **tapping it**, and require the noise floor to move. Sweep
`SPT0_ROUTE0` across 36/37/38 if slot 0 is silent — the `LARK` vs `LARK_LITE` enum split
(`STT_PATH.md`) means the value could be `0`-based on this part, and the ID registers do not say.
