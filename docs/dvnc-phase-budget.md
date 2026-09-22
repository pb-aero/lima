# The DVNC phase budget — accelerometer reference against the IM72D128V PDM mic

**Date:** 2026-09-22 · **Agent:** LIMA · **Status:** derived. Nothing measured on hardware.
**Trigger:** Peter asked what the phase budget is with the IM72D128V. It can now be assembled, because
Infineon specifies the mic's phase response directly.

Provenance: `[fetched]` = read off the vendor PDF, page cited · `[graph]` = **read off a figure, ±2–3°**
· `[derived]` = arithmetic shown · `[assumed]` = **not established, flagged** · `[repo]` = in this
repository.

---

## 1. The answer in one line

**Uncorrected this does not work at any coupling-capacitor value** — the floor is around **−9 dB** at
both edges of the 50–300 Hz band. **But the correction splits in two, and only half of it is hard:**
the accelerometer contributes a **pure 148 µs delay** (fixable with a 7-sample digital delay, exactly),
while the microphone contributes a **frequency-dependent** phase error that needs a real correcting
filter. After the delay is removed the residual is **18.2° at 50 Hz falling to 4.7° at 300 Hz** — all
of it the mic's. **Phase calibration is mandatory, not optional**, which is what `[repo]` the parts note
already concluded for the IM73A135, for the same reason.

## 2. The mic, specified

`[fetched]` IM72D128V datasheet v01.00, Table 2, Acoustic specifications. Test conditions are
**VDD = 1.8 V, fCLK = 3.072 MHz, OSR = 64** — exactly our operating point, so these are not
extrapolated.

| Parameter | Value |
|---|---|
| **Phase response** | **+11° at 75 Hz**, −0.3° at 1 kHz, −4° at 4 kHz |
| **Group delay** | **60 µs at 250 Hz**, 10 µs at 600 Hz, 6 µs at 1 kHz, 3.5 µs at 4 kHz |
| Low-frequency roll-off | **11 Hz** (−3 dB rel. 1 kHz) |
| Sensitivity | −36 dBFS at 1 kHz, 94 dBSPL |
| SNR | 71.5 dB(A) at fCLK = 3.072 MHz |
| AOP | 128 dBSPL (10% THD) |
| **Polarity** | **"Positive pressure increases density of 1's, negative pressure decreases density of 1's in data output"** |

> **The polarity line closes one of the four sign terms** flagged in the level-shifter work: the mic is
> **non-inverting**. Remaining: the codec's 180° analog-path inversion `[fetched]`, the DMIC path's 0°
> `[derived]`, and the accelerometer's axis sign versus physical direction.

`[graph]` Figure 4, typical phase response, read across our band: **≈ +37° at 20 Hz, ≈ +20° at 50 Hz,
+11° at 75 Hz, ≈ +8° at 150 Hz, ≈ +5° at 300 Hz**, crossing zero around 1 kHz. The 75 Hz, 1 kHz and
4 kHz points are specified; the rest are graph readings and carry ±2–3°.

**Consistency check:** a single-pole 11 Hz high-pass alone would give +8.3° at 75 Hz against the
specified +11°, so the roll-off is steeper than one pole. That matters in §4.

## 3. The reference path — it is a SINC filter, and that changes everything

**`[assumed]` single-pole was wrong.** `[fetched]` ADXL354/ADXL355 datasheet Rev. D, p.25, FILTER:

> *"The analog, low-pass antialiasing filter in the ADXL354/ADXL355 provides a **fixed 3 dB bandwidth
> of approximately 1.5 kHz**... **The shape of the filter response in the frequency domain is that of a
> sinc filter.**"*

A sinc in frequency is a boxcar in time, which is **linear phase — constant group delay, not the
arctan(f/fc) of a pole.** `[derived]` For a boxcar, |sinc(πfT)| = 0.707 at fT = 0.4429, so a 1.5 kHz
−3 dB point gives **T = 295 µs and a group delay of 148 µs** — **7.1 samples at 48 kHz.**

Two more `[fetched]` corrections to what the repo carried:

- The **overall** 3 dB bandwidth is **1.9 kHz**, not 1.5 kHz: *"the MEMS sensor has a resonance at
  2.4 kHz and mechanically amplifies the output response at around 1 kHz and above... Therefore, the
  overall 3 dB bandwidth of the ADXL354 is 1.9 kHz."* The 1.5 kHz figure is the antialias filter alone.
- **ADI publishes no phase or group delay for the ADXL354's analog path.** Table 10's group delays
  belong to the **ADXL355's digital** decimation filter, which the analog-output ADXL354 does not have.
  The 148 µs above is derived from the stated sinc shape, not a vendor number.

| | 50 Hz | 75 Hz | 150 Hz | 300 Hz |
|---|---|---|---|---|
| ADXL354 sinc, 148 µs group delay `[derived]` | −2.66° | −3.99° | −7.97° | −15.94° |
| 100 nF C0G into 1 MΩ `[derived]` | +1.82° | +1.21° | +0.61° | +0.30° |
| **reference path net** | **−0.84°** | **−2.77°** | **−7.36°** | **−15.64°** |
| IM72D128V mic | +20.0° `[graph]` | +11.0° `[fetched]` | +8.0° `[graph]` | +5.0° `[graph]` |
| **mismatch** | **20.84°** | **13.77°** | **15.36°** | **20.64°** |
| **uncorrected floor** | **−8.8 dB** | **−12.4 dB** | **−11.5 dB** | **−8.9 dB** |

The single-pole assumption had understated the accelerometer's lag by about 1.4×, so the uncorrected
budget is **worse** than §1 first suggested — around −9 dB at both band edges.

## 4. But the correction splits cleanly into an easy half and a hard half

**This is the useful result.** The two paths fail in structurally different ways:

| | Mechanism | Correction |
|---|---|---|
| **ADXL354** | linear phase, **constant 148 µs group delay** | **a pure digital delay — 7 samples at 48 kHz.** Exact, trivial, no filter design |
| **IM72D128V** | frequency-dependent group delay: `[fetched]` **60 µs at 250 Hz, 10 µs at 600 Hz, 6 µs at 1 kHz** | **a real phase-correcting filter.** Irreducible |

`[derived]` Delay the mic path by 148 µs and the accelerometer's entire contribution disappears. What
remains is the mic's own curve against the coupling cap:

| | 50 Hz | 75 Hz | 150 Hz | 300 Hz |
|---|---|---|---|---|
| residual after the pure delay | 18.18° | 9.79° | 7.39° | 4.70° |
| floor | −10.0 dB | −15.4 dB | −17.8 dB | −21.7 dB |

**So the accelerometer is not the problem — the microphone is**, and specifically its low-frequency
roll-off, which is worst exactly where DVNC works hardest. A delay line gets you nothing at 50 Hz; only
a phase-shaping filter does.

## 4.1 No single capacitor tracks the mic

The tempting move is to give the reference path the mic's own 11 Hz roll-off so the error becomes
common-mode. `[derived]` It does not survive the band: to match at 50 Hz a single pole needs
**fc = 18.2 Hz**; at 300 Hz it needs **26.2 Hz**. One pole cannot be in two places, because the mic's
roll-off is steeper than first order (§2).

**A single frequency is misleading here.** At 75 Hz alone, 10 nF gives a small mismatch and looks like
a 16 dB win over 100 nF. Across the band it is worth a few dB. Optimising a broadband quantity at one
frequency is how you get a number that is true and useless.

## 5. What follows for the design

1. **Calibrate.** Both curves are specified and smooth, with tight manufacturing tolerance `[repo]`
   (±1 dB on the IM73A135). A fixed phase correction in the FastDSP closes this properly and is the
   only thing that gets past −13 dB. It is also already mandatory for the analog mics, so the mechanism
   will exist.
2. **Given calibration exists, choose the capacitor to be small, stable and predictable rather than to
   chase a partial match** — so the low corner, **100 nF C0G into 1 MΩ**, whose own contribution is
   ≤1.8° across the band and barely moves with temperature or tolerance. Chasing 10 nF buys 3.6 dB
   uncorrected and complicates the correction.
3. **Keep the leads short** — `[derived]` 100 pF of stray capacitance on the ADXL354's 32 kΩ output
   costs −0.35° at 300 Hz; 1 nF costs −3.45°.

## 6. What a residual mismatch costs

`[derived]` best achievable cancellation for a residual phase error θ, from 2·sin(θ/2):

| θ | floor | | θ | floor |
|---|---|---|---|---|
| 1° | −35.2 dB | | 10° | −15.2 dB |
| 2° | −29.1 dB | | 12° | −13.6 dB |
| 5° | −21.2 dB | | 20° | −9.2 dB |

## 7. Still open

- ~~ADXL354 filter shape and corner.~~ **Closed — §3. It is a sinc, 148 µs of linear-phase group
  delay.** `[gap]` remaining: ADI publishes no phase or group delay for the analog path, so the 148 µs
  is derived from the stated shape and should be confirmed on the bench — conveniently, by the same
  two-distance measurement as the codec skew, since the two sit in series in one channel.
- `[gap]` **ADC ↔ DMIC relative group delay inside the codec.** `docs/accel-vs-pdm-mic-skew.md`
  establishes ADI publishes neither path and five registers move it. **Measurement, on the shipping
  configuration.** This budget assumes it is zero, which it is not.
- `[gap]` **Whether common-mode phase between reference and error actually helps** depends on the
  control topology, which is John's. The arithmetic here is about matching, not about the algorithm.
- `[graph]` The 50 / 150 / 300 Hz mic figures are read off a curve. If this budget starts driving
  decisions, get the tabulated curve from Infineon or measure it.

## Sources

- **IM72D128V datasheet v01.00** (19 pp, Infineon, 2025-05-04) — Table 2 Acoustic specifications p.5,
  Figure 4 typical phase response p.4, Figure 5 typical group delay p.4. Pinned in
  `scripts/fetch-datasheets.sh`.
- `[repo]` `docs/accel-vs-pdm-mic-skew.md`, `docs/audio-board-level-shifter.md`,
  `docs/two-adau1860-channel-allocation.md`, `.agent/status.md` (ADXL354 and IM73A135 parts notes).
